---
name: wh40k
description: >
  Look up Warhammer 40,000 (11th edition) rules from the official app dataset. Use this skill
  whenever the user asks about WH40K units, weapons, stats, abilities, stratagems, detachments,
  army rules, enhancements, points costs, FAQ/errata, OR asks about rule interactions, rulings,
  "does X work with Y", "can I do Z", or how two rules interact. Also covers organised play and
  Warhammer Event rules: event mission sequence, VP structure, secondary missions (Fixed/Tactical),
  Battle Ready scoring, Force Disposition, and Chapter Approved Mission Deck FAQs. Triggers on any
  WH40K rules lookup, ruling question, or event/tournament play question.
---

# Warhammer 40,000 11th Edition — Rules Skill

## First-time setup

This skill requires a local SQLite database built from the Warhammer 40,000 app's data export.

**Step 1 — Get your data file**
Export a `dump_vXXX.json` from the official Warhammer 40,000 app or obtain one from your
organisation. The file is typically 30–40 MB.

**Step 2 — Build the database (run once)**
```bash
python scripts/build_db.py /path/to/your/dump_vXXX.json
```
This creates `data/wh40k_rules.db` inside the skill folder. Takes ~30 seconds.
Run again whenever you have a newer dump file.

**Step 3 — Use the skill**
The skill is now ready. All queries run against the local database automatically.

---

## Query commands

Find the query script relative to this file, then use it:

```bash
# Discover the scripts directory at runtime
QUERY="$(python3 -c "import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve())" \
  "$(dirname "$0")/scripts/query.py" 2>/dev/null || \
  find ~ -name "query.py" -path "*/wh40k/scripts/*" 2>/dev/null | head -1)"

python3 "$QUERY" unit <name>            # stats, abilities, points, composition
python3 "$QUERY" weapon <name>          # range, A, BS/WS, S, AP, D, special rules
python3 "$QUERY" stratagem <faction>    # all stratagems with CP cost + WHEN/TARGET/EFFECT
python3 "$QUERY" detachment <faction>   # detachment list + full rule text
python3 "$QUERY" army-rule <faction>    # faction-wide army rule text
python3 "$QUERY" enhancement <faction>  # enhancements + points + rules
python3 "$QUERY" faq <faction|topic>    # FAQ and errata entries
python3 "$QUERY" keyword <name>         # [LETHAL HITS], [SUSTAINED HITS], Feel No Pain, etc.
python3 "$QUERY" core-rule <section>    # core rulebook text by section name or topic
python3 "$QUERY" search <term>          # cross-table keyword search
```

Alternatively, pass the absolute path directly once you know it.

---

## Simple lookups

For direct factual questions (stats, weapon profiles, ability text, stratagem list): run the
appropriate command and synthesise the result — don't dump raw output.

---

## Rule interaction rulings

When the user asks "does X work with Y", "can I do Z", or "what happens when…":

### Step 1 — Gather all relevant rules

Pull the exact text of every rule involved. Paraphrasing leads to wrong rulings.

```bash
python3 "$QUERY" core-rule "04. Making Attacks"
python3 "$QUERY" core-rule "05. Attack Sequence"
python3 "$QUERY" core-rule "06. Other Concepts"
python3 "$QUERY" core-rule "01. Core Concepts"
python3 "$QUERY" core-rule "02. Datasheets"
python3 "$QUERY" core-rule "15. Stratagems"
python3 "$QUERY" core-rule "19. Attached Units"
python3 "$QUERY" keyword "Lethal Hits"
python3 "$QUERY" keyword "Devastating Wounds"
python3 "$QUERY" keyword "Feel No Pain"
python3 "$QUERY" faq "topic or faction"
```

Run multiple queries in parallel.

### Step 2 — Apply the WH40K 11th edition ruling principles

**Principle 1 — Check FAQ/errata first.**
If the FAQ settles it, cite it and stop.

**Principle 2 — Read the exact rule text from the database.**
Do not rely on memory of previous editions. 11th edition changed many fundamentals.

**Principle 3 — Specific overrides general.**
A datasheet ability that explicitly addresses a situation is an exception to the core rule for
that unit. If a rule says "unless otherwise stated", the thing that "states otherwise" wins.
Source: implied by 01.03.02 and general rule structure.

**Principle 4 — "Cannot" beats "can" (restriction beats permission).**
If one rule permits something and another restricts it, the restriction wins — unless the
permissive rule explicitly says "even if…", "regardless of…", or "cannot be prevented by…".

**Principle 5 — Rules sequencing when two rules trigger at the same time (01.03.02).**
When two rules can or must be used at the same time, resolve in this order:
1. Active player's rules that **must** be used — in an order of their choosing.
2. Active player's rules they **can** optionally use — in an order of their choosing.
3. Opposing player's rules that **must** be used — in an order of their choosing.
4. Opposing player's rules they **can** optionally use — in an order of their choosing.

If a new rule triggers *during* this sequence, it does not fire until all remaining rules in
the same timing window have resolved. Who is the active player changes contextually (01.03):
while a unit is selected to shoot or fight, that unit's controlling player is the active player.

**Principle 6 — The attack-dice / fast-rolling system (04.03).**

Attack flow: **04.01 Select Weapons → 04.02 Select Targets → 04.03 Resolve Attacks**

Within 04.03:
1. **Gather Attack Dice**: pick one weapon, gather D6s = A characteristic. Any other weapons
   targeting the *same unit* that make **identical attacks (04.03.01)** — same BS/WS, S, AP, D,
   and same applicable abilities — pool into the same batch immediately.
2. **Resolve Attack Sequence (05)**: run the full sequence for the entire batch simultaneously.
3. Repeat for remaining weapons or targets.

*Identical attacks (04.03.01)*: any difference in BS/WS, S, AP, D, or applicable abilities
breaks the pool into separate batches. Modifier differences between weapons always create
separate batches (04.01.04).

**Principle 7 — The attack sequence step by step (05.00–05.04).**

- **Hit Rolls (05.01):** All dice simultaneously. Unmod 1 = fail. Unmod 6 = critical hit
  (05.01.01). ≥ BS/WS = hit.
  - **[SUSTAINED HITS X] (24.36):** Critical hit → X automatic additional **hits** (no dice
    rolled; they are not attack dice — go straight to Wound Roll).
  - **[LETHAL HITS] (24.23):** Critical hit → *may choose* to auto-wound (skip wound roll).
    If chosen: no wound roll → no critical wound → 24.10 [DEVASTATING WOUNDS] **cannot** trigger.
    (24.23 Designer's Note confirms this explicitly.)

- **Wound Rolls (05.02):** Remaining hits rolled simultaneously. Unmod 6 = critical wound.
  S vs T table otherwise.
  - *Multiple T (05.02.01)*: use highest T of bodyguard models; if none remain, highest T of
    remaining models.
  - **[DEVASTATING WOUNDS] (24.10):** Critical wound ends attack sequence; target suffers mortal
    wounds = D characteristic. Inflicted *after* all normal damage from the batch (06.02).
    Capped to one model per critical wound — excess mortal wounds from that die are lost.

- **Save Rolls (05.03):** Models divided into *allocation groups* — one per CHARACTER model, one
  per set of non-CHARACTER models sharing the same W, Sv, and InSv. No CHARACTER group can
  precede any surviving non-CHARACTER group. One save roll per wounding attack.
  - **[PRECISION] (24.28):** At the Allocation Order step: may select a visible CHARACTER group
    as the current group, overriding normal order.
  - Invulnerable save checked before armour save.

- **Inflict Damage (05.04):** Save rolls resolved lowest → highest. For each: select model in
  current group (05.04.01), check save, model loses wounds = D.
  - **Feel No Pain X+ (24.12):** Each time a model would lose a wound, roll D6: on X+, not lost.
    Applies to mortal wounds too.
  - **Random D (02.02.03):** Determined *now* — when defending player selects the model.

- **Mortal Wounds (06.02):** Resolved *after all normal damage from the same batch*. Priority:
  (1) wounded non-CHARACTER → (2) any non-CHARACTER → (3) wounded CHARACTER → (4) any CHARACTER.

**Principle 8 — Modifier application order and caps (02.02.01).**

Order: **Replace → × Multiply → + Add → ÷ Divide → − Subtract → round up**

All modifiers are cumulative. However **hit rolls and wound rolls are capped**: sum all
cumulative modifiers, then cap total at +1 or −1.

*"Unmodified" = after re-rolls, before modifiers (02.02.01, 01.05.02).* An unmodified 6 is
a critical hit regardless of a −1 modifier. A +1 to hit does not make a 5 a critical hit.

*Characteristic hard limits after all modifiers (02.02.01):*
Sv/InSv cannot be 1+ or better. WS/BS cannot be 1+ or better nor 7+ or worse. AP cannot be
worse than 0. A, D, S cannot be less than 1. M and Range cannot be less than 1".

*Modifiers lock in at weapon level (04.01.04):* modifier differences break identical-attack
pools, forcing separate batches.

*Ignoring modifiers is selective (02.02.02):* may ignore only detrimental modifiers while
retaining beneficial ones.

**Principle 9 — Duplicated abilities (24.02).**
Multiple instances of the same core or weapon ability do not stack. Controlling player picks
which instance applies at any given time. For weapon abilities, choice is made at Select Weapons.

**Principle 10 — Stratagem stacking rules (15.01).**
- Same stratagem: once per phase per player.
- Same unit: targeted by at most one stratagem per phase (unless otherwise stated).
- CP cost: cannot be reduced below 0 CP (15.01.01).
- Battle-shocked units: cannot be targeted by stratagems (01.07).

**Principle 11 — Attached units (19.00–19.04).**
- T characteristic: use highest T of bodyguard models; only switch to leader/support T if no
  bodyguard models survive (19.02).
- Keywords: attached unit has all keywords of all components; models keep only their own (19.03).
- Abilities: from a leader/support apply to the whole attached unit until that leader/support's
  last model is destroyed; abilities from bodyguard apply until bodyguard's last model is
  destroyed (19.04). Single-model abilities (e.g. from an enhancement) apply only to that model.

**Principle 12 — "Each time" vs "once per…"**
"Each time" applies to every qualifying event. "Once per phase/turn/battle" caps regardless of
batch size.

**Principle 13 — Rules that trigger "against" an attack (04.02.02).**
Rules triggered "against" attacks activate after Select Targets (04.02), before rolling.
Rules triggered when an attack is "allocated" activate at step 1 of Inflict Damage (05.04).

**Principle 14 — Battle round and phase structure (07).**
Battle round: Start → Player Turns (both) → End. Each turn: Start → Command → Movement →
Shooting → Charge → Fight → End (07.02).
- *Out-of-phase rules (07.02.01)*: cannot also trigger phase-locked rules.
- *Definitions (07.02.02)*: "the phase" triggers in both players' phases; "your phase" only yours.

**Principle 15 — Movement, coherency, engagement (03, 09).**
- *Coherency (03.03)*: every model within 2" horizontal / 5" vertical of at least one other,
  AND within 9" horizontal / 5" vertical of every other model in the unit.
- *Engagement range (03.04)*: 2" horizontal / 5" vertical. While any model is within this of an
  enemy model, both those models and their units are engaged. No engaged models = unengaged.
- *Move types (09.02)*: Remain Stationary; Normal (up to M"); Advance (D6 + M — no shoot except
  [ASSAULT], no charge); Fall-back (no shoot/charge unless a rule permits); Disembark (see 18.03);
  Ingress/arrive from strategic reserves (see 20.03).

**Principle 16 — Charge Phase and Fight Phase (11, 12).**
- *Charge (11.02)*: must end in engagement range of declared target; roll 2D6. Failure if cannot
  reach (11.02.01).
- *Fight eligibility (12.04)*: unit must be engaged, or was engaged at start of Fight step, or
  made a charge move this turn.
- *Fights First (24.13)*: every model in unit must have the ability. Fights First units selected
  before other eligible units; active player selects first in each step.
- *Eligible but unable (12.04.01)*: if all eligible units are >5" from all enemies, the
  controlling player may pass. Both passing in succession ends the Fight step.

**Principle 17 — Terrain (13). V11 cover ≠ V10 cover.**
- *Benefit of Cover (13.08)*: unit has cover if every model is INFANTRY/BEASTS/SWARM within a
  terrain area, OR every model is not fully visible due to intervening terrain.
  Effect: **worsen attacker's BS by 1** — this is NOT a +1 Sv bonus. [IGNORES COVER] (24.18) prevents.
- *Hidden (13.09)*: model is INFANTRY/BEASTS/SWARM in terrain with light/dense features AND unit
  made no ranged attacks this turn or last turn. Only visible to enemies within detection range
  (15" default). First turn: "previous turn" condition is treated as satisfied.
- *Obscuring (13.10)*: terrain area with light/dense blocks LoS if every line of sight crosses it
  and neither model is within it.
- *Plunging Fire (22.05)*: attacking from terrain ≥3" high, or TOWERING keyword within 12" of
  target: improve (subtract 1 from) BS characteristic of that ranged attack. New to 11th edition.

**Principle 18 — Objectives and OC (14).**
- Objectives are terrain areas (14.01); model is in range while within the terrain area.
- *Level of control (14.02)*: sum OC of all models in range. Highest controls. Tie = neither
  controls (unless secured 14.03). Checked at end of each phase and turn.
- OC modified to "−" (e.g. battle-shocked) contributes 0 to control totals.
- *Secured (14.03)*: stays controlled even with no models present, until opponent's OC exceeds
  yours at the end of a phase.

**Principle 19 — Ability types and Monsters/Vehicles (22, 17).**
- *Aura abilities (22.01)*: model always in range of its own aura; same aura from multiple
  sources applies only once to a unit.
- *Faction abilities (22.02)*: apply only if army faction matches unit's faction keyword.
- *Wargear abilities (22.04)*: gained from equipment; bearer applies until destroyed.
- *MONSTER/VEHICLE movement (17.01)*: can move through friendly/enemy models (not other
  MONSTERs/VEHICLEs) during normal and advance moves.
- *Shooting at engaged MONSTER/VEHICLE (17.03)*: can target in Shooting phase (excluding [BLAST]);
  −1 to hit unless attacker uses [CLOSE-QUARTERS] while itself engaged with the target.

**Principle 20 — Transports and Strategic Reserves (18, 20).**
- *Embarking (18.02)*: after normal/advance/fall-back move, every model within 3" of TRANSPORT,
  not set up on battlefield this turn, eligible per datasheet.
- *Disembarking (18.03)*: active player's Movement phase; set up within 3" of TRANSPORT; not in
  engagement range of enemies.
- *Strategic reserves (20.01)*: max half army points in reserve; arrive from turn 2 via ingress
  move; destroyed at end of turn 3 if not arrived (20.03).

**Principle 21 — Organised Play / Warhammer Event rules.**
Source: Warhammer Event Companion v1.0 (pages 1–4). Used at official GW Warhammer Events and
most organised-play tournaments.

*Event Mission Sequence (14 steps):*
1. **Muster Armies** — select one Force Disposition card and record on roster.
2. **Determine Mission** — your Primary Mission = the one listed under *your opponent's* Force
   Disposition symbol (each player can have a different Primary Mission).
3. **Determine a Layout** — A, B, or C for the pair of Primary Missions; set by organiser or
   randomly determined.
4. **Create the Battlefield** — 44" × 60"; terrain placed per selected layout.
5. **Determine Attacker and Defender** — agree which edges match the layout labels; roll-off
   winner chooses their role.
6. **Select Secondary Missions** — secretly note Fixed or Tactical, then reveal simultaneously.
   - *Fixed*: face-up, cannot be discarded, active all battle (max 20VP per Fixed card).
   - *Tactical*: draw 2 at start of each Command phase; once per battle spend 1CP to swap one
     active card for a new draw; may discard any active card for 1CP.
7. **Declare Battle Formations** — secretly note embarked units and units in strategic reserves;
   reveal simultaneously.
8. **Deploy Armies** — alternate one unit at a time, Defender first. TITANIC unit costs next
   setup turn. When one player finishes, opponent sets up all remaining units.
9. **Redeploy Units** — post-deployment redeployments resolved now; alternate from Attacker.
   Units placed in reserves here do not count toward the reserves points limit.
10. **Determine First Turn** — roll-off; winner takes first turn.
11. **Resolve Pre-Battle Rules** — alternate from first-turn player.
12. **Begin the Battle.**
13. **End the Battle** — after 5 battle rounds. Both players complete their turns even if one
    has no models remaining.
14. **Determine Victor** — highest VP wins; tie = draw. Each player scores 10VP for a Battle
    Ready standard army.

*VP maximums:*

| Source | Per-round cap | Total cap |
|---|---|---|
| Primary Mission | 15VP | 45VP |
| Secondary Missions | 15VP | 45VP (20VP cap per Fixed card) |
| Battle Ready Army | — | 10VP |
| **Grand total** | | **100VP** |

*Key card-rule definitions (Event Companion p.3):*
- **Leaves the battlefield**: destroyed, embarks within a TRANSPORT, or removed by a rule.
- **Cumulative** condition: if met, gain VP for both the cumulative and the preceding condition.
- **Or** condition: gain VP for only one of the listed options.
- **One** (underlined): exactly one — not "one or more."
- **VP up to a limit**: any VP beyond the stated limit are ignored.
- **When Drawn**: only applies when using Tactical Secondary Missions.

*Mission Deck FAQ (p.4, current June 2026):*
- Operation markers cannot be removed unless the Primary Mission card specifies how and when.
- Death Trap: terrain area need not be trapped at the moment of destruction — only at some point
  during that turn.
- Surveil the Foe: removing an operation marker after surveilling counts if both actions are in
  the same turn.
- Vital Link: operation markers on any central objective count toward cumulative VP, as long as
  those objectives are controlled.

### Step 3 — Present the ruling

**Ruling:** [one-sentence yes/no/conditional answer]

**Reasoning:**
- Quote the exact rule text, citing the rule number (e.g. "Rule 04.03.01 states…")
- Walk through the sequence step by step if timing matters
- State which principle applies and why

**Caveats / edge cases:** [anything that could flip the ruling]

**Source:** [rule numbers, ability names, FAQ reference]

If genuinely ambiguous, say so and explain both interpretations — do not invent a ruling.

---

## Core rule number reference

The complete rule-number index (all 127 cited rules across sections 01–25) is in:

```
references/rules_index.md
```

Load it with: `python3 "$QUERY" core-rule "<section name>"` for any section's full text,
or refer to `references/rules_index.md` to look up a rule number before citing it in a ruling.

## Search tips

- Faction names: `"Adeptus Astartes"`, `"T'AU EMPIRE"`, `"Chaos Space Marines"`, `"Death Guard"`,
  `"Astra Militarum"`, `"Tyranids"`, `"Orks"`, `"Necrons"`, `"Drukhari"`, `"Aeldari"`,
  `"Grey Knights"`, `"Adeptus Mechanicus"`, etc.
- Subfactions (Blood Angels, Salamanders, etc.): search by that name directly.
- Core rules: search by section name (`"04. Making Attacks"`, `"13. Terrain"`) or title
  (`"Identical Attacks"`, `"Benefit Of Cover"`, `"Modifiers"`).
- Search is case-insensitive, partial match.

## What's in the database

- **~1,035 datasheets** (all factions — exact count depends on your dump version)
- **~3,700 weapon profiles** with abilities
- **~1,360 stratagems**
- **~266 detachments** with full rule text
- **~910 enhancements**
- **~58 army rules**
- **~728 FAQ / errata entries**
- **Weapon keyword definitions** (all 24.xx abilities)
- **Full core rulebook text** — all 25 sections (01–25) plus Introduction, Mission Sequence, Appendix
- Combat Patrol and event-companion content excluded
