---
name: Johny-Handover
description: >-
  Read-only pre-flight self-check a Simedia developer runs on their OWN ticket before handing it in.
  Produces one standardized report naming every Definition-of-Done item that is still unmet, split
  into what the developer can close themselves and what only the project tooling can close, plus a
  paste-ready handover comment that has already been cleared by the review comment guard. It reads
  Jira, Bitbucket and Confluence and writes nothing anywhere: no comment, no transition, no PR, no
  deploy. It is the AUTHOR-side pre-flight. The delivery gate that actually links a receipt and moves
  a ticket is Johny-Receipt; the reviewer-side gate is Johny-Pm.
version: 1.0.0
user-invocable: true
# Curated and used VERBATIM by command-center/refresh-registries.mjs, whose single-line regex cannot
# see the folded description above. Deliberately DISJOINT from Johny-Receipt's triggers ("move SD-xxxx
# to To Be Checked", "hand this in", "ready for review", "I am done with SD-xxxx") and from Johny-Pm's
# hard-routed "to be checked", so a developer asking what is missing does not fire a write path and a
# reviewer asking for the column does not fire this one.
triggers:
  - johny-handover
  - johny handover
  - johny handover sd
  - johny
  - self-check
  - self-check sd
  - what is missing on sd
  - what is missing from my implementation
  - what is missing from my ticket
  - check my implementation
  - check my own ticket
  - what is missing from my work
  - check my work before i hand it in
  - pre-flight sd
  - preflight my ticket
  - handover check
  - handover report
  - am i ready to hand this in
  - is my ticket complete
---

# Johny-Handover - check your own ticket before you hand it in

You are checking **one ticket, assigned to the person asking**, and you are checking it the way the
reviewer will. The deliverable is `report-template.md` filled in with real evidence, and nothing else.

**Why this exists.** On 2026-08-26 a board-wide audit found 47 of 80 Approved tickets had a real fix
receipt sitting unlinked, and only 15 had none at all. Two days later, on one developer's queue,
nine of ten blocked tickets were blocked on a Confluence link rather than on the work. The review had become a mechanical
checker for things the author could have seen first. This moves that check earlier.

## Two rules that shape every report

1. **Every unmet item is tagged with who can close it.** `FIX: YOU`, `FIX: TOOLING`, or `FIX: PO`. A
   developer's `POST /issue/<KEY>/remotelink` lands without `apps=['Confluence']`, so turning an
   existing Confluence page into a link a reviewer can read is **not something the author can do** - it
   needs the project tooling. Authoring a Definition of Done is the product owner's. Readiness counts
   `FIX: YOU` and `FIX: PO`; `FIX: TOOLING` is counted separately and never reduces it. Never present a
   TOOLING or PO item as a failure of the developer's work.
2. **A ticket with no Definition of Done section is NOT READY, and the gap is the product owner's.**
   Roughly half the board has no DoD (48 of 60 measured on 2026-08-28), and an empty checklist passes
   vacuously. Do NOT fall back to an invented bar: a ticket that passes a bar we made up still gets
   rejected by the reviewer, and that false green is the worst thing this tool can do. Print
   `DOD SOURCE: NONE (ticket has no DoD)`, emit one `FIX: PO` item, and say plainly that asking the
   product owner for a Definition of Done is the useful next move. Never the developer's gap.
3. **Warn when nothing in any repo carries the change.** The reviewer applies "only merged code counts
   as proof of completion" and has rejected on it even where the DoD asked for no code (SD-5303,
   2026-08-31). When the feature search comes back empty, print `WILL LIKELY BOUNCE: yes`. It is a
   warning about what will happen, never an unmet item and never the developer's mistake.

## Step 0 - Resolve the repo root and probe access, then name what failed

```
root="${SIMEDIA_ROOT:?set SIMEDIA_ROOT to your Simedia checkout directory}"
```
`repo-map.json` declares `root_env: SIMEDIA_ROOT`; use the env var, and fall back to its `root` value
only when the variable is unset and that path exists.

Credentials come from plain environment variables. Confirm each one is set before running anything,
and **name the missing variable rather than working around it**:

| Lane | Needs |
|---|---|
| Jira read | `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_SITE` |
| Bitbucket PR state | `BITBUCKET_EMAIL`, `BITBUCKET_API_TOKEN`, `BITBUCKET_WORKSPACE` |
| Repo lanes | a local checkout under `$SIMEDIA_ROOT` and network reach to Bitbucket over IPv4 |

Bitbucket needs IPv4: force `GIT_SSH_COMMAND="ssh -4"` and `curl -4` on every call, or the
allowlist rejects the IPv6 attempt.

## Step 1 - Confirm the ticket is yours

Read the ticket's `assignee`. If it is somebody else's, stop and say so. Another person's ticket is
not yours to pre-flight, for the same reason a fix receipt is written by whoever landed the fix.

## Step 2 - Run the verifier

Spawn one `Johny-Handover-Verifier` for the ticket, passing the key, the mapped repo path, and the
feature nouns from the summary. It runs the repo and artifact lanes and returns the filled key block.
Do not hand-roll its lanes here, and do not add a live-system lane: this self-check deliberately never
drives the application.

## Step 3 - Render the report

Fill `report-template.md`. The key block comes first, byte-identical in key names and order, and the
prose explanation follows it. Every unmet item carries the command or the file reference that proves
it is unmet. An absence with no proving command is not a finding; drop it or mark it unverified.

## Step 4 - Clear the handover comment locally, then hand it over as text

Write the four-layer draft to a file and run the guard:

```
python3 <handover-dir>/review-comment-guard.py draft.txt
```

Exit 0 means it is safe to paste. Exit 1 means it is not, and the guard names which of the four
layers is missing: what **ran** (spec, regression test, load test), what **changed** (commit sha,
files, merged), where the **documentation** is (receipt, root cause), and what was seen **live**.
It also rejects em and en dashes, local filesystem paths, and internal tooling names. **Never present
a draft that exits 1.** Fix the draft and re-run.

Then print the cleared text for the developer to paste into Jira themselves. Do not post it.

## Hard rules

1. **Read-only, everywhere.** No Jira comment, no transition, no field edit, no PR, no merge, no
   deploy, no production URL. If a step would write, stop and say what a human needs to do.
2. **Never transition to Done**, and never transition anything at all. Only the product owner sets
   Done, and moving a ticket into To Be Checked belongs to `Johny-Receipt`.
3. **Never fix the work.** Not the Simedia code, tests, docs or config, and not this tooling. A defect
   you notice is a line in the report.
4. **Never touch a ticket assigned to somebody else.**
5. **A missing branch, a missing PR, or a spec not named after the key is never on its own a finding.**
   Run the feature search first. Only `NOT_FOUND_AFTER_5_SEARCHES`, with its command and raw output,
   may back an absence claim.
6. **Never claim a receipt or a doc is missing off a single title search.** Two title conventions
   exist; search both, and ship the command with the claim.
7. Never print a token value.

## Related

- The bar itself, and the receipt rules: `knowledge/handover-bar.md` (generated, do not hand-edit).
- The delivery gate that links the receipt and moves the ticket: `Johny-Receipt`.
- The reviewer-side loop this pre-flight anticipates: `Johny-Pm`.
- Distribution to a developer machine: `bundle.sh`, and `README-dev.md` for setup.
