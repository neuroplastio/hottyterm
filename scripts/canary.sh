#!/bin/sh
# Applies patches/ to upstream Ghostty's latest main in a throwaway worktree
# and says whether they still apply and the branding still finds its anchors.
# Changes nothing else.
#
#   scripts/canary.sh [ref]    # default: origin/main, fetched now
set -eu
HERE="$(cd "$(dirname "$0")/.." && pwd)"
FORK="${HOTTYTERM_GHOSTTY:-$(dirname "$HERE")/ghostty}"
REF="${1:-origin/main}"
git -C "$FORK" fetch -q --depth 200 origin main
TMP="$(mktemp -d)"; trap 'git -C "$FORK" worktree remove --force "$TMP" >/dev/null 2>&1 || true; rm -rf "$TMP"' EXIT
git -C "$FORK" worktree add -q --detach "$TMP" "$REF"
behind=$(git -C "$FORK" rev-list --count "$(grep -v '^#' "$HERE/ghostty-ref" | head -1)..$REF" 2>/dev/null || echo "?")
if git -C "$TMP" am -q --3way "$HERE"/patches/*.patch >/dev/null 2>&1; then
  echo "canary: patches apply to $REF ($(git -C "$TMP" rev-parse --short "$REF"), $behind commit(s) past ghostty-ref)"
  if out=$("$HERE/scripts/brand.py" --dry-run "$TMP" 2>&1); then echo "canary: $out"
  else echo "canary: BRANDING needs a rule update on $REF:"; echo "$out" | sed 's/^/  /'; exit 1; fi
else
  echo "canary: CONFLICT on $REF ($(git -C "$TMP" rev-parse --short "$REF"), $behind commit(s) past ghostty-ref)"
  git -C "$TMP" diff --name-only --diff-filter=U | sed 's/^/  /'
  git -C "$TMP" am --abort >/dev/null 2>&1 || true
  exit 1
fi
