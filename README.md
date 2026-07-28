# DUMP-40K

Carries the Warhammer 40,000 app data export so the `wh40k` skill works in any
Claude Code session started against this repo — including from a phone.

## The problem this solves

The `wh40k` skill syncs from claude.ai into every session, but only its code:
`SKILL.md`, `scripts/query.py`, `scripts/build_db.py`, `references/`. Its `data/`
directory arrives **empty** — the ~35 MB app dump is not part of the skill package.

So on a fresh session the skill loads and then every lookup fails:

```
Database not found: ~/.claude/skills/wh40k/data/wh40k_rules.db
Run build_db.py first: ...
```

This repo holds the data, and a `SessionStart` hook installs it into the skill's
`data/` directory before the session starts. Start a session against DUMP-40K and
rules lookups just work — nothing to upload, nothing to build by hand.

## Setup (one time, from a computer)

The dump has to be added from a machine that has the file — you can't upload
35 MB from a phone. Pick one option:

### Option A — prebuilt + gzipped (recommended, fastest startup)

```bash
git clone <this repo> && cd DUMP-40K
python3 ~/.claude/skills/wh40k/scripts/build_db.py /path/to/dump_vXXX.json data/wh40k_rules.db
gzip data/wh40k_rules.db          # leaves data/wh40k_rules.db.gz
git add data/wh40k_rules.db.gz && git commit -m "Add wh40k rules database" && git push
```

Session startup cost: ~1–2 s to decompress.

### Option B — raw dump

```bash
cp /path/to/dump_vXXX.json data/
git add data/dump_vXXX.json && git commit -m "Add wh40k dump vXXX" && git push
```

Session startup cost: ~30 s, the database is rebuilt each new session.

The hook picks the first source it finds, in this order:

| File in `data/` | How it's installed | Startup cost |
|---|---|---|
| `wh40k_rules.db.gz` | decompressed | ~1–2 s |
| `wh40k_rules.db` | symlinked (no copy) | instant |
| `dump_v*.json` | built via `build_db.py` | ~30 s |

If several are present the table order decides. With none present the hook prints
instructions and exits cleanly — it never blocks a session from starting.

## Updating to a new dump version

Rebuild and replace the file, then commit. Each version is a full binary blob in
git history, so prefer replacing `data/wh40k_rules.db.gz` over accumulating one
`dump_vXXX.json` per release.

## Verifying without the real dump

`tests/make_fixture.py` writes a small synthetic dump with the same shape as the
real export, so the pipeline can be exercised on its own:

```bash
python3 tests/make_fixture.py data/dump_v999.json
CLAUDE_PROJECT_DIR="$PWD" ./.claude/hooks/session-start.sh
python3 ~/.claude/skills/wh40k/scripts/query.py unit "Test Intercessor"
rm data/dump_v999.json                     # don't commit the fixture
```

The fixture contains one made-up unit — it is a plumbing check, not real rules
data. Delete it afterwards so the hook doesn't pick it up instead of the real dump.

## Layout

```
.claude/hooks/session-start.sh   installs the database into the synced skill
.claude/settings.json            registers the SessionStart hook
data/                            the dump and/or built database live here
tests/make_fixture.py            synthetic dump for testing the pipeline
```

## A note on the data

The dump is Games Workshop's proprietary app data. This repo is for making your
own copy available to your own sessions — keep it private.
