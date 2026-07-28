#!/bin/bash
# SessionStart hook: make the wh40k skill's rules database available in this session.
#
# The wh40k skill syncs from claude.ai with its scripts and SKILL.md, but its
# data/ directory arrives empty -- the ~35 MB app dump is not part of the skill
# package. Without a database every query.py call exits with "Database not found".
#
# This hook wires data carried in *this repo* into the skill's data directory,
# so any session started against DUMP-40K has a working skill.
#
# Source precedence (first match wins):
#   1. data/wh40k_rules.db.gz   -- prebuilt, compressed (recommended: fastest)
#   2. data/wh40k_rules.db      -- prebuilt, uncompressed (symlinked, no copy)
#   3. data/dump_v*.json        -- raw app export, built on the fly (~30s)
#
# Never fails the session: if no data is present it prints instructions and exits 0.

set -euo pipefail

REPO="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

# --- Locate the synced wh40k skill ------------------------------------------
SKILL="${HOME}/.claude/skills/wh40k"
if [ ! -d "$SKILL" ]; then
  SKILL="$(find "${HOME}/.claude" -maxdepth 4 -type d -name wh40k 2>/dev/null | head -1 || true)"
fi
if [ -z "$SKILL" ] || [ ! -f "$SKILL/scripts/query.py" ]; then
  echo "wh40k skill not found in this session -- skipping database setup."
  exit 0
fi

TARGET="$SKILL/data/wh40k_rules.db"
mkdir -p "$SKILL/data"

# --- Pick the newest available source ---------------------------------------
GZ="$REPO/data/wh40k_rules.db.gz"
DB="$REPO/data/wh40k_rules.db"
JSON="$(ls -1t "$REPO"/data/dump_v*.json 2>/dev/null | head -1 || true)"

if [ -f "$GZ" ]; then
  SRC="$GZ"
elif [ -f "$DB" ]; then
  SRC="$DB"
elif [ -n "$JSON" ]; then
  SRC="$JSON"
else
  echo "wh40k: no rules data in this repo yet."
  echo "  Add ONE of the following to DUMP-40K/data/ and commit it:"
  echo "    data/wh40k_rules.db.gz  (prebuilt + gzipped -- recommended)"
  echo "    data/wh40k_rules.db     (prebuilt)"
  echo "    data/dump_vXXX.json     (raw Warhammer 40,000 app export)"
  echo "  Until then, wh40k rules lookups will not work in this session."
  exit 0
fi

# --- Idempotency: skip when the target is already current -------------------
if [ -e "$TARGET" ] && [ ! "$SRC" -nt "$TARGET" ]; then
  echo "wh40k: rules database already current ($(basename "$SRC"))."
  exit 0
fi

# --- Install ----------------------------------------------------------------
case "$SRC" in
  *.db.gz)
    rm -f "$TARGET"
    gunzip -c "$SRC" > "$TARGET"
    ;;
  *.db)
    # Symlink instead of copying -- the repo copy is already on this disk.
    rm -f "$TARGET"
    ln -s "$SRC" "$TARGET"
    ;;
  *.json)
    echo "wh40k: building database from $(basename "$SRC") (~30s)..."
    python3 "$SKILL/scripts/build_db.py" "$SRC" "$TARGET" >/dev/null
    ;;
esac

# --- Verify the database actually answers a query ---------------------------
UNITS="$(python3 - "$TARGET" <<'PY' 2>/dev/null || true
import sqlite3, sys
try:
    con = sqlite3.connect(sys.argv[1])
    print(con.execute("SELECT COUNT(*) FROM unit").fetchone()[0])
except Exception:
    print("")
PY
)"

if [ -z "$UNITS" ] || [ "$UNITS" = "0" ]; then
  echo "wh40k: WARNING -- database installed from $(basename "$SRC") but contains no units."
  exit 0
fi

echo "wh40k: rules database ready ($UNITS datasheets, from $(basename "$SRC")). Rules lookups are available."
