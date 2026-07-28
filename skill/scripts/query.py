#!/usr/bin/env python3
"""
WH40K Rules Query Tool
Queries the local SQLite database built from the Warhammer 40,000 app data.

Usage:
    python query.py unit <name>              — unit stats, abilities, points
    python query.py weapon <name>            — weapon profile(s)
    python query.py stratagem <faction>      — stratagems for a faction/detachment
    python query.py detachment <faction>     — detachments + their rules
    python query.py army-rule <faction>      — faction army rule text
    python query.py enhancement <faction>    — enhancements for a faction/detachment
    python query.py faq <faction|topic>      — FAQ / errata entries
    python query.py keyword <name>           — weapon keyword or core ability definition
    python query.py core-rule <topic>        — core rulebook text by section or title
    python query.py search <term>            — cross-table keyword search

The database is expected at:
    <skill_dir>/data/wh40k_rules.db

Run build_db.py first if the database does not yet exist.
"""
import sqlite3
import sys
from pathlib import Path
from textwrap import fill, indent

# Self-locating: DB lives two levels up from this script → <skill>/data/
SKILL_DIR = Path(__file__).resolve().parent.parent
DB_PATH   = SKILL_DIR / "data" / "wh40k_rules.db"

LIKE = lambda s: f"%{s}%"


def get_db() -> sqlite3.Connection:
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        print(f"Run build_db.py first:  python {SKILL_DIR/'scripts'/'build_db.py'} /path/to/dump_vXXX.json")
        sys.exit(1)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def wrap(text: str, width: int = 80, prefix: str = "") -> str:
    if not text:
        return ""
    lines = []
    for para in text.split("\n"):
        if para.strip():
            lines.append(fill(para, width=width, subsequent_indent=prefix))
        else:
            lines.append("")
    return "\n".join(lines)


def hr(char: str = "─", width: int = 72) -> str:
    return char * width


def cmd_unit(con, name):
    rows = con.execute(
        "SELECT * FROM unit WHERE name LIKE ? ORDER BY name", (LIKE(name),)
    ).fetchall()
    if not rows:
        print(f"No units found matching '{name}'.")
        return
    for u in rows:
        print(hr("═"))
        print(f"UNIT: {u['name']}")
        print(f"Faction: {u['factions'] or '—'}   |   Source: {u['publication'] or '—'}")
        if u['min_points'] is not None:
            pts = (f"{u['min_points']}–{u['max_points']} pts"
                   if u['max_points'] != u['min_points'] else f"{u['min_points']} pts")
            print(f"Points: {pts}")
        if u['base_size']:
            print(f"Base: {u['base_size']}")
        if u['is_legends']:
            print("⚠ LEGENDS (not tournament legal)")
        print()
        stats = con.execute(
            "SELECT * FROM unit_stat WHERE unit_id = ? ORDER BY stat_name", (u['id'],)
        ).fetchall()
        if stats:
            print(hr())
            print(f"{'MODEL':<28} {'M':>4} {'T':>4} {'SV':>4} {'W':>4} {'LD':>4} {'OC':>4} {'INV':>5}")
            print(hr())
            for s in stats:
                print(f"{s['stat_name']:<28} {s['movement']:>4} {s['toughness']:>4} "
                      f"{s['save']:>4} {s['wounds']:>4} {s['leadership']:>4} "
                      f"{s['oc']:>4} {s['invuln'] or '—':>5}")
            print()
        if u['unit_composition']:
            print("UNIT COMPOSITION")
            print(wrap(u['unit_composition']))
            print()
        abilities = con.execute(
            "SELECT * FROM unit_ability WHERE unit_id = ? ORDER BY name", (u['id'],)
        ).fetchall()
        if abilities:
            print("ABILITIES")
            print(hr())
            for ab in abilities:
                flags = []
                if ab['is_aura']:   flags.append("AURA")
                if ab['is_psychic']:flags.append("PSYCHIC")
                tag     = f" [{', '.join(flags)}]" if flags else ""
                ab_type = f" ({ab['ability_type']})" if ab['ability_type'] else ""
                print(f"▸ {ab['name']}{tag}{ab_type}")
                if ab['rules'] and ab['rules'].strip() != "-":
                    print(indent(wrap(ab['rules']), "  "))
                print()
        print()


def cmd_weapon(con, name):
    rows = con.execute(
        "SELECT * FROM weapon WHERE name LIKE ? OR profile_name LIKE ? ORDER BY name, profile_name",
        (LIKE(name), LIKE(name))
    ).fetchall()
    if not rows:
        print(f"No weapons found matching '{name}'.")
        return
    grouped: dict = {}
    for r in rows:
        grouped.setdefault(r['name'] or r['profile_name'], []).append(r)
    for wname, profiles in grouped.items():
        print(hr("═"))
        print(f"WEAPON: {wname}")
        print()
        print(f"{'PROFILE':<26} {'RANGE':>6} {'A':>6} {'SKILL':>6} {'S':>4} {'AP':>4} {'D':>4}  ABILITIES")
        print(hr())
        for p in profiles:
            pname = p['profile_name'] if p['profile_name'] != p['name'] else "—"
            print(f"{pname:<26} {p['range_val']:>6} {p['attacks']:>6} {p['skill'] or '—':>6} "
                  f"{p['strength']:>4} {p['ap']:>4} {p['damage']:>4}  {p['abilities'] or ''}")
        print()


def cmd_stratagem(con, query):
    rows = con.execute(
        "SELECT * FROM stratagem WHERE faction LIKE ? OR detachment_name LIKE ? OR name LIKE ? "
        "ORDER BY faction, detachment_name, name",
        (LIKE(query), LIKE(query), LIKE(query))
    ).fetchall()
    if not rows:
        print(f"No stratagems found for '{query}'.")
        return
    current = None
    for s in rows:
        label = s['detachment_name'] or s['faction'] or "Unknown"
        if label != current:
            print(hr("═"))
            print(f"DETACHMENT: {label}   [{s['faction']}]")
            print(hr())
            current = label
        print(f"\n▸ {s['name']}  [{s['cp_cost']} CP]")
        if s['when_rules']:   print(f"  WHEN:   {s['when_rules']}")
        if s['target_rules']: print(f"  TARGET: {s['target_rules']}")
        if s['effect_rules']: print(f"  EFFECT: {wrap(s['effect_rules'], prefix='          ')}")
        if s['restriction_rules']: print(f"  LIMIT:  {s['restriction_rules']}")
    print()


def cmd_detachment(con, query):
    dets = con.execute(
        "SELECT * FROM detachment WHERE faction LIKE ? OR name LIKE ? ORDER BY faction, name",
        (LIKE(query), LIKE(query))
    ).fetchall()
    if not dets:
        print(f"No detachments found for '{query}'.")
        return
    for det in dets:
        print(hr("═"))
        print(f"DETACHMENT: {det['name']}")
        print(f"Faction: {det['faction']}   |   Source: {det['publication']}")
        if det['points_cost']:
            print(f"Detachment cost: {det['points_cost']} pts")
        print()
        rules = con.execute(
            "SELECT * FROM detachment_rule WHERE detachment_id = ? ORDER BY name", (det['id'],)
        ).fetchall()
        if rules:
            print("DETACHMENT RULES")
            print(hr())
            for dr in rules:
                print(f"\n▸ {dr['name']}")
                if dr['rules']:
                    print(indent(wrap(dr['rules']), "  "))
        print()


def cmd_army_rule(con, query):
    rows = con.execute(
        "SELECT * FROM army_rule WHERE faction LIKE ? OR name LIKE ? OR publication LIKE ? "
        "ORDER BY faction, name",
        (LIKE(query), LIKE(query), LIKE(query))
    ).fetchall()
    if not rows:
        print(f"No army rules found for '{query}'.")
        return
    for ar in rows:
        print(hr("═"))
        print(f"ARMY RULE: {ar['name']}")
        print(f"Faction: {ar['faction']}   |   Source: {ar['publication']}")
        print()
        if ar['rules']:
            print(wrap(ar['rules']))
        print()


def cmd_enhancement(con, query):
    rows = con.execute(
        "SELECT * FROM enhancement WHERE faction LIKE ? OR detachment_name LIKE ? OR name LIKE ? "
        "ORDER BY faction, detachment_name, points",
        (LIKE(query), LIKE(query), LIKE(query))
    ).fetchall()
    if not rows:
        print(f"No enhancements found for '{query}'.")
        return
    current = None
    for e in rows:
        label = e['detachment_name'] or e['faction'] or "Unknown"
        if label != current:
            print(hr("═"))
            print(f"DETACHMENT: {label}   [{e['faction']}]")
            print(hr())
            current = label
        pts = f"{e['points']} pts" if e['points'] else ""
        print(f"\n▸ {e['name']}  {pts}")
        if e['rules']:
            print(indent(wrap(e['rules']), "  "))
    print()


def cmd_faq(con, query):
    rows = con.execute(
        "SELECT * FROM faq WHERE faction LIKE ? OR publication LIKE ? "
        "OR header LIKE ? OR body LIKE ? ORDER BY publication, header",
        (LIKE(query), LIKE(query), LIKE(query), LIKE(query))
    ).fetchall()
    if not rows:
        print(f"No FAQ/errata found for '{query}'.")
        return
    current = None
    for fq in rows:
        pub = fq['publication'] or "Unknown"
        if pub != current:
            print(hr("═"))
            print(f"SOURCE: {pub}   [{fq['faction']}]")
            print(hr())
            current = pub
        print(f"\n▸ {fq['header']}")
        if fq['body']:     print(indent(wrap(fq['body']), "  "))
        if fq['question']: print(f"  Q: {fq['question']}")
        if fq['answer']:   print(f"  A: {wrap(fq['answer'], prefix='     ')}")
    print()


def cmd_keyword(con, query):
    rows = con.execute(
        "SELECT * FROM keyword WHERE name LIKE ? ORDER BY keyword_type, name",
        (LIKE(query),)
    ).fetchall()
    if not rows:
        print(f"No keyword definitions found for '{query}'.")
        return
    for kw in rows:
        print(hr("═"))
        ktype = {"weapon": "WEAPON KEYWORD", "core_ability": "CORE ABILITY"}.get(
            kw['keyword_type'], kw['keyword_type'].upper())
        print(f"{ktype}: {kw['name']}")
        print()
        if kw['rules']:
            print(wrap(kw['rules']))
        print()


def cmd_core_rule(con, query):
    rows = con.execute(
        "SELECT * FROM core_rule WHERE section LIKE ? OR title LIKE ? OR rules LIKE ? "
        "ORDER BY section, display_order",
        (LIKE(query), LIKE(query), LIKE(query))
    ).fetchall()
    if not rows:
        print(f"No core rules found matching '{query}'.")
        return
    current = None
    for cr in rows:
        if cr['section'] != current:
            print(hr("═"))
            print(f"SECTION: {cr['section']}")
            print(hr())
            current = cr['section']
        if cr['title']:
            sub = f"  [{cr['subtitle']}]" if cr['subtitle'] else ""
            print(f"\n▸ {cr['title']}{sub}")
        if cr['rules']:
            print(indent(wrap(cr['rules']), "  "))
    print()


def cmd_search(con, term):
    print(f"Searching for '{term}' …\n")
    for label, sql, cols in [
        ("UNITS",        "SELECT name, factions, publication FROM unit WHERE name LIKE ? LIMIT 10",              [term]),
        ("WEAPONS",      "SELECT DISTINCT name, profile_name FROM weapon WHERE name LIKE ? OR profile_name LIKE ? LIMIT 10", [term, term]),
        ("STRATAGEMS",   "SELECT name, faction, cp_cost FROM stratagem WHERE name LIKE ? LIMIT 10",              [term]),
        ("KEYWORDS",     "SELECT name, keyword_type, rules FROM keyword WHERE name LIKE ? LIMIT 5",              [term]),
        ("CORE RULES",   "SELECT section, title FROM core_rule WHERE title LIKE ? OR rules LIKE ? LIMIT 5",      [term, term]),
        ("DETACHMENTS",  "SELECT name, faction FROM detachment WHERE name LIKE ? LIMIT 10",                      [term]),
    ]:
        results = con.execute(sql, [LIKE(c) for c in cols]).fetchall()
        if results:
            print(f"{label} ({len(results)} found):")
            for r in results:
                row = dict(r)
                vals = [str(v) for v in row.values() if v]
                print(f"  {' | '.join(vals[:3])}")
            print()
    print("(search complete)")


COMMANDS = {
    "unit":        cmd_unit,
    "weapon":      cmd_weapon,
    "stratagem":   cmd_stratagem,
    "detachment":  cmd_detachment,
    "army-rule":   cmd_army_rule,
    "enhancement": cmd_enhancement,
    "faq":         cmd_faq,
    "keyword":     cmd_keyword,
    "core-rule":   cmd_core_rule,
    "search":      cmd_search,
}


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(0)
    cmd   = sys.argv[1].lower()
    query = " ".join(sys.argv[2:])
    if cmd not in COMMANDS:
        print(f"Unknown command '{cmd}'. Available: {', '.join(COMMANDS)}")
        sys.exit(1)
    con = get_db()
    COMMANDS[cmd](con, query)
    con.close()


if __name__ == "__main__":
    main()
