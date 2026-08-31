#!/usr/bin/env bash
# find-by-feature.sh - locate a ticket's implementation on origin/dev WITHOUT trusting the branch name.
#
# The team puts several tickets on ONE branch, so a ticket key is NOT a reliable handle:
#   SD-5333 rode branch SD-5332-5333-projected-column, its spec is named ...-sd5332.cy.ts
#   SD-5175 rode commits marked [SD-5120][SD-5175], its spec is named ...-sd4855.cy.ts
# A key-based filename grep returns zero for both. That zero is a FALSE zero.
#
# Runs five labelled searches so a real zero is always visibly a zero from a NAMED command,
# then prints one verdict:
#   FOUND_VIA_KEY               - the key itself resolves the work
#   FOUND_VIA_FEATURE           - work exists but only the feature/sibling key finds it
#   NOT_FOUND_AFTER_5_SEARCHES  - the ONLY verdict that may back an absence claim
#
# Read-only. Never fetches, never writes, never checks out. Fetch dev yourself first.
#
# Usage: find-by-feature.sh <repo-path> <SD-KEY> [feature terms ...]
#   find-by-feature.sh $SIMEDIA_ROOT/admin-frontend SD-5333 "projected column" "personnel cost"
set -uo pipefail

repo="${1:?usage: find-by-feature.sh <repo-path> <SD-KEY> [feature terms ...]}"
key="${2:?usage: find-by-feature.sh <repo-path> <SD-KEY> [feature terms ...]}"
shift 2
terms=("$@")

[ -d "$repo/.git" ] || { echo "ERROR: $repo is not a git repo"; exit 2; }
git -C "$repo" rev-parse --verify -q origin/dev >/dev/null || {
  echo "ERROR: origin/dev missing in $repo (fetch it first)"; exit 2; }

digits="${key#SD-}"
digits="${digits#sd-}"
# Test/spec path classifier. Cypress-only patterns under-reported coverage on every other stack and
# produced false "no regression tests added" verdicts (2026-08-15: missed 20 pytest files in
# chat-service and 4 xUnit files in asaservice-consumer across SD-5557/5580/5581).
#   (^|/)tests?/       repo-relative dirs, not just /tests/ — `tests/unit/x.py`, `Foo.Tests/Unit/Y.cs`
#   (^|/)test_         pytest prefix convention — `test_revenue_forecast_card.py`
#   tests?\.(cs|...)$  xUnit/JUnit suffix convention — `RoomNightBilledWindowTests.cs`
# Matched case-insensitively (callers use grep -iE).
TEST_RX='cypress|\.cy\.|\.spec\.|\.test\.|_test\.|(^|/)tests?/|(^|/)test_|tests?\.(cs|java|kt|scala)$|_test\.go$'

found_key=0     # key itself resolved something
found_feat=0    # only feature/sibling resolved something
sib=""
shas=""

hr() { printf '\n--- %s\n' "$1"; }
indent() { local p="$1"; while IFS= read -r l; do printf '%s%s\n' "$p" "$l"; done; }

echo "=== find-by-feature: $key in $(basename "$repo") on origin/dev ==="
if [ ${#terms[@]} -gt 0 ]; then echo "feature terms: ${terms[*]}"; else
  echo "feature terms: (none given - searches 3 and 5 will be skipped, so a zero here is WEAK)"; fi

# ---------------------------------------------------------------- 1. remote branch by key
hr "SEARCH 1  remote branch matching '$digits'"
echo "\$ git -C <repo> ls-remote --heads origin | grep -i $digits"
b=$(GIT_SSH_COMMAND="ssh -4" git -C "$repo" ls-remote --heads origin 2>/dev/null | grep -i "$digits")
if [ -n "$b" ]; then echo "$b"; found_key=1
else echo "(no live branch - expected when the branch was merged and deleted, NOT evidence of absence)"; fi

# ---------------------------------------------------------------- 2. commit messages by key
hr "SEARCH 2  commit messages (subject AND body) mentioning $key"
echo "\$ git -C <repo> log origin/dev --format='%h %s' --grep=$key -i"
c=$(git -C "$repo" log origin/dev --format='%h %s' --grep="$key" -i)
if [ -n "$c" ]; then
  echo "$c"; found_key=1
  shas=$(git -C "$repo" log origin/dev --format='%H' --grep="$key" -i)
  sib=$(git -C "$repo" log origin/dev --format='%s%n%b' --grep="$key" -i \
        | grep -oiE 'SD-[0-9]{3,5}' | tr '[:lower:]' '[:upper:]' | sort -u | grep -v "^${key}$" | tr '\n' ' ')
  [ -n "$sib" ] && echo ">> SHARED BRANCH: these commits also carry $sib - a spec or file may be named after a SIBLING key, not $key"
else echo "(no commit mentions $key)"; fi

# ---------------------------------------------------------------- 3. commit messages by feature
hr "SEARCH 3  commit messages by FEATURE term (catches a ticket the commit never names)"
if [ ${#terms[@]} -eq 0 ]; then echo "(skipped - no feature terms given)"; else
  for t in "${terms[@]}"; do
    echo "\$ git -C <repo> log origin/dev --format='%h %s' --grep='$t' -i"
    r=$(git -C "$repo" log origin/dev --format='%h %s' --grep="$t" -i | head -15)
    if [ -n "$r" ]; then echo "$r"; [ "$found_key" -eq 0 ] && found_feat=1
    else echo "(none)"; fi
  done
fi

# ---------------------------------------------------------------- 4. files the commits touched
hr "SEARCH 4  files touched by those commits, split code vs test (the strongest link)"
if [ -z "$shas" ]; then echo "(no commits from search 2 to inspect)"; else
  all=$(while IFS= read -r s; do [ -n "$s" ] && git -C "$repo" show --name-only --format='' "$s"; done <<<"$shas" | sort -u | sed '/^$/d')
  echo "CODE:"; echo "$all" | grep -viE "$TEST_RX" | indent "  " || true
  echo "TEST/SPEC:"
  t=$(echo "$all" | grep -iE "$TEST_RX")
  if [ -n "$t" ]; then
    echo "$t" | indent "  "
    echo "$t" | grep -qi "$digits" \
      && echo ">> spec is named after $key" \
      || echo ">> NOTE: spec does NOT contain '$digits' - this is the false-zero case; a filename grep for $key would MISS it"
  else echo "  (none - the commits touched no test file; the 'regression tests added' DoD line is likely UNMET)"; fi
fi

# ---------------------------------------------------------------- 5. content search by feature
hr "SEARCH 5  tracked-file content by FEATURE term (finds specs named after another ticket)"
if [ ${#terms[@]} -eq 0 ]; then echo "(skipped - no feature terms given)"; else
  for t in "${terms[@]}"; do
    echo "\$ git -C <repo> grep -il '$t' origin/dev"
    r=$(git -C "$repo" grep -il "$t" origin/dev -- 2>/dev/null | cut -d: -f2- | head -25)
    if [ -n "$r" ]; then
      echo "$r" | indent "  "
      s=$(echo "$r" | grep -iE "$TEST_RX")
      [ -n "$s" ] && { echo "  >> test/spec hits: "; echo "$s" | indent "     "; [ "$found_key" -eq 0 ] && found_feat=1; }
    else echo "  (none)"; fi
  done
fi

# ---------------------------------------------------------------- verdict
echo
if   [ "$found_key" -eq 1 ]; then v="FOUND_VIA_KEY"
elif [ "$found_feat" -eq 1 ]; then v="FOUND_VIA_FEATURE"
else v="NOT_FOUND_AFTER_5_SEARCHES"; fi

echo "=== VERDICT: $v ==="
case "$v" in
  FOUND_VIA_KEY)
    echo "The key resolves the work. Verify each DoD item against the files above."
    [ -n "$sib" ] && echo "Shared branch with $sib - check the DoD against files named for the SIBLING key too." ;;
  FOUND_VIA_FEATURE)
    echo "The key resolves NOTHING but the feature does. Name the carrying branch/sibling in the Jira comment."
    echo "Do NOT claim the work is missing." ;;
  NOT_FOUND_AFTER_5_SEARCHES)
    if [ ${#terms[@]} -eq 0 ]; then
      echo "WEAK zero: no feature terms were given, so searches 3 and 5 never ran."
      echo "Re-run with feature terms from the ticket summary BEFORE any absence claim."
    else
      echo "This is the ONLY verdict that may back an absence claim."
      echo "Copy the exact commands + output above into <draft>.evidence as:  $key :: <cmd> :: <output|EMPTY>"
      echo "then let absence-claim-guard.py gate the comment."
    fi ;;
esac
