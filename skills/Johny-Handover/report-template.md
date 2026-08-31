# Handover self-check report - template

The key block is parsed. Keep the key names, their order and their spelling exactly as below, even
when a value is unknown: write the reason instead of dropping the line. Prose goes after the block,
never inside it.

## Key block

```
TICKET: SD-XXXX
REPO: <repo name, or "no code repo">
ASSIGNEE: <display name>
READY: YES | NO (<n> on you, <n> on the product owner)
DOD SOURCE: ticket description | NONE (ticket has no DoD)
CHECKLIST
  [x] <item text>  --  <evidence: file:line, git ref, commit sha, or Confluence page id>
  [ ] <item text>  --  <what is absent, and the command whose empty output proves it>
      FIX: YOU -- <the smallest action that closes this>
  [ ] <item text>  --  <what is absent>
      FIX: TOOLING -- <what to ask the project tooling for>
  [ ] <item text>  --  <what is absent>
      FIX: PO -- <what to ask the product owner for>
BRANCH/PR: <branch name, or "no live branch"> -- <PR#<id> <STATE> | NO_PR>
SEARCH: FOUND_VIA_KEY | FOUND_VIA_FEATURE | NOT_FOUND_AFTER_5_SEARCHES -- <carrying branch or sibling key, or the commands run>
MERGED-TO-DEV: yes | no -- <reason, naming the fetch that backs it>
TESTS: <framework and the spec files that assert the change, or "absent" with the search that proves it>
DOC: linked <page id> | exists but NOT linked <page id> | none found | n/a (not in DoD)
RECEIPT: linked <page id> | exists but NOT linked <page id> | owed (trigger <1-5>) | n/a (not in DoD)
LIVE: NOT-CHECKED (self-check does not drive the application)
ON YOU: <n>   ON TOOLING: <n>
```

`READY: YES` requires every `FIX: YOU` item closed. `FIX: TOOLING` items are listed, counted, and
excluded from readiness.

## Prose section

After the block, in full sentences: what you actually found, the mechanism rather than the outcome,
and every lane that could not run said out loud. Close with a named caveat stating what is not safe
to hand in yet and why. If there genuinely is nothing, write "No caveat:" and one clause saying why.

No em or en dashes. No local filesystem paths. No internal tooling names.

## Paste-ready handover comment

```
--- PASTE-READY HANDOVER COMMENT (guard exit 0) ---
What ran: <spec / regression test / load test, and its result>
What changed: <the change reference, the files, and whether it is merged to dev>
Documentation: <receipt or Confluence page, and the root cause in one line>
Live: <what was seen on the deployed system, or "no user-visible surface">
```

All four layers are mandatory. `review-comment-guard.py` refuses a draft missing any of them, and a
comment describing something rendered on screen with no screenshot attached is refused as well. A
ticket with nothing to photograph must say `no user-visible surface` in plain words, so the exemption
is visible to the reviewer rather than silent.
