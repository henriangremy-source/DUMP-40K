#!/usr/bin/env python3
"""
Build a wh40k skill package with the rules database baked in, ready to upload
to claude.ai.

Cross-platform equivalent of make_skill_bundle.sh -- works on Windows, macOS and
Linux with nothing but Python. No 'zip' binary required.

Usage:
    python tools/make_skill_bundle.py C:\\path\\to\\dump_vXXX.json
    python tools/make_skill_bundle.py /path/to/dump_vXXX.json [output_dir]

Produces <output_dir>/wh40k.zip (default: <repo>/build/wh40k.zip). Upload that at
claude.ai -> Settings -> Capabilities -> Skills, replacing the existing wh40k skill.

Only copies data in; it never rewrites your skill's code.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXCLUDE = {"__pycache__", ".DS_Store", ".gitkeep"}


def die(msg: str) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def find_skill() -> Path:
    override = os.environ.get("WH40K_SKILL_DIR")
    candidates = []
    if override:
        candidates.append(Path(override))
    candidates.append(REPO / "skill")
    candidates.append(Path.home() / ".claude" / "skills" / "wh40k")
    for c in candidates:
        if (c / "scripts" / "build_db.py").is_file():
            return c
    die("wh40k skill source not found. Set WH40K_SKILL_DIR and retry.\n"
        "  Looked in: " + ", ".join(str(c) for c in candidates))


def mb(path: Path) -> float:
    return path.stat().st_size / 1_048_576


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        die("no dump JSON given.")

    dump = Path(sys.argv[1]).expanduser()
    if not dump.is_file():
        die(f"dump JSON not found: {dump}")

    outdir = Path(sys.argv[2]).expanduser() if len(sys.argv) > 2 else REPO / "build"
    skill = find_skill()
    print(f"Using skill source: {skill}")

    stage = Path(tempfile.mkdtemp())
    try:
        # The zip must contain the skill directory as its single top-level entry,
        # and that name must match the 'name' in SKILL.md frontmatter.
        pkg = stage / "wh40k"
        shutil.copytree(
            skill, pkg,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", "data"),
        )
        data_dir = pkg / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        db = data_dir / "wh40k_rules.db"

        print(f"Building database from {dump.name} ...")
        proc = subprocess.run(
            [sys.executable, str(skill / "scripts" / "build_db.py"), str(dump), str(db)],
            capture_output=True, text=True,
        )
        if proc.returncode != 0 or not db.is_file():
            sys.stderr.write(proc.stdout)
            sys.stderr.write(proc.stderr)
            die("build_db.py failed -- is that a real Warhammer 40,000 app dump?")

        outdir.mkdir(parents=True, exist_ok=True)
        zip_path = outdir / "wh40k.zip"
        if zip_path.exists():
            zip_path.unlink()

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(pkg.rglob("*")):
                if any(part in EXCLUDE for part in path.parts):
                    continue
                if path.is_file():
                    zf.write(path, path.relative_to(stage).as_posix())

        # Confirm the packaged database actually answers a query.
        import sqlite3
        units = sqlite3.connect(db).execute("SELECT COUNT(*) FROM unit").fetchone()[0]

        print()
        print(f"Bundle ready: {zip_path}")
        print(f"  datasheets: {units}")
        print(f"  database:   {mb(db):.1f} MB uncompressed")
        print(f"  zip:        {mb(zip_path):.1f} MB")
        print()
        if units == 0:
            print("WARNING: the database contains no datasheets. Do not upload this;")
            print("the dump file is probably not a real app export.")
            return
        print("Next: claude.ai -> Settings -> Capabilities -> Skills -> replace 'wh40k'")
        print("with this zip. Then ask a rules question from any chat.")
    finally:
        shutil.rmtree(stage, ignore_errors=True)


if __name__ == "__main__":
    main()
