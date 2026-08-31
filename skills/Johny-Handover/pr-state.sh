#!/usr/bin/env bash
# pr-state.sh — READ-ONLY Bitbucket pull-request state for a branch. Requires VPN + IPv4.
# Env: BITBUCKET_EMAIL / BITBUCKET_API_TOKEN / BITBUCKET_WORKSPACE (set them in your shell profile).
# Usage: pr-state.sh <repo> <branch>
# Output: "<repo> <branch>: NO_PR"  OR one line per PR: "PR#<id> <STATE> — <title> — <url>"
set -euo pipefail

repo="${1:?usage: pr-state.sh <repo> <branch>}"
branch="${2:?usage: pr-state.sh <repo> <branch>}"
BITBUCKET_EMAIL="${BITBUCKET_EMAIL:?set BITBUCKET_EMAIL}"
: "${BITBUCKET_API_TOKEN:?set BITBUCKET_API_TOKEN (set it in your shell profile)}"
ws="${BITBUCKET_WORKSPACE:-simedia-data}"

base="https://api.bitbucket.org/2.0/repositories/$ws/$repo/pullrequests"
# URL-encode the BBQL filter: source.branch.name="<branch>"
q=$(python3 -c 'import urllib.parse,sys; print(urllib.parse.quote(f"source.branch.name=\"{sys.argv[1]}\""))' "$branch")
fields="values.id,values.state,values.title,values.links.html.href"

resp=$(curl -4 -s -w $'\n%{http_code}' -u "$BITBUCKET_EMAIL:$BITBUCKET_API_TOKEN" \
  "$base?q=$q&pagelen=10&fields=$fields")
http="${resp##*$'\n'}"
body="${resp%$'\n'*}"

if [ "$http" != "200" ]; then
  echo "ERROR http=$http (VPN up? IPv4? repo=$repo) — $(printf '%s' "$body" | head -c 200)" >&2
  exit 4
fi

n=$(printf '%s' "$body" | jq '.values | length')
if [ "$n" = "0" ]; then
  echo "$repo $branch: NO_PR"
  exit 0
fi
printf '%s' "$body" | jq -r --arg r "$repo" --arg b "$branch" \
  '.values[] | "\($r) \($b): PR#\(.id) \(.state) — \(.title) — \(.links.html.href)"'
