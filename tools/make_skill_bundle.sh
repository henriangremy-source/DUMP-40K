#!/bin/bash
# Build a wh40k skill package with the rules database baked in, ready to upload
# to claude.ai.
#
# Why: the skill syncs arbitrary bundled files into every session, but its data/
# directory was uploaded empty. Putting the database inside the package makes the
# skill work everywhere -- plain claude.ai chats included -- with no hook, no
# network fetch and no repo.
#
# Usage:
#   tools/make_skill_bundle.sh /path/to/dump_vXXX.json [output_dir]
#
# Produces <output_dir>/wh40k.zip. Upload that at claude.ai -> Settings -> Skills,
# replacing the existing wh40k skill.
#
# Only copies data in; it never rewrites your skill's code.

set -euo pipefail

DUMP="${1:-}"
OUTDIR="${2:-$PWD/build}"

if [ -z "$DUMP" ] || [ ! -f "$DUMP" ]; then
  echo "Usage: $0 /path/to/dump_vXXX.json [output_dir]" >&2
  echo "Error: dump JSON not found: ${DUMP:-<none given>}" >&2
  exit 1
fi

SKILL="${WH40K_SKILL_DIR:-$HOME/.claude/skills/wh40k}"
if [ ! -f "$SKILL/scripts/build_db.py" ]; then
  echo "Error: wh40k skill not found at $SKILL" >&2
  echo "Set WH40K_SKILL_DIR to its location and retry." >&2
  exit 1
fi

command -v zip >/dev/null 2>&1 || { echo "Error: 'zip' is not installed." >&2; exit 1; }

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

# The zip must contain the skill directory as its single top-level entry, and
# that directory name must match the 'name' in SKILL.md frontmatter.
echo "Staging skill from $SKILL ..."
cp -R "$SKILL" "$STAGE/wh40k"
rm -rf "$STAGE/wh40k/data"
mkdir -p "$STAGE/wh40k/data"

echo "Building database from $(basename "$DUMP") ..."
python3 "$SKILL/scripts/build_db.py" "$DUMP" "$STAGE/wh40k/data/wh40k_rules.db"

DB_MB=$(( $(stat -c%s "$STAGE/wh40k/data/wh40k_rules.db" 2>/dev/null \
          || stat -f%z "$STAGE/wh40k/data/wh40k_rules.db") / 1048576 ))

mkdir -p "$OUTDIR"
ZIP="$OUTDIR/wh40k.zip"
rm -f "$ZIP"
( cd "$STAGE" && zip -qr "$ZIP" wh40k -x '*.pyc' '*__pycache__*' '*.DS_Store' )

ZIP_MB=$(( $(stat -c%s "$ZIP" 2>/dev/null || stat -f%z "$ZIP") / 1048576 ))

echo
echo "Bundle ready: $ZIP"
echo "  database: ${DB_MB} MB uncompressed"
echo "  zip:      ${ZIP_MB} MB"
echo
echo "Next: claude.ai -> Settings -> Capabilities -> Skills -> replace 'wh40k' with this zip."
echo "Then start a fresh session (any repo, or a plain chat) and ask a rules question."
