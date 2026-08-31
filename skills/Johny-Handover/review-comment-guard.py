#!/usr/bin/env python3
"""Hard gate for Simedia review comments.

Blocks a comment that does not explicitly cover all four review layers, plus the
pre-existing house rules (no em/en dashes, no local paths or internal tooling names).
Also warns when a live UI observation is described but no screenshot is attached.

Usage:
    review-comment-guard.py <comment-file> [--shots DIR]

Exit 0 = safe to post. Exit 1 = blocked, with the reason per block.
A comment file may hold several blocks separated by lines like:  --- SD-1234
"""
import argparse
import os
import re
import sys

LAYERS = {
    "e2e": re.compile(r"\b(e2e|cypress|k6|spec|regression test)\b", re.I),
    "implementation": re.compile(r"\b(implementation|commit [0-9a-f]{7}|\.tsx|\.ts\b|\.py\b|\.cs\b|\.scss|merged)\b", re.I),
    "doc": re.compile(r"\b(doc|documented|documentation|confluence|receipt|root cause)\b", re.I),
    "live": re.compile(r"\b(live|deployed|on the deployed|in the browser|cluster)\b", re.I),
}
BAD_DASH = re.compile(r"[—–]")
LEAK = re.compile(r"/home/[a-z]+|/tmp/|\bclaude\b|\bjohny\b|\bsubagent\b|ATATT|playwright", re.I)
UI_OBSERVED = re.compile(r"\b(rendered|renders|on the page|in the browser|screen|placeholder|column|label|tab|drawer|button)\b", re.I)
SHOT_REF = re.compile(r"\b(screenshot|attached|attachment)\b", re.I)
# Explicit, reader-visible opt-out for tickets with nothing to photograph.
NO_UI_SURFACE = re.compile(
    r"no user-visible surface|not user visible|backend only|no ui surface|"
    r"documentation change|infrastructure only|no visible change", re.I)


def blocks(text):
    parts = re.split(r"^--- (SD-\d+).*$", text, flags=re.M)
    if len(parts) == 1:
        return [("(single)", text.strip())]
    return [(parts[i], parts[i + 1].strip()) for i in range(1, len(parts), 2)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--shots", default=None, help="directory of screenshots, to check availability")
    a = ap.parse_args()

    text = open(a.path, encoding="utf-8").read()
    failed = False

    for key, body in blocks(text):
        problems, warnings = [], []

        missing = [name for name, rx in LAYERS.items() if not rx.search(body)]
        if missing:
            problems.append("missing review layer(s): " + ", ".join(missing))

        if BAD_DASH.search(body):
            problems.append("contains an em or en dash")

        leaks = sorted(set(m.group(0).lower() for m in LEAK.finditer(body)))
        if leaks:
            problems.append("contains a local path or internal name: " + ", ".join(leaks))

        # Live check + screenshot is mandatory for anything with a user-visible surface (Paul,
        # 2026-07-30). This was a warning until a UI verdict shipped on SD-5313 with no image, so it
        # is now a BLOCK. Backend-only tickets opt out by SAYING SO in the comment, which keeps the
        # reader informed instead of silently skipping the evidence.
        if UI_OBSERVED.search(body) and not SHOT_REF.search(body):
            if NO_UI_SURFACE.search(body):
                warnings.append("UI wording present but declared backend only, screenshot waived")
            else:
                problems.append("describes a UI observation with no screenshot. Capture one and "
                                "attach it, or state plainly that the ticket has no user-visible "
                                "surface")

        status = "BLOCK" if problems else "ok   "
        print(f"  {status} {key}  ({len(body)} chars)")
        for p in problems:
            print(f"        ! {p}")
            failed = True
        for w in warnings:
            print(f"        ~ {w}")

    if a.shots and os.path.isdir(a.shots):
        n = len([f for f in os.listdir(a.shots) if f.lower().endswith((".png", ".jpg"))])
        print(f"  screenshots available in {a.shots}: {n}")

    if failed:
        print("\nBLOCKED. Fix the above before posting.")
        return 1
    print("\nAll blocks pass the gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
