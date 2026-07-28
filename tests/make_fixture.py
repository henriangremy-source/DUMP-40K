#!/usr/bin/env python3
"""
Generate a tiny synthetic dump JSON with the same shape as the real
Warhammer 40,000 app export.

This exists so the pipeline (build_db.py -> query.py -> session-start hook) can be
verified without the real ~35 MB dump, which is not redistributable and is not
committed by this script.

Usage:
    python3 tests/make_fixture.py /tmp/dump_v999.json
"""
import json
import sys
from pathlib import Path


def loc(**fields):
    return {"en": fields}


FIXTURE = {
    "data": {
        "publication": [
            {"id": "pub1", "isCombatPatrol": False, "localisations": loc(name="Codex: Test Marines")},
            {"id": "pubcp", "isCombatPatrol": True, "localisations": loc(name="Combat Patrol: Excluded")},
        ],
        "faction_keyword": [
            {"id": "fk1", "localisations": loc(name="Adeptus Astartes")},
        ],
        "datasheet": [
            {"id": "ds1", "publicationId": "pub1", "isLegends": False,
             "localisations": loc(name="Test Intercessor Squad", lore="They test.",
                                  unitComposition="1 Sergeant, 4 Intercessors", baseSize="32mm")},
            {"id": "dscp", "publicationId": "pubcp", "isLegends": False,
             "localisations": loc(name="Excluded CP Unit")},
        ],
        "datasheet_faction_keyword": [
            {"datasheetId": "ds1", "factionKeywordId": "fk1"},
        ],
        "unit_composition": [
            {"datasheetId": "ds1", "points": 80, "isDefault": True},
            {"datasheetId": "ds1", "points": 160, "isDefault": False},
        ],
        "invulnerable_save": [
            {"datasheetId": "ds1", "miniatureId": None, "save": "4+"},
        ],
        "miniature": [
            {"id": "min1", "datasheetId": "ds1", "movement": '6"', "toughness": "4",
             "save": "3+", "wounds": "2", "leadership": "6+", "objectiveControl": "2",
             "localisations": loc(name="Intercessor")},
        ],
        "datasheet_ability": [
            {"id": "ab1", "abilityType": "datasheet", "isAura": False, "isPsychic": False,
             "localisations": loc(name="Test Doctrine", rules="This unit tests things.")},
            {"id": "abcore", "abilityType": "core", "isAura": False, "isPsychic": False,
             "localisations": loc(name="Feel No Pain", rules="Roll a D6 each time a model loses a wound.")},
        ],
        "datasheet_datasheet_ability": [
            {"datasheetId": "ds1", "datasheetAbilityId": "ab1"},
        ],
        "datasheet_sub_ability": [
            {"datasheetAbilityId": "ab1", "localisations": loc(rules="Sub-clause of the test ability.")},
        ],
        "wargear_item": [
            {"id": "wi1", "localisations": loc(name="Test Bolt Rifle")},
        ],
        "wargear_item_profile": [
            {"id": "wp1", "wargearItemId": "wi1", "type": "Ranged", "range": '24"',
             "attacks": "2", "ballisticSkill": "3+", "strength": "4",
             "armourPenetration": "-1", "damage": "1",
             "localisations": loc(name="Test Bolt Rifle")},
        ],
        "wargear_ability": [
            {"id": "wa1", "localisations": loc(name="Lethal Hits",
                                               rules="Critical hit scores an automatic wound.")},
        ],
        "wargear_item_profile_wargear_ability": [
            {"wargearItemProfileId": "wp1", "wargearAbilityId": "wa1"},
        ],
        "detachment": [
            {"id": "det1", "isCombatPatrol": False, "publicationId": "pub1",
             "detachmentPointsCost": 0, "localisations": loc(name="Test Assault Doctrine")},
        ],
        "detachment_faction_keyword": [
            {"detachmentId": "det1", "factionKeywordId": "fk1"},
        ],
        "detachment_rule": [
            {"id": "dr1", "detachmentId": "det1", "localisations": loc(name="Test Detachment Rule")},
        ],
        "stratagem": [
            {"id": "st1", "detachmentId": "det1", "cpCost": "1",
             "localisations": loc(name="Test Stratagem", whenRules="Your Shooting phase.",
                                  targetRules="One unit from your army.",
                                  effectRules="That unit tests successfully.",
                                  restrictionRules="")},
        ],
        "enhancement": [
            {"id": "en1", "detachmentId": "det1", "publicationId": "pub1",
             "isCombatPatrol": False, "basePointsCost": 15,
             "localisations": loc(name="Test Relic", rules="Bearer tests better.", lore="Ancient.")},
        ],
        "army_rule": [
            {"id": "ar1", "publicationId": "pub1", "localisations": loc(name="Test Oath")},
        ],
        "army_rule_faction_keyword": [
            {"armyRuleId": "ar1", "factionKeywordId": "fk1"},
        ],
        "faq": [
            {"id": "faq1", "publicationId": "pub1",
             "localisations": loc(errataHeader="Page 42", errataText="Change 'X' to 'Y'.",
                                  question="Does the test work?", answer="Yes.")},
        ],
        "rule_section": [
            {"id": "rs1", "localisations": loc(name="04. Making Attacks")},
            {"id": "rscp", "localisations": loc(name="01. Combat Patrol Mission Sequence")},
        ],
        "rule_container": [
            {"id": "rc1", "ruleSectionId": "rs1", "containerType": "rule", "displayOrder": 1,
             "localisations": loc(title="Identical Attacks", subtitle="04.03.01")},
            {"id": "rccp", "ruleSectionId": "rscp", "containerType": "rule", "displayOrder": 1,
             "localisations": loc(title="Excluded CP Rule", subtitle="")},
        ],
        "rule_container_component": [
            {"type": "text", "displayOrder": 1, "ruleContainerId": "rc1",
             "localisations": loc(title="Identical Attacks",
                                  textContent="Attacks are identical if they share BS/WS, S, AP and D.")},
            {"type": "text", "displayOrder": 1, "armyRuleId": "ar1",
             "localisations": loc(title="", textContent="Once per battle, re-roll all hit rolls.")},
            {"type": "text", "displayOrder": 1, "detachmentRuleId": "dr1",
             "localisations": loc(title="", textContent="Units gain the test keyword.")},
            {"type": "text", "displayOrder": 1, "ruleContainerId": "rccp",
             "localisations": loc(title="", textContent="This should be excluded.")},
        ],
    }
}


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/dump_v999.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(FIXTURE), encoding="utf-8")
    print(f"Fixture written: {out}")
