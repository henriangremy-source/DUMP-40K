# DUMP-40K

Carries the Warhammer 40,000 app data export so the `wh40k` skill works in any
Claude Code session started against this repo — including from a phone.

## Start here

Do this once on a computer, and the phone never has to do anything again:

```bash
git clone https://github.com/henriangremy-source/DUMP-40K && cd DUMP-40K
python tools/make_skill_bundle.py /path/to/dump_vXXX.json
```

On Windows, in PowerShell:

```powershell
python tools\make_skill_bundle.py C:\path\to\dump_vXXX.json
```

(`tools/make_skill_bundle.sh` is the same thing for people who prefer bash, but it
needs a `zip` binary that Windows doesn't ship — use the Python version there.)

Then upload the resulting `build/wh40k.zip` at **claude.ai → Settings →
Capabilities → Skills**, replacing `wh40k`. The skill now carries its own data
into every session — phone chats included — with nothing to run or start.

No local Claude Code install is needed; the skill source is vendored in `skill/`.

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

## Two ways to fix it — pick based on where you need the skill

**Skills sync arbitrary bundled files, not just code.** `data/.gitkeep` and
`references/rules_index.md` both arrive in every session, so nothing strips the
data directory — the database is simply missing from the uploaded package. That
means the best fix is at the source.

| | Database bundled in the skill | This repo + `SessionStart` hook |
|---|---|---|
| Plain claude.ai chat (phone) | ✅ | ❌ no hook mechanism exists |
| Claude Code, any repo | ✅ | ❌ only sessions on DUMP-40K |
| Claude Code on DUMP-40K | ✅ | ✅ |
| Startup cost | none | 1–2 s, or ~30 s from raw JSON |
| Re-upload needed per dump version | yes | no, just `git push` |

Bundling covers every case; the hook only covers sessions started against this
repo. Use bundling as the primary fix and keep the hook as the fallback for
whenever the skill is out of date relative to a fresh dump.

## Bundling the database into the skill (fixes every session)

From a computer that has the dump:

```bash
tools/make_skill_bundle.sh /path/to/dump_vXXX.json
```

> **`build/wh40k.zip` is generated on your machine — it is not in this repo and
> never will be.** Building it requires the dump, which isn't committed here. The
> repo holds the recipe; you run it to produce the zip.

This stages the synced skill, builds the database into its `data/` directory, and
writes `build/wh40k.zip` with `wh40k/` as the single top-level entry (required for
upload). It copies data in only — it never rewrites the skill's code.

Then: **claude.ai → Settings → Capabilities → Skills → replace `wh40k` with the
zip.** Start any fresh session and rules lookups work with no further setup.

Check the reported zip size before uploading. A few tens of MB is fine; if it is
unexpectedly large, fall back to the repo + hook approach below.

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

## Event charts

`tools/bcp_disposition_chart.py` draws the Force Disposition split by faction for
a Best Coast Pairings event — one stacked bar per faction, sorted by headcount:

```bash
python3 tools/bcp_disposition_chart.py ChZP41nemm16
```

The event id is the last path segment of the BCP event URL. It writes a PNG and
a CSV of the same counts into `build/`. Needs `matplotlib`; nothing else in this
repo does, so install it only if you want the charts.

Players who have not yet picked a faction or a disposition are left out, and the
script reports how many that was — registration is usually still open right up to
the event, so the numbers move.

Set apart from the ranking by a divider sits a combined **All Space Marines** row:
Codex Space Marines plus its supplements (Dark Angels, Blood Angels, Space Wolves,
Black Templars, Deathwatch). It re-counts players already shown in the ranking, so
it never joins the sort. Grey Knights are left out of it — Astartes, but their own
codex and army rule. Edit `MARINE_CHAPTERS` to draw that line differently.

`--marine-total top|bottom|none` moves that row above the ranking, below it
(default), or drops it. Anything other than the default gets its own file name, so
the variants sit side by side instead of overwriting each other.

## Layout

```
.claude/hooks/session-start.sh   installs the database into the synced skill
.claude/settings.json            registers the SessionStart hook
data/                            the dump and/or built database live here
skill/                           vendored wh40k skill source (SKILL.md, scripts)
tools/make_skill_bundle.sh       builds an uploadable skill zip with data baked in
tools/bcp_disposition_chart.py   disposition-by-faction chart for a BCP event
tests/make_fixture.py            synthetic dump for testing the pipeline
```

`skill/` is a copy of the skill as it syncs from claude.ai, so the bundle script
runs on any machine. If you edit the skill on claude.ai, refresh this copy.

## A note on the data

The dump is Games Workshop's proprietary app data. This repo is for making your
own copy available to your own sessions — keep it private.
