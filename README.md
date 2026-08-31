# Handover self-check - setup, one page

Run this on your own ticket before you move it to To Be Checked. It tells you which Definition-of-Done
items are still unmet, and it writes you a handover comment that already passes the review checks.

It reads. It never writes. No comment, no status change, no pull request, no deploy.

## Install

```
git clone https://github.com/Hex-Cross/handover-selfcheck.git
cd handover-selfcheck
./install.sh
```

To update later, whenever the review rules change:

```
git pull && ./install.sh
```

## Set the variables

Seven are required, one is optional. Put them in your shell profile. Nothing is stored by the tool and no value is ever printed.

| Variable | What it is |
|---|---|
| `SIMEDIA_ROOT` | the directory holding your Simedia repository checkouts |
| `JIRA_SITE` | `simedia-data.atlassian.net` |
| `JIRA_EMAIL` | your Atlassian account email |
| `JIRA_API_TOKEN` | an Atlassian API token, read scope is enough |
| `BITBUCKET_WORKSPACE` | `simedia-data` |
| `BITBUCKET_EMAIL` | your Bitbucket account email |
| `BITBUCKET_API_TOKEN` | a Bitbucket API token, read scope is enough |
| `PO_ACCOUNT_ID` | optional. The product owner's Atlassian account id. Without it the report still works, but it cannot single out the product owner's comments, and those are usually the ones that decide the ticket. Ask your lead for the value. |

Bitbucket only answers over IPv4 here, so the tool forces that on every call. If a Bitbucket lane
fails, check the connection before you suspect the token.

## Run it

```
self-check SD-1234
```

Other phrasings that start it: "what is missing on SD-1234", "check my implementation",
"pre-flight SD-1234", "am I ready to hand this in".

You get one report. Every unmet item is tagged:

- **FIX: YOU** - you can close it. Push the spec, merge the branch, write the receipt page.
- **FIX: TOOLING** - you cannot close it from your side, and it is not held against you. Today the
  only real case is turning a Confluence page into a link that shows up in the Jira panel: your API
  call lands without the Confluence application marker, so the panel stays empty however many times
  you try. Ask for the link and carry on.

`READY: YES` counts only the FIX: YOU items.

At the end you get a four-layer handover comment to paste into the ticket yourself: what ran, what
changed, where the documentation is, and what was seen live. It has already been checked for the
things a reviewer sends tickets back for.

## What it will not tell you

- **It does not drive the application.** Every report says `LIVE: NOT-CHECKED`. If your change is
  user-visible, open it on dev yourself and attach a screenshot. A reviewer cannot approve a visible
  change with no picture of it.
- **It cannot link a Confluence page for you**, and it cannot approve or move anything.
- **It will not invent a checklist.** About half the tickets on the board have no Definition of Done
  section (48 of 60 measured on 2026-08-28). When yours does not, the report says
  `DOD SOURCE: NONE` and `READY: NO` with a single `FIX: PO` item. It deliberately does not judge you
  against a bar we made up, because passing an invented bar does not stop the reviewer rejecting the
  ticket. This is not your gap to close. Ask the product owner for a Definition of Done.
- **A `WILL LIKELY BOUNCE: yes` line is a warning, not a fault.** It appears when no commit in any
  repository carries your change. The reviewer has rejected on that even where the ticket asked for
  no code, so you are being told what is coming, not what you did wrong.
- **It is not the review.** It anticipates it. A clean report makes a fast review much more likely; it
  does not promise one.

## If a lane cannot run

The report ends with `LANES NOT RUN` naming the lane and the missing variable or connection. That line
is the answer, not an error to work around. Fix the variable and run it again.
