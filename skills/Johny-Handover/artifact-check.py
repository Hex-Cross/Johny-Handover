#!/usr/bin/env python3
"""artifact-check.py - READ-ONLY. The three artifacts a ticket must carry, plus receipt conformance.

Why this is a script and not a paragraph in an agent file: the same four checks were already
described in prose in agents/Johny-Pm-Verifier.md lane 6/6b, and on 2026-08-26 an audit of 29
approvals found not one carried a structured RECEIPT line. The knowledge was right; it was never
executed. Prose gets skipped under time pressure, a script does not.

What it reports per ticket:

  DOC:          visible <id> | present but NOT visible <id> | none | n/a
  RECEIPT:      visible <id> | present but NOT visible <id> | exists but NOT linked <id> | none
  RECEIPT-FORM: conform | missing section(s): ... | title off-convention | over-length | n/a
  SHOT:         attached <n> image(s) | none, declared no user-visible surface | none

Two corrections learned the hard way on 2026-08-26, both encoded here:

1. VISIBLE, not merely present. A remote link posted without an `application` is stored and returned
   by GET /remotelink, and Jira never shows it, because the issue's Confluence panel is grouped by
   application.type. Six links across five tickets were invisible while every check called them
   linked. So the test is application.type == com.atlassian.confluence.
2. Match on PAGE ID, not URL string. Confluence serves one page as /wiki/spaces/<X>/pages/<id> and as
   /wiki/pages/viewpage.action?pageId=<id>. String comparison reported "not visible" for a page that
   was plainly linked.

And one older lesson kept: search BOTH title conventions plus a full-text fallback, or the absence
claim is false. A receipt whose title omits the key was nearly reported missing on 2026-08-26.

Usage:  artifact-check.py SD-1234 [SD-1235 ...]
        artifact-check.py --jql 'project=SD AND status="To Be Checked"'
        add --json for machine-readable output.
"""
import argparse, base64, json, os, re, sys, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

SITE = os.environ.get("JIRA_SITE", "simedia-data.atlassian.net")
EMAIL = os.environ.get("JIRA_EMAIL") or sys.exit("set JIRA_EMAIL")
RECEIPT_PARENT = "568066050"      # Fix Receipts - Process, the parent every receipt hangs under
RECEIPT_TEMPLATE = "568098817"    # Fix Receipt - Template, the source of the required sections

# Fallback only. The live template is fetched first, so a change there does not silently pass.
# Fallback only, and it deliberately EXCLUDES "Notes for reviewers": the live template marks that
# section Optional. Everything here is required.
FALLBACK_SECTIONS = [
    "Root cause", "Fix", "Regression checks done", "Files changed", "Coverage trade-offs",
    "Out of scope, flagged elsewhere", "DoD mapping", "How to verify after deploy",
]
HEADER_FIELDS = ["Status", "Ticket", "First detected", "Repo touched"]

# Same vocabulary as review-comment-guard.py, deliberately: a ticket opts out of the screenshot by
# SAYING it has no user-visible surface, so the reader learns why there is no image.
NO_UI_SURFACE = re.compile(
    r"no user-visible surface|not user visible|backend only|no ui surface|"
    r"infrastructure only|no visible change|documentation change", re.I)

_auth = None
def auth():
    global _auth
    if _auth is None:
        tok = os.environ.get("JIRA_API_TOKEN")
        if not tok:
            sys.exit("set JIRA_API_TOKEN (set them in your shell profile)")
        _auth = "Basic " + base64.b64encode(f"{EMAIL}:{tok}".encode()).decode()
    return _auth

def get(path, params=None, tries=3):
    url = f"https://{SITE}{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
    for n in range(tries):
        try:
            r = urllib.request.Request(url, headers={"Authorization": auth(), "Accept": "application/json"})
            with urllib.request.urlopen(r, timeout=60) as f:
                return json.load(f)
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 504) and n < tries - 1:
                continue
            return {"__error__": f"HTTP {e.code}"}
        except Exception as e:
            if n < tries - 1:
                continue
            return {"__error__": str(e)}

def adf(n):
    if isinstance(n, dict):
        return n.get("text", "") + "".join(adf(c) for c in (n.get("content") or []))
    if isinstance(n, list):
        return "".join(adf(c) for c in n)
    return ""

def page_id(url):
    """Pull the numeric page id out of either Confluence URL form."""
    m = re.search(r"/pages/(\d+)", url or "") or re.search(r"[?&]pageId=(\d+)", url or "")
    return m.group(1) if m else None

def norm(s):
    """Compare headings by meaning, not punctuation: dashes, commas and case all vary in practice.
    The internal-whitespace collapse is load-bearing, not tidiness. Without it the template's
    "Out of scope - flagged elsewhere" normalised to a DOUBLE space where a receipt's
    "Out of scope, flagged elsewhere" had one, and four conform receipts were reported as missing
    that section."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())).strip()

_sections = None
def required_sections():
    """Read the LIVE template, and read its OPTIONALITY from the template too.

    A hand-maintained list is how a standard drifts: receipts.md paraphrases this and drops
    "Notes for reviewers" entirely. But the template also marks that one section "(Optional...)",
    so requiring every heading it defines is equally wrong in the other direction, and it briefly
    reported four conform receipts as non-conform here. The rule the template states for itself is
    what gets enforced: sections are required unless their own body says Optional."""
    global _sections
    if _sections is not None:
        return _sections
    d = get(f"/wiki/rest/api/content/{RECEIPT_TEMPLATE}", {"expand": "body.view"})
    html = ((d.get("body") or {}).get("view") or {}).get("value", "") if isinstance(d, dict) else ""
    heads = [(m.start(), re.sub(r"<[^>]+>", "", m.group(1)).strip())
             for m in re.finditer(r"<h2[^>]*>(.*?)</h2>", html, re.S)]
    found = []
    for i, (pos, title) in enumerate(heads):
        if not title or title.lower().startswith("fix receipt"):
            continue
        end = heads[i + 1][0] if i + 1 < len(heads) else len(html)
        body = re.sub(r"<[^>]+>", " ", html[pos:end])
        if re.search(r"\(\s*optional", body, re.I):
            continue                     # the template says this one is the author's call
        found.append(title)
    _sections = found or FALLBACK_SECTIONS
    return _sections

_anc = {}
def under_receipt_parent(pid):
    """The only reliable discriminator. A DELIVERY DOC and a FIX RECEIPT are both routinely titled
    "<KEY> - <summary>", so title alone cannot tell them apart: SD-5716's doc page was classified as
    a receipt and then reported as missing all nine template sections, which it has no obligation to
    have. Receipts hang under 568066050; docs hang under a domain folder."""
    if pid in _anc:
        return _anc[pid]
    d = get(f"/wiki/rest/api/content/{pid}", {"expand": "ancestors"})
    ids = {a.get("id") for a in (d.get("ancestors") or [])} if isinstance(d, dict) else set()
    _anc[pid] = RECEIPT_PARENT in ids
    return _anc[pid]

def receiptish(title, key, pid=None):
    """Parent first, title second. The title fallback exists because the second convention
    ("Fix Receipt: <KEY> - ...") files pages under domain folders rather than the process page."""
    t = (title or "")
    if pid and under_receipt_parent(pid):
        return True
    return t.lower().startswith("fix receipt")

def check_form(pid, key):
    """Conformance of one receipt page against the live template."""
    d = get(f"/wiki/rest/api/content/{pid}", {"expand": "body.view,ancestors"})
    if not isinstance(d, dict) or "__error__" in d:
        return "unreadable", {}
    html = ((d.get("body") or {}).get("view") or {}).get("value", "")
    title = d.get("title", "")
    heads = [norm(re.sub(r"<[^>]+>", "", m.group(2)))
             for m in re.finditer(r"<h([1-4])[^>]*>(.*?)</h\1>", html, re.S)]
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    problems = []

    missing = [s for s in required_sections() if norm(s) not in heads]
    if missing:
        problems.append("missing section(s): " + ", ".join(missing))

    absent_header = [h for h in HEADER_FIELDS if not re.search(rf"\b{re.escape(h)}\b", text, re.I)]
    if absent_header:
        problems.append("header field(s) absent: " + ", ".join(absent_header))

    # Both live title conventions are legitimate; anything else is off-convention.
    if not (re.match(rf"^{re.escape(key)}\b", title, re.I)
            or re.match(rf"^fix receipt:\s*{re.escape(key)}\b", title, re.I)):
        problems.append("title off-convention")

    # The standard's own wording: "300 to 800 words. Code snippets and tables do not count toward
    # the budget." So they are STRIPPED before counting, rather than counted and compensated for
    # with a loose threshold. Counting them made SD-5967 read as over-length at 1456 words when most
    # of that was its regression-check, files-changed and DoD-mapping tables.
    prose_html = re.sub(r"<table\b.*?</table>", " ", html, flags=re.S | re.I)
    prose_html = re.sub(r"<(pre|code)\b.*?</\1>", " ", prose_html, flags=re.S | re.I)
    prose = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", prose_html))
    words = len(prose.split())
    # ADVISORY, not a blocker, and the distinction comes from the process page rather than from me:
    # 568066050 has a heading "Required sections" and a SEPARATE heading "Length guidance". A missing
    # section is a requirement unmet; length is guidance. Blocking on it pushed toward trimming
    # SD-5715, a decision record for a ticket where nothing was built and the reasoning IS the
    # deliverable. Cutting content to satisfy a counter is the same failure as ticking a DoD box
    # without doing the work.
    note = f"long ({words} words of prose, guidance is 300 to 800)" if words > 1000 else None

    verdict = "; ".join(problems) if problems else "conform"
    if note:
        verdict += f" [advisory: {note}]"
    return verdict, {
        "title": title, "words": words,
        "parent": (d.get("ancestors") or [{}])[-1].get("id") if d.get("ancestors") else None,
    }

def check(key):
    key = key.upper()
    out = {"key": key}
    f = get(f"/rest/api/3/issue/{key}",
            {"fields": "summary,status,assignee,description,attachment,comment"})
    if "__error__" in f:
        out["error"] = f["__error__"]
        return out
    fields = f.get("fields", {})
    out["summary"] = (fields.get("summary") or "")[:60]
    out["status"] = (fields.get("status") or {}).get("name", "?")
    out["assignee"] = (fields.get("assignee") or {}).get("displayName", "unassigned")
    out["assignee_id"] = (fields.get("assignee") or {}).get("accountId", "")
    desc = adf(fields.get("description") or {})
    out["has_dod"] = "definition of done" in desc.lower()
    comments = " ".join(adf(c.get("body") or {}) for c in (fields.get("comment") or {}).get("comments", []))

    # --- links, split into visible and merely-present
    rl = get(f"/rest/api/3/issue/{key}/remotelink")
    rl = rl if isinstance(rl, list) else []
    wiki = []
    for r in rl:
        o = r.get("object") or {}
        pid = page_id(o.get("url"))
        if not pid:
            continue
        wiki.append({"pid": pid, "title": o.get("title") or "", "url": o.get("url"),
                     "visible": (r.get("application") or {}).get("type") == "com.atlassian.confluence"})

    # --- receipt discovery: BOTH title conventions, then full text. Never one instrument.
    hits = []
    t = get("/wiki/rest/api/search", {"cql": f'title ~ "{key}"', "limit": 10})
    for r in (t.get("results") or []):
        c = r.get("content") or {}
        if c.get("id"):
            hits.append({"pid": c["id"], "title": c.get("title", "")})
    if not hits:
        x = get("/wiki/rest/api/search", {"cql": f'text ~ "{key}"', "limit": 10})
        for r in (x.get("results") or []):
            c = r.get("content") or {}
            if c.get("id") and receiptish(c.get("title"), key, c["id"]):
                hits.append({"pid": c["id"], "title": c.get("title", "")})

    linked_receipt = next((w for w in wiki if receiptish(w["title"], key, w["pid"])), None)
    unlinked_receipt = None
    if not linked_receipt:
        linked_pids = {w["pid"] for w in wiki}
        unlinked_receipt = next((h for h in hits
                                 if receiptish(h["title"], key, h["pid"]) and h["pid"] not in linked_pids), None)

    if linked_receipt and linked_receipt["visible"]:
        out["receipt"] = f"visible {linked_receipt['pid']}"
        out["receipt_pid"] = linked_receipt["pid"]
    elif linked_receipt:
        out["receipt"] = f"present but NOT visible {linked_receipt['pid']} (no Confluence application; add a jira macro to the page body)"
        out["receipt_pid"] = linked_receipt["pid"]
    elif unlinked_receipt:
        out["receipt"] = f"exists but NOT linked {unlinked_receipt['pid']}"
        out["receipt_pid"] = unlinked_receipt["pid"]
    else:
        out["receipt"] = f"none (assignee {out['assignee_id'] or 'unassigned'})"
        out["receipt_pid"] = None

    # --- doc: any other linked Confluence page
    docs = [w for w in wiki if not (linked_receipt and w["pid"] == linked_receipt["pid"])]
    if not docs:
        out["doc"] = "none"
    else:
        vis = [d for d in docs if d["visible"]]
        out["doc"] = (f"visible {vis[0]['pid']}" if vis
                      else f"present but NOT visible {docs[0]['pid']}")

    # --- receipt conformance
    if out["receipt_pid"]:
        verdict, meta = check_form(out["receipt_pid"], key)
        out["receipt_form"] = verdict
        out["receipt_title"] = meta.get("title", "")
    else:
        out["receipt_form"] = "n/a (no receipt)"

    # --- screenshot
    shots = [a for a in (fields.get("attachment") or [])
             if str(a.get("mimeType", "")).startswith("image/")]
    if shots:
        out["shot"] = f"attached {len(shots)} image(s)"
    elif NO_UI_SURFACE.search(desc) or NO_UI_SURFACE.search(comments):
        out["shot"] = "none, ticket declares no user-visible surface"
    else:
        out["shot"] = f"none (assignee {out['assignee_id'] or 'unassigned'})"

    blockers = []
    if not out["receipt"].startswith("visible"):
        blockers.append("receipt")
    # An advisory-only verdict still reads "conform [advisory: ...]" and must not block.
    rf = out["receipt_form"]
    if not (rf.startswith("conform") or rf.startswith("n/a")):
        blockers.append("receipt-form")
    if out["shot"].startswith("none ("):
        blockers.append("screenshot")
    out["blockers"] = blockers
    out["verdict"] = "ARTIFACTS OK" if not blockers else "BLOCKED: " + ", ".join(blockers)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("keys", nargs="*")
    ap.add_argument("--jql")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()

    keys = [k.upper() for k in a.keys]
    if a.jql:
        tok = None
        while True:
            p = {"jql": a.jql, "fields": "key", "maxResults": 100}
            if tok:
                p["nextPageToken"] = tok
            d = get("/rest/api/3/search/jql", p)
            if "__error__" in d:
                sys.exit(f"JQL failed: {d['__error__']}")
            keys += [i["key"] for i in d.get("issues", [])]
            tok = d.get("nextPageToken")
            if not tok or d.get("isLast"):
                break
    if not keys:
        sys.exit("give ticket keys or --jql")

    required_sections()   # warm once, before the pool, so every worker sees the same list
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        rows = list(ex.map(check, keys))

    if a.json:
        print(json.dumps(rows, indent=1))
        return 0

    print(f"template sections in force ({len(required_sections())}): "
          + " | ".join(required_sections()))
    ok = 0
    for r in sorted(rows, key=lambda x: int(re.sub(r"\D", "", x["key"]) or 0)):
        if r.get("error"):
            print(f"\n{r['key']}  READ FAILED: {r['error']}")
            continue
        print(f"\n{r['key']}  [{r['status']}]  {r['assignee']}  {r['summary']}")
        print(f"  DOC:          {r['doc']}")
        print(f"  RECEIPT:      {r['receipt']}")
        print(f"  RECEIPT-FORM: {r['receipt_form']}")
        print(f"  SHOT:         {r['shot']}")
        if not r["has_dod"]:
            print("  NOTE:         ticket has NO 'Definition of Done' section")
        print(f"  VERDICT:      {r['verdict']}")
        ok += 1 if not r["blockers"] else 0
    print(f"\n{'='*70}\n{ok} of {len(rows)} clear the artifact gate")
    return 0

if __name__ == "__main__":
    sys.exit(main())
