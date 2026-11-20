"""State audit: do the ledger, STATE_NOW, the log and the event clock agree?"""
import datetime
import re

INJURY_WORDS = r"cracked|broken|snapped|fractur|concuss|crushed|burn(?:ed|s|t)?\b|bite|bitten|torn|sprain|dislocat|pinned|stab|gash"
MONTHS = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}


def day_zero(game):
    """The calendar date of D0, read from a line like 'D1 Fri 15 Mar 2047'."""
    for text in [game.state] + game.log:
        m = re.search(r"D(\d+) (?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w* (\d{1,2}) ([A-Za-z]{3})\w*(?: (\d{4}))?", text)
        if m:
            year = int(m.group(4)) if m.group(4) else None
            if year is None:
                y = re.search(r"\b(20\d\d)\b", game.state + " " + str(game.ledger.get("flags", {}).get("date", "")))
                year = int(y.group(1)) if y else None
            if year and m.group(3).lower() in MONTHS:
                return datetime.date(year, MONTHS[m.group(3).lower()], int(m.group(2))) - datetime.timedelta(days=int(m.group(1)))
    return None


def audit(game):
    L, finds = game.ledger, []
    add = lambda sev, msg: finds.append((sev, msg))
    gm, flags = game.gm, game.ledger.get("flags", {})

    # the sheet itself
    probe = game.sheet()
    gm.recalc(probe)
    if probe["hp_max"] != L["hp_max"] or probe["mp_max"] != L["mp_max"]:
        add("FAIL", f"HP/MP maximum is {L['hp_max']}/{L['mp_max']} but Vitality and Intelligence give {probe['hp_max']}/{probe['mp_max']}")
    if L["hp"] > L["hp_max"] or L["hp"] < 0:
        add("FAIL", f"HP {L['hp']} is outside 0-{L['hp_max']}")
    if L.get("xp", 0) >= 100 * L["level"]:
        add("FAIL", f"XP {L['xp']} is enough to level up (needs {100 * L['level']}) but the level was not raised")
    if L.get("points", 0) < 0:
        add("FAIL", "unspent points are negative")
    base = 10 + L["level"] - 1
    low = [k for k, v in L["stats"].items() if v < base]
    if low:
        add("FAIL", f"{', '.join(low)} below {base}, the floor for Lv{L['level']} (+1 to every stat per level)")
    for skill, text in L.get("skills", {}).items():
        m = re.match(r"\s*(\d+)", str(text))
        techs = [e for e in L.get("effects", []) if e.get("src") == "training" and e.get("tech") is not None]
        if m and "taekwondo" in skill.lower() and techs:
            want = int(m.group(1)) // 2
            off = [e["id"] for e in techs if e["tech"] != want]
            if off:
                add("WARN", f"{skill} is mastery {m.group(1)}, so technique should be +{want} (+1 per 2 mastery); {', '.join(off)} differ")
    if L["hp"] == 0 and "down" not in game.state.lower():
        add("WARN", "HP is 0 (down and dying) but STATE_NOW does not say so")

    # ledger against STATE_NOW and the log
    head = "\n".join(game.state.splitlines()[:3])
    m = re.search(r"\bD(\d+)\b", head)
    if m and int(m.group(1)) != L["day"]:
        add("FAIL", f"STATE_NOW is written for D{m.group(1)} but the ledger is on D{L['day']} {L.get('time', '')}: STATE_NOW is stale")
    m = re.search(r"\bHP (\d+)", head)
    if m and int(m.group(1)) != L["hp"]:
        add("FAIL", f"STATE_NOW says HP {m.group(1)}; the ledger says HP {L['hp']}")
    last = game.log_day()
    if last is not None and last != L["day"]:
        add("WARN", f"the last log entry is D{last} but the ledger is on D{L['day']}")
    recent = " ".join(game.log[-12:]) + " " + game.state
    hurts = sorted({w.lower() for w in re.findall(INJURY_WORDS, recent, re.I)})
    if hurts and not L.get("injuries") and L["hp"] < L["hp_max"]:
        add("WARN", "recent notes mention injuries (" + ", ".join(hurts[:6]) + ") but the ledger has none, so gm.py applies no "
            "injury penalty to any roll. Add them with `gm.py injury add \"<name>\" <mod>` or note that they are cosmetic")

    # the calendar
    d0 = day_zero(game)
    if d0 and flags.get("date"):
        want = (d0 + datetime.timedelta(days=L["day"])).isoformat()
        if flags["date"] != want:
            add("FAIL", f"flags.date is {flags['date']} but D{L['day']} is {want} (D0 = {d0.isoformat()})")
    for e in game.events:
        if isinstance(e.get("day"), (int, float)) and e["day"] < L["day"] and not e.get("done"):
            add("WARN", f"event D{e['day']} {e.get('time', '')} is past and not marked done: {e['text'][:70]}")
    for key, val in flags.items():
        m = re.fullmatch(r"D(\d+)", str(val))
        if not (key.endswith("_due") and m):
            continue
        word = key.split("_")[0].lower()
        match = [e for e in game.events if word in e.get("text", "").lower()]
        if match and all(e.get("day") != int(m.group(1)) for e in match):
            add("FAIL", f"flags.{key} says D{m.group(1)} but the event clock has it on D{match[0]['day']}: {match[0]['text'][:60]}")
        elif not match:
            add("NOTE", f"flags.{key} = {val} has no matching entry in events.json")

    # every kill should have a card, and the daily counter should not run ahead of the calendar
    names = {f.get("name", "").lower() for f in game.foes.values()}
    for k in L.get("kills", {}):
        if not any(k.lower().startswith(n) or n.startswith(k.lower()) for n in names if n):
            add("NOTE", f"kill '{k}' has no foe card")
    dq = L.get("daily", {})
    if dq.get("count", 0) + dq.get("missed", 0) > L["day"] + 1:
        add("FAIL", f"daily quests done+missed ({dq.get('count', 0)}+{dq.get('missed', 0)}) exceed the days played")
    return finds
