#!/usr/bin/env python3
"""comment-digest.py — fetch ALL comments on a Jira issue (paginated) and print a compact
digest: every product owner comment plus the latest comment overall, flattened from ADF to
plain text. Avoids the Atlassian MCP token-cap that large comment threads blow past.

Env: JIRA_EMAIL / JIRA_API_TOKEN / JIRA_SITE (set them in your shell profile).
Usage: python3 comment-digest.py SD-5166 [PO_ACCOUNT_ID]
"""
import os, sys, json, base64, urllib.request, urllib.parse, urllib.error

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

PO_ACCOUNT_ID = os.environ.get("PO_ACCOUNT_ID", "")


def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def adf_text(node):
    """Flatten an Atlassian Document Format node to text."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    t = node.get("type")
    if t == "text":
        return node.get("text", "")
    if t == "hardBreak":
        return "\n"
    s = "".join(adf_text(c) for c in node.get("content", []) or [])
    if t in ("paragraph", "heading", "listItem", "blockquote", "codeBlock"):
        s += "\n"
    return s


key = sys.argv[1] if len(sys.argv) > 1 else die("usage: comment-digest.py <KEY> [PO_ACCOUNT_ID]", 2)
po = sys.argv[2] if len(sys.argv) > 2 else PO_ACCOUNT_ID
email = os.environ.get("JIRA_EMAIL", "")
token = os.environ.get("JIRA_API_TOKEN")
site = os.environ.get("JIRA_SITE", "simedia-data.atlassian.net")
if not email or not token:
    die("MISSING JIRA_EMAIL/JIRA_API_TOKEN — set both in your shell profile", 3)

auth = base64.b64encode(f"{email}:{token}".encode()).decode()
api = f"https://{site}/rest/api/3/issue/{key}/comment"


def page(start):
    url = api + "?" + urllib.parse.urlencode({"startAt": start, "maxResults": "100", "orderBy": "created"})
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        die(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}", 4)
    except urllib.error.URLError as e:
        die(f"NETWORK ERROR: {e} (is the VPN up?)", 5)


def preflight_auth():
    # A bad token makes the issue endpoint 404 ("does not exist or no permission"), which would
    # mislead. Verify identity on /myself first so auth failure is reported as auth failure.
    url = f"https://{site}/rest/api/3/myself"
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            json.load(r)
    except urllib.error.HTTPError as e:
        die(f"AUTH FAILED (HTTP {e.code}) on /myself — JIRA_API_TOKEN is invalid/expired. "
            f"Your JIRA_API_TOKEN has expired. Issue a new one in Atlassian account settings and update your shell profile.", 6)
    except urllib.error.URLError as e:
        die(f"NETWORK ERROR on /myself: {e} (is the VPN up?)", 5)


preflight_auth()
comments = []
start = 0
while True:
    data = page(start)
    comments.extend(data.get("comments", []))
    total = data.get("total", len(comments))
    start += data.get("maxResults", 100)
    if start >= total or not data.get("comments"):
        break


def fmt(c):
    a = (c.get("author") or {}).get("displayName", "?")
    when = c.get("created", "")
    body = adf_text(c.get("body")).strip()
    return f"[{when}] {a}:\n{body}"


po_comments = [c for c in comments if (c.get("author") or {}).get("accountId") == po]

print(f"=== {key} — {len(comments)} comments total, {len(po_comments)} from PO ===\n")
if po_comments:
    print("--- product owner comments (oldest to newest) ---")
    for c in po_comments:
        print(fmt(c))
        print()
else:
    print("(no PO comments)\n")

if comments:
    print("--- Latest comment overall ---")
    print(fmt(comments[-1]))
