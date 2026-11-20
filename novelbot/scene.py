"""Scene check: the mechanical half of a review.

It compares what a scene shows (status numbers, dice lines, techniques,
names, format) with the ledger and the log. Judgment calls such as voice,
fight style and plot holes belong to the reviewer bot (bots/SCENE_CHECKER.md).
"""
import json
import re

LABELS = {"Strength": "Str", "Vitality": "Con", "Agility": "Agi", "Intelligence": "Int", "Perception": "Sense"}
DEFAULT_RULES = {
    "banned": [
        {"pattern": r"\bKim Dokja\b|\bStar Stream\b|\bDokkaebi Bag\b|\bWays of Survival\b", "why": "Omniscient Reader's Viewpoint element"},
        {"pattern": r"\bMori Jin state\b", "why": "ruled out: there is no 'Mori Jin state' in this world"}
    ],
    "weapon_words": r"\bdaggers?\b|\bknife\b|\bknives\b",
    "options": {"min": 3, "max": 4, "free": "something else"}
}


def rules(game):
    r = json.loads(json.dumps(DEFAULT_RULES))
    extra = game.json("review_rules.json", {})
    r["banned"] += extra.get("banned", [])
    for k in ("weapon_words", "options"):
        if k in extra:
            r[k] = extra[k]
    return r


def technique_levels(game):
    """'M5 **Ground Drawer**' in SKILL_TREES.md -> {'ground drawer': 5}"""
    out = {}
    for line in game.text("SKILL_TREES.md").splitlines():
        m = re.match(r"\s*-\s*M(\d)\s+(.*)", line)
        if m:
            for name in re.findall(r"\*\*([^*]+)\*\*", m.group(2)):
                out[name.strip().lower()] = int(m.group(1))
    return out


def lost_names(game):
    """A memory like "Hana's name" means Mori can no longer say or think 'Hana'."""
    out = []
    for mem in game.ledger.get("flags", {}).get("memories_lost", []):
        m = re.search(r"([A-Z][a-z]+)'s name", mem)
        if m:
            out.append(m.group(1))
    return out


def check(game, text, turn=False):
    L, finds = game.ledger, []
    lines = text.splitlines()
    add = lambda sev, msg, n=None: finds.append((sev, (f"line {n}: " if n else "") + msg))
    R = rules(game)

    # status numbers shown to the player must be the ledger's
    hp = [(i, int(a), int(b)) for i, l in enumerate(lines, 1) for a, b in re.findall(r"\bHP:?\s*(\d+)\s*/\s*(\d+)", l)]
    for i, a, b in hp:
        if b != L["hp_max"]:
            add("FAIL", f"shows HP maximum {b}; the ledger has {L['hp_max']}", i)
    if hp and hp[-1][1] != L["hp"]:
        add("FAIL", f"the scene ends on HP {hp[-1][1]}; the ledger has {L['hp']} (apply the damage with gm.py, or fix the scene)", hp[-1][0])
    for i, l in enumerate(lines, 1):
        for a, b in re.findall(r"\bMP:?\s*(\d+)\s*/\s*(\d+)", l):
            if int(b) != L["mp_max"]:
                add("FAIL", f"shows MP maximum {b}; the ledger has {L['mp_max']}", i)
        m = re.search(r"\bLevel:?\s*(\d+)", l)
        if m and re.search(r"Name|Job|Class|Title|STATUS", " ".join(lines[max(0, i - 3):i + 1])) and int(m.group(1)) != L["level"]:
            add("FAIL", f"status window shows Level {m.group(1)}; the ledger has {L['level']}", i)
        for label, key in LABELS.items():
            m = re.search(rf"\b{label}:?\s+(\d+)\b", l)
            if m and int(m.group(1)) != L["stats"][key]:
                add("FAIL", f"shows {label} {m.group(1)}; the ledger has {L['stats'][key]}", i)

    # every die on the page must be one the engine rolled
    logged = [(r["d"], r["dc"]) for r in game.rolls()]
    pool = list(logged)
    dice = 0
    for i, l in enumerate(lines, 1):
        if "🎲" not in l and not re.search(r"d20 \*\*\d+\*\*", l):
            continue
        m = re.search(r"d20\s*\**(\d+)\**", l)
        dc = re.search(r"DC\s*(\d+)", l)
        if not m:
            continue
        dice += 1
        key = (int(m.group(1)), int(dc.group(1)) if dc else None)
        hit = next((p for p in reversed(pool) if p[0] == key[0] and key[1] in (None, p[1])), None)
        if hit:
            pool.remove(hit)
        else:
            add("FAIL", f"dice line (d20 {key[0]}" + (f", DC {key[1]}" if key[1] else "") + ") has no matching roll in LOG.md: "
                "it was not rolled with gm.py, or the number was changed", i)
        m2 = re.search(r"=\s*\**(-?\d+)\**\s*vs DC\s*(\d+)\s*(?:→|->)\s*\**([A-Za-z ]+\d?)\**", l)
        if m2:
            total, dcv, word = int(m2.group(1)), int(m2.group(2)), m2.group(3).strip().upper()
            want = game.gm.tier(key[0], total, dcv).replace("FAIL+", "NATURAL 1")
            if word != want:
                add("FAIL", f"result reads {word} but {total} vs DC {dcv} on a {key[0]} is {want}", i)

    # techniques above Mori's mastery
    mastery = 0
    for skill, val in L.get("skills", {}).items():
        m = re.match(r"\s*(\d+)", str(val))
        if m and "taekwondo" in skill.lower():
            mastery, note = int(m.group(1)), str(val).lower()
            for name, need in technique_levels(game).items():
                if need > mastery and name not in note:
                    for i, l in enumerate(lines, 1):
                        if re.search(rf"\b{re.escape(name)}\b", l, re.I):
                            add("WARN", f"'{name.title()}' opens at mastery {need}; Mori is at {mastery}. Fine if someone else "
                                "does it or he fails at it; otherwise it needs an earned unlock", i)
                            break

    # things Mori cannot say, own or do
    for name in lost_names(game):
        hits = [i for i, l in enumerate(lines, 1) if re.search(rf"\b{name}\b", l)]
        if hits:
            add("WARN", f"'{name}' appears on line(s) {', '.join(map(str, hits[:8]))}. Mori lost this name: fine in another "
                "character's mouth, an error in his speech, thoughts or narration from his view")
    for ban in R["banned"]:
        for i, l in enumerate(lines, 1):
            if re.search(ban["pattern"], l, re.I):
                add("FAIL", f"{ban['why']}: \"{l.strip()[:60]}\"", i)
    affinity = str(L.get("weapon_affinity", ""))
    if affinity and "dagger" not in affinity:
        for i, l in enumerate(lines, 1):
            if re.search(R["weapon_words"], l, re.I) and re.search(r"\bMori\b|\byou(r)?\b", l, re.I):
                add("WARN", f"a blade near Mori; his weapons are {affinity}", i)
                break

    # format
    for i, l in enumerate(lines, 1):
        if re.match(r"\s*(System|SYSTEM)\s*[:>-]", l):
            add("FAIL", "System messages go in [brackets]", i)
        if l.count("[") != l.count("]") and "](" not in l:
            add("WARN", "unbalanced bracket", i)
    tail = [l.strip() for l in lines if l.strip()][-8:]
    numbered = [l for l in tail if re.match(r"^\**\d+[.)]", l)]
    if turn or numbered:
        o = R["options"]
        if not o["min"] <= len(numbered) <= o["max"]:
            add("FAIL", f"a turn ends with {o['min']}-{o['max']} numbered options; found {len(numbered)}")
        if not any(o["free"] in l.lower() for l in tail):
            add("WARN", f"the options do not offer '{o['free']}'")

    # time
    m = re.search(r"\bD(\d+)\b[ ,]+(?:\w{3} \d+ \w+ ?(?:\d{4})? ?~?)?(\d{1,2}:\d{2})?", text)
    if m and int(m.group(1)) > L["day"]:
        add("FAIL", f"the scene is set on D{m.group(1)} but the ledger is still on D{L['day']}: advance the day with gm.py")
    elif m and int(m.group(1)) < L["day"]:
        add("NOTE", f"the scene is set on D{m.group(1)}; the ledger is already on D{L['day']} (fine for a scene being reviewed late)")

    # secrets: an optional GM-side watch list, never shown to the player
    from . import clues as CL, people as PE
    clue_data = CL.load(game)
    watch = game.json("secrets_watch.json", []) + CL.watch_list(clue_data)
    rung = max([clue_data.get("rung", 0)] + [int(x) for line in game.log for x in re.findall(r"rung (\d+)", line)])
    if game.text("people.json"):
        finds += PE.scene_findings(PE.load(game), text, lines)
    for w in watch:
        if w.get("rung", 99) > rung:
            for i, l in enumerate(lines, 1):
                if re.search(w["pattern"], l, re.I):
                    add("FAIL", f"secret leak: a rung-{w.get('rung')} truth is on the page while the story is at rung {rung}", i)
                    break
    if not watch:
        add("NOTE", "no watch patterns (clues.json or secrets_watch.json): the reviewer must check the reveal ladder by reading")
    if dice == 0 and re.search(r"\b(kick|punch|dodge|strike|swing)", text, re.I) and len(lines) > 12:
        add("NOTE", "a fight is described with no dice line shown; confirm every contested action was rolled")
    order = {"FAIL": 0, "WARN": 1, "NOTE": 2}
    return sorted(finds, key=lambda f: order[f[0]])
