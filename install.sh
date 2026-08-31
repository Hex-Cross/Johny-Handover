#!/usr/bin/env bash
# Install the handover self-check into your own Claude Code configuration.
# Re-run it after every `git pull`. It refuses to clobber anything it did not put there.
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"

[ -d "$SRC/skills/Johny-Handover" ] || { echo "run this from inside the cloned repo" >&2; exit 2; }
mkdir -p "$DEST/skills" "$DEST/agents"

# Refuse to overwrite a hand-modified copy: compare against the VERSION we last installed.
STAMP="$DEST/skills/Johny-Handover/.installed-version"
if [ -f "$STAMP" ] && [ -d "$DEST/skills/Johny-Handover" ]; then
  if ! diff -rq "$SRC/skills/Johny-Handover" "$DEST/skills/Johny-Handover" \
       --exclude=.installed-version >/dev/null 2>&1; then
    echo "Your installed copy differs from this clone."
    echo "If you edited it, save your changes first. To overwrite: rm -rf $DEST/skills/Johny-Handover"
    exit 3
  fi
fi

rm -rf "$DEST/skills/Johny-Handover"
cp -r "$SRC/skills/Johny-Handover" "$DEST/skills/"
cp    "$SRC/agents/Johny-Handover-Verifier.md" "$DEST/agents/"
cp    "$SRC/VERSION" "$STAMP"

echo "installed version $(cat "$SRC/VERSION")"
echo
echo "Set the variables from README.md in your shell profile, then run:  Johny-Handover SD-1234"
