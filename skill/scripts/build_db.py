#!/usr/bin/env python3
"""
WH40K Rules Database Builder
Converts a dump_vXXX.json from the Warhammer 40,000 app into a queryable SQLite database.

Usage:
    python build_db.py /path/to/dump_vXXX.json

The database is written to:
    <skill_dir>/data/wh40k_rules.db

Combat Patrol and event-companion content is automatically excluded.
"""
import html
import json
import re
import sqlite3
import sys
from pathlib import Path

# The DB always lives in <skill_dir>/data/ — relative to this script
SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB = SKILL_DIR / "data" / "wh40k_rules.db"

_LIST_ITEM = re.compile(r"<li>(.*?)</li>", re.DOTALL)
_TAG       = re.compile(r"<[^>]+>")

# Rule sections to exclude — game-mode-specific sequences whose numbering
# (01.xx, etc.) collides with Core Concepts and contains no matched-play rules.
EXCLUDED_RULE_SECTIONS = {
    "01. Combat Patrol Mission Sequence",
    "Event Companion",
    "Dominatus Event Companion",
    "Doubles Event Companion",
    "Teams Event Companion",
}


def clean(text: str) -> str:
    if not text:
        return text
    text = _LIST_ITEM.sub(r"\n■ \1", text)
    text = _TAG.sub("", text)
    text = html.unescape(text)
    return text.strip()


def en(obj, field="name"):
    loc = obj.get("localisations", {})
    return clean((loc.get("en") or {}).get(field) or "")


def _build_exclusion_sets(raw: dict) -> dict:
    cp_pub_ids = {p["id"] for p in raw["publication"] if p.get("isCombatPatrol")}
    cp_ds_ids  = {d["id"] for d in raw["datasheet"] if d.get("publicationId") in cp_pub_ids}
    cp_det_ids = {d["id"] for d in raw["detachment"] if d.get("isCombatPatrol")}

    cp_section_ids = set()
    for rs in raw["rule_section"]:
        name = (rs.get("localisations") or {}).get("en", {}).get("name", "")
        if name in EXCLUDED_RULE_SECTIONS:
            cp_section_ids.add(rs["id"])

    cp_container_ids = {
        rc["id"] for rc in raw["rule_container"]
        if rc.get("ruleSectionId") in cp_section_ids
    }

    print(f"  Excluding: {len(cp_pub_ids)} CP publications, "
          f"{len(cp_ds_ids)} CP datasheets, "
          f"{len(cp_det_ids)} CP detachments, "
          f"{len(cp_section_ids)} excluded rule sections")

    return {
        "pub_ids":       cp_pub_ids,
        "ds_ids":        cp_ds_ids,
        "det_ids":       cp_det_ids,
        "section_ids":   cp_section_ids,
        "container_ids": cp_container_ids,
    }


def build(json_path: Path, db_path: Path):
    print(f"Loading {json_path} …")
    with open(json_path, encoding="utf-8") as f:
        raw = json.load(f)["data"]

    print("Computing exclusions (Combat Patrol + event-companion) …")
    excl = _build_exclusion_sets(raw)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    cur.executescript("""
    CREATE TABLE unit (
        id TEXT PRIMARY KEY, name TEXT, factions TEXT, publication TEXT,
        lore TEXT, unit_composition TEXT, base_size TEXT,
        is_legends INTEGER, min_points INTEGER, max_points INTEGER
    );
    CREATE TABLE unit_stat (
        id TEXT PRIMARY KEY, unit_id TEXT, stat_name TEXT,
        movement TEXT, toughness TEXT, save TEXT, wounds TEXT,
        leadership TEXT, oc TEXT, invuln TEXT
    );
    CREATE TABLE unit_ability (
        id TEXT PRIMARY KEY, unit_id TEXT, name TEXT,
        ability_type TEXT, is_aura INTEGER, is_psychic INTEGER, rules TEXT
    );
    CREATE TABLE weapon (
        id TEXT PRIMARY KEY, name TEXT, profile_name TEXT, weapon_type TEXT,
        range_val TEXT, attacks TEXT, skill TEXT, strength TEXT,
        ap TEXT, damage TEXT, abilities TEXT
    );
    CREATE TABLE stratagem (
        id TEXT PRIMARY KEY, name TEXT, cp_cost TEXT,
        detachment_id TEXT, detachment_name TEXT, faction TEXT,
        when_rules TEXT, target_rules TEXT, effect_rules TEXT, restriction_rules TEXT
    );
    CREATE TABLE detachment (
        id TEXT PRIMARY KEY, name TEXT, faction TEXT,
        publication TEXT, points_cost INTEGER
    );
    CREATE TABLE detachment_rule (
        id TEXT PRIMARY KEY, detachment_id TEXT, detachment_name TEXT,
        faction TEXT, name TEXT, rules TEXT
    );
    CREATE TABLE army_rule (
        id TEXT PRIMARY KEY, name TEXT, faction TEXT,
        publication TEXT, rules TEXT
    );
    CREATE TABLE enhancement (
        id TEXT PRIMARY KEY, name TEXT, detachment_id TEXT,
        detachment_name TEXT, faction TEXT, publication TEXT,
        points INTEGER, rules TEXT, lore TEXT
    );
    CREATE TABLE faq (
        id TEXT PRIMARY KEY, faction TEXT, publication TEXT,
        header TEXT, body TEXT, question TEXT, answer TEXT
    );
    CREATE TABLE keyword (
        id TEXT PRIMARY KEY, name TEXT, keyword_type TEXT, rules TEXT
    );
    CREATE TABLE core_rule (
        id TEXT PRIMARY KEY, section TEXT, title TEXT, subtitle TEXT,
        rule_type TEXT, rules TEXT, display_order INTEGER
    );
    """)

    print("Building index helpers …")
    pub_name = {p["id"]: en(p) for p in raw["publication"]}
    fk_name  = {fk["id"]: en(fk) for fk in raw["faction_keyword"]}

    ds_factions: dict = {}
    for row in raw["datasheet_faction_keyword"]:
        ds_factions.setdefault(row["datasheetId"], []).append(
            fk_name.get(row["factionKeywordId"], ""))

    ds_points: dict = {}
    for row in raw["unit_composition"]:
        if row.get("points") is not None:
            ds_points.setdefault(row["datasheetId"], []).append(
                (int(row["points"]), bool(row.get("isDefault"))))

    ds_invuln: dict = {}
    for row in raw["invulnerable_save"]:
        ds_invuln[row["datasheetId"]] = row.get("save") or ""

    mini_invuln: dict = {}
    for row in raw["invulnerable_save"]:
        if row.get("miniatureId"):
            mini_invuln[row["miniatureId"]] = row.get("save") or ""

    ds_abilities: dict = {}
    for row in raw["datasheet_datasheet_ability"]:
        ds_abilities.setdefault(row["datasheetId"], []).append(row["datasheetAbilityId"])

    ability_by_id = {a["id"]: a for a in raw["datasheet_ability"]}

    sub_abilities: dict = {}
    for row in raw["datasheet_sub_ability"]:
        sub_abilities.setdefault(row["datasheetAbilityId"], []).append(
            en(row, "rules") or "")

    wa_by_id = {w["id"]: en(w, "name") for w in raw["wargear_ability"]}
    profile_abilities: dict = {}
    for row in raw["wargear_item_profile_wargear_ability"]:
        profile_abilities.setdefault(row["wargearItemProfileId"], []).append(
            wa_by_id.get(row["wargearAbilityId"], ""))

    det_by_id = {d["id"]: d for d in raw["detachment"]}

    det_factions: dict = {}
    for row in raw["detachment_faction_keyword"]:
        det_factions.setdefault(row["detachmentId"], []).append(
            fk_name.get(row["factionKeywordId"], ""))

    arc_texts: dict = {}
    drc_texts: dict = {}
    core_texts: dict = {}
    for comp in raw["rule_container_component"]:
        text  = en(comp, "textContent") or ""
        title = en(comp, "title") or ""
        ctype = comp.get("type", "")
        order = comp.get("displayOrder", 0)
        if ctype == "loreAccordion":
            continue
        full = (f"**{title}**\n{text}" if title else text).strip()
        if not full:
            continue
        if comp.get("armyRuleId"):
            arc_texts.setdefault(comp["armyRuleId"], []).append((order, ctype, full))
        elif comp.get("detachmentRuleId"):
            drc_texts.setdefault(comp["detachmentRuleId"], []).append((order, ctype, full))
        elif comp.get("ruleContainerId"):
            core_texts.setdefault(comp["ruleContainerId"], []).append(
                (order, ctype, title, text))

    ar_factions: dict = {}
    for row in raw["army_rule_faction_keyword"]:
        ar_factions.setdefault(row["armyRuleId"], []).append(
            fk_name.get(row["factionKeywordId"], ""))

    section_name: dict = {}
    for rs in raw["rule_section"]:
        section_name[rs["id"]] = en(rs)

    # ── Units ─────────────────────────────────────────────────────────────────
    print("Inserting units …")
    for ds in raw["datasheet"]:
        did = ds["id"]
        if did in excl["ds_ids"]:
            continue
        pts     = ds_points.get(did, [])
        min_pts = min((p for p, _ in pts), default=None)
        max_pts = max((p for p, _ in pts), default=None)
        cur.execute("INSERT INTO unit VALUES (?,?,?,?,?,?,?,?,?,?)", (
            did, en(ds),
            ", ".join(f for f in ds_factions.get(did, []) if f),
            pub_name.get(ds.get("publicationId", ""), ""),
            en(ds, "lore") or "", en(ds, "unitComposition") or "",
            en(ds, "baseSize") or "", int(bool(ds.get("isLegends"))),
            min_pts, max_pts))

    print("Inserting unit stats …")
    for m in raw["miniature"]:
        mid, did = m["id"], m["datasheetId"]
        if did in excl["ds_ids"]:
            continue
        cur.execute("INSERT INTO unit_stat VALUES (?,?,?,?,?,?,?,?,?,?)", (
            mid, did, en(m) or "",
            m.get("movement") or "", m.get("toughness") or "",
            m.get("save") or "", m.get("wounds") or "",
            m.get("leadership") or "", m.get("objectiveControl") or "",
            mini_invuln.get(mid) or ds_invuln.get(did, "")))

    print("Inserting unit abilities …")
    seen = set()
    for did, ab_ids in ds_abilities.items():
        if did in excl["ds_ids"]:
            continue
        for ab_id in ab_ids:
            ab = ability_by_id.get(ab_id)
            if not ab or (did, ab_id) in seen:
                continue
            seen.add((did, ab_id))
            rules = en(ab, "rules") or ""
            subs  = sub_abilities.get(ab_id, [])
            if subs:
                rules += "\n" + "\n".join(s for s in subs if s)
            cur.execute("INSERT INTO unit_ability VALUES (?,?,?,?,?,?,?)", (
                f"{did}_{ab_id}", did, en(ab) or "",
                ab.get("abilityType") or "",
                int(bool(ab.get("isAura"))), int(bool(ab.get("isPsychic"))),
                rules))

    print("Inserting weapons …")
    item_name  = {w["id"]: en(w) for w in raw["wargear_item"]}
    seen_prof  = set()
    for prof in raw["wargear_item_profile"]:
        pid = prof["id"]
        if pid in seen_prof:
            continue
        seen_prof.add(pid)
        wid  = prof.get("wargearItemId", "")
        skill = prof.get("ballisticSkill") or prof.get("weaponSkill") or ""
        cur.execute("INSERT OR IGNORE INTO weapon VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            pid, item_name.get(wid, ""), en(prof) or "",
            prof.get("type") or "", prof.get("range") or "",
            prof.get("attacks") or "", skill,
            prof.get("strength") or "", prof.get("armourPenetration") or "",
            prof.get("damage") or "",
            ", ".join(a for a in profile_abilities.get(pid, []) if a)))

    print("Inserting detachments …")
    for det in raw["detachment"]:
        did = det["id"]
        if did in excl["det_ids"]:
            continue
        cur.execute("INSERT INTO detachment VALUES (?,?,?,?,?)", (
            did, en(det) or "",
            ", ".join(f for f in det_factions.get(did, []) if f),
            pub_name.get(det.get("publicationId", ""), ""),
            det.get("detachmentPointsCost")))

    print("Inserting detachment rules …")
    for dr in raw["detachment_rule"]:
        det_id = dr.get("detachmentId", "")
        if det_id in excl["det_ids"]:
            continue
        det  = det_by_id.get(det_id, {})
        comps = sorted(drc_texts.get(dr["id"], []), key=lambda x: x[0])
        cur.execute("INSERT INTO detachment_rule VALUES (?,?,?,?,?,?)", (
            dr["id"], det_id, en(det) if det else "",
            ", ".join(f for f in det_factions.get(det_id, []) if f),
            en(dr) or "", "\n\n".join(c[2] for c in comps)))

    print("Inserting stratagems …")
    for strat in raw["stratagem"]:
        det_id = strat.get("detachmentId", "")
        if det_id in excl["det_ids"]:
            continue
        loc  = (strat.get("localisations") or {}).get("en") or {}
        det  = det_by_id.get(det_id, {})
        cur.execute("INSERT INTO stratagem VALUES (?,?,?,?,?,?,?,?,?,?)", (
            strat["id"], loc.get("name") or "", strat.get("cpCost") or "",
            det_id, en(det) if det else "",
            ", ".join(f for f in det_factions.get(det_id, []) if f),
            loc.get("whenRules") or "", loc.get("targetRules") or "",
            loc.get("effectRules") or "", loc.get("restrictionRules") or ""))

    print("Inserting army rules …")
    for ar in raw["army_rule"]:
        pub_id = ar.get("publicationId", "")
        if pub_id in excl["pub_ids"]:
            continue
        comps = sorted(arc_texts.get(ar["id"], []), key=lambda x: x[0])
        cur.execute("INSERT INTO army_rule VALUES (?,?,?,?,?)", (
            ar["id"], en(ar) or "",
            ", ".join(f for f in ar_factions.get(ar["id"], []) if f),
            pub_name.get(pub_id, ""),
            "\n\n".join(c[2] for c in comps)))

    print("Inserting enhancements …")
    for enh in raw["enhancement"]:
        det_id = enh.get("detachmentId", "")
        pub_id = enh.get("publicationId", "")
        if det_id in excl["det_ids"] or pub_id in excl["pub_ids"] or enh.get("isCombatPatrol"):
            continue
        det = det_by_id.get(det_id, {})
        cur.execute("INSERT INTO enhancement VALUES (?,?,?,?,?,?,?,?,?)", (
            enh["id"], en(enh) or "", det_id,
            en(det) if det else "",
            ", ".join(f for f in det_factions.get(det_id, []) if f),
            pub_name.get(pub_id, ""), enh.get("basePointsCost"),
            en(enh, "rules") or "", en(enh, "lore") or ""))

    print("Inserting FAQ / errata …")
    pub_faction: dict = {}
    for ar in raw["army_rule"]:
        pub_id = ar.get("publicationId", "")
        if pub_id in excl["pub_ids"]:
            continue
        facs = ar_factions.get(ar["id"], [])
        if facs and pub_id:
            pub_faction[pub_id] = ", ".join(f for f in facs if f)
    for fq in raw["faq"]:
        pub_id = fq.get("publicationId", "")
        if pub_id in excl["pub_ids"]:
            continue
        loc = (fq.get("localisations") or {}).get("en") or {}
        cur.execute("INSERT INTO faq VALUES (?,?,?,?,?,?,?)", (
            fq["id"], pub_faction.get(pub_id, ""),
            pub_name.get(pub_id, ""), loc.get("errataHeader") or "",
            loc.get("errataText") or "", loc.get("question") or "",
            loc.get("answer") or ""))

    print("Inserting weapon keywords …")
    seen_kw: set = set()
    for wa in raw["wargear_ability"]:
        name = en(wa) or ""
        key  = name.upper().strip()
        if key in seen_kw:
            continue
        seen_kw.add(key)
        cur.execute("INSERT INTO keyword VALUES (?,?,?,?)",
                    (wa["id"], name, "weapon", en(wa, "rules") or ""))

    seen_core_kw: dict = {}
    for ab in raw["datasheet_ability"]:
        if ab.get("abilityType") == "core":
            name  = en(ab)
            rules = en(ab, "rules") or ""
            if name and name not in seen_core_kw:
                seen_core_kw[name] = rules
    for name, rules in seen_core_kw.items():
        cur.execute("INSERT INTO keyword VALUES (?,?,?,?)",
                    (f"core_{name}", name, "core_ability", rules))

    print("Inserting core rules …")
    for rc in raw["rule_container"]:
        rc_id      = rc["id"]
        section_id = rc.get("ruleSectionId", "")
        if section_id in excl["section_ids"]:
            continue
        section  = section_name.get(section_id, "")
        title    = en(rc, "title") or ""
        subtitle = en(rc, "subtitle") or ""
        rc_type  = rc.get("containerType", "")
        order    = rc.get("displayOrder", 0)
        comps    = sorted(core_texts.get(rc_id, []), key=lambda x: x[0])
        if not comps:
            continue
        rules_text = "\n\n".join(
            (f"**{c[2]}**\n{c[3]}" if c[2] and c[2] != title else c[3]).strip()
            for c in comps)
        cur.execute("INSERT INTO core_rule VALUES (?,?,?,?,?,?,?)",
                    (rc_id, section, title, subtitle, rc_type, rules_text, order))

    print("Creating indexes …")
    cur.executescript("""
    CREATE INDEX idx_unit_name     ON unit(name COLLATE NOCASE);
    CREATE INDEX idx_unit_factions ON unit(factions);
    CREATE INDEX idx_unit_stat_uid ON unit_stat(unit_id);
    CREATE INDEX idx_unit_ab_uid   ON unit_ability(unit_id);
    CREATE INDEX idx_weapon_name   ON weapon(name COLLATE NOCASE);
    CREATE INDEX idx_weapon_prof   ON weapon(profile_name COLLATE NOCASE);
    CREATE INDEX idx_strat_det     ON stratagem(detachment_id);
    CREATE INDEX idx_strat_faction ON stratagem(faction);
    CREATE INDEX idx_strat_name    ON stratagem(name COLLATE NOCASE);
    CREATE INDEX idx_det_faction   ON detachment(faction);
    CREATE INDEX idx_det_name      ON detachment(name COLLATE NOCASE);
    CREATE INDEX idx_dr_det        ON detachment_rule(detachment_id);
    CREATE INDEX idx_dr_faction    ON detachment_rule(faction);
    CREATE INDEX idx_ar_faction    ON army_rule(faction);
    CREATE INDEX idx_enh_det       ON enhancement(detachment_id);
    CREATE INDEX idx_enh_faction   ON enhancement(faction);
    CREATE INDEX idx_faq_faction   ON faq(faction);
    CREATE INDEX idx_faq_pub       ON faq(publication);
    CREATE INDEX idx_kw_name       ON keyword(name COLLATE NOCASE);
    CREATE INDEX idx_kw_type       ON keyword(keyword_type);
    CREATE INDEX idx_cr_section    ON core_rule(section);
    CREATE INDEX idx_cr_title      ON core_rule(title COLLATE NOCASE);
    """)

    con.commit()
    con.close()
    size_mb = db_path.stat().st_size / 1_048_576
    print(f"\nDatabase ready: {db_path}  ({size_mb:.1f} MB)")

    # Quick completeness check
    con2 = sqlite3.connect(db_path)
    for table in ["unit", "weapon", "stratagem", "detachment", "core_rule", "keyword"]:
        n = con2.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<20} {n:>5} rows")
    con2.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python build_db.py <path/to/dump_vXXX.json> [output/path/wh40k_rules.db]")
        print(f"Default output: {DEFAULT_DB}")
        sys.exit(1)
    json_path = Path(sys.argv[1])
    db_path   = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_DB
    if not json_path.exists():
        print(f"Error: JSON file not found: {json_path}")
        sys.exit(1)
    build(json_path, db_path)
