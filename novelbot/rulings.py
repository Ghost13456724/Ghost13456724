"""Rulings and lessons keeper.

Rules made in the middle of play, and corrections the player gave, usually live
in one log line and are then forgotten. rulings.json keeps them, and makes the
ones that can be counted or checked do real work:

  kind "bonus"    a roll modifier that grows with use, per foe (adaptation: +1 per lost exchange, max +3)
  kind "limited"  something usable N times per day (a once-a-day reroll)
  kind "lesson"   a correction; with a "pattern" the scene check enforces it
  kind "rule"     a mechanics ruling kept for reference (XP, healing, 0 HP)
"""
import re

HARVEST = r"Rules? (?:added|clarified)|Correction|Retcon|RETCON|Ruling|Recalibrated|house rule"
DEFENCE = {"dodge", "read", "endure"}


def load(game):
    return game.json("rulings.json", None) or {"rulings": [], "uses": {}, "seen": []}


def get(data, rid):
    r = next((r for r in data["rulings"] if r["id"] == rid), None)
    if r is None:
        raise KeyError(f"no ruling '{rid}' (see `rules list`)")
    return r


def _new_id(data, base):
    base = re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_")[:24] or "r"
    ids, n, rid = {r["id"] for r in data["rulings"]}, 2, base
    while rid in ids:
        rid, n = f"{base}_{n}", n + 1
    return rid


def scan(game, data, plan):
    """Harvest rulings from the log and from item text; structure the ones whose shape is recognisable."""
    for i, line in enumerate(game.log):
        if not re.search(HARVEST, line) or line in data["seen"]:
            continue
        data["seen"].append(line)
        stamp = (re.match(r"- (D\d+(?: \d{1,2}:\d{2})?)", line) or [None, "?"])[1].strip()
        body = re.sub(r"^- D\d+ [\d:]*:?\s*", "", line)
        kind = "lesson" if re.search(r"Correction|Retcon", body, re.I) else "rule"
        m = re.search(r"(\w+) \(\+(\d+) per ([^,]+?)(?: vs same (\w+))?, max \+(\d+)", body)
        if m:
            data["rulings"].append({"id": _new_id(data, m.group(1)), "kind": "bonus", "per": m.group(4) or "foe",
                                    "step": int(m.group(2)), "max": int(m.group(5)), "trigger": m.group(3).strip(),
                                    "text": body, "source": stamp, "reviewed": False})
            plan.note(f"bonus ruling found: {m.group(1)} (+{m.group(2)} per {m.group(3).strip()}, max +{m.group(5)})")
        rid = _new_id(data, ("lesson " if kind == "lesson" else "rule ") + stamp)
        data["rulings"].append({"id": rid, "kind": kind, "text": body, "source": stamp, "reviewed": False})
        plan.note(f"{kind} harvested from {stamp}: {body[:70]}...")
    for item in game.ledger.get("items", []):
        m = re.search(r"once per (day|fight|scene)[:,]?\s*([^)]*)", item, re.I)
        name = item.split("(")[0].strip()
        if m and not any(r.get("item") == name for r in data["rulings"]):
            data["rulings"].append({"id": _new_id(data, name), "kind": "limited", "item": name, "per": m.group(1).lower(),
                                    "uses": 1, "text": f"{name}: once per {m.group(1).lower()}, {m.group(2).strip()}",
                                    "source": "ledger item", "reviewed": False})
            plan.note(f"limited-use ruling found: {name} (once per {m.group(1).lower()})")


def import_lessons(data, text, source, plan):
    """Numbered lines of an older LESSONS.md become unreviewed lessons."""
    have = {r["text"] for r in data["rulings"]}
    n = 0
    for line in text.splitlines():
        m = re.match(r"\s*(\d+)\.\s+(.*)", line)
        if m and m.group(2).strip() not in have:
            data["rulings"].append({"id": _new_id(data, f"old {m.group(1)}"), "kind": "lesson", "text": m.group(2).strip(),
                                    "source": source, "reviewed": False})
            n += 1
    plan.note(f"{n} lessons imported from {source}, all marked unreviewed: keep the ones that apply to this world, delete the rest")


def bump(game, data, rid, key, plan, reset=False):
    r = get(data, rid)
    if r["kind"] != "bonus":
        return plan.error(f"{rid} is a {r['kind']} ruling; only a bonus ruling is bumped")
    k = f"{rid}:{key}"
    data["uses"][k] = 0 if reset else min(r["max"], data["uses"].get(k, 0) + r["step"])
    plan.note(f"{rid} vs {key}: now +{data['uses'][k]}" + (" (the maximum)" if data["uses"][k] == r["max"] else ""))


def use(game, data, rid, plan):
    r = get(data, rid)
    if r["kind"] != "limited":
        return plan.error(f"{rid} is a {r['kind']} ruling; only a limited ruling is used up")
    k = f"{rid}:D{game.ledger['day']}" if r.get("per") == "day" else f"{rid}:{r.get('per')}"
    if data["uses"].get(k, 0) >= r.get("uses", 1):
        return plan.error(f"{r.get('item', rid)} was already used {data['uses'][k]}x this {r.get('per')}: it cannot be used again")
    data["uses"][k] = data["uses"].get(k, 0) + 1
    plan.note(f"{r.get('item', rid)} used ({data['uses'][k]}/{r.get('uses', 1)} this {r.get('per')})")
    plan.log(f"Used {r.get('item', rid)} ({data['uses'][k]}/{r.get('uses', 1)} this {r.get('per')})")


def mods(game, data, foe):
    """What to remember on the next roll against this foe."""
    total, lines = 0, []
    for r in data["rulings"]:
        if r["kind"] == "bonus":
            v = data["uses"].get(f"{r['id']}:{foe}", 0)
            total += v
            lines.append(f"{r['id']}: +{v} of +{r['max']} (+{r['step']} per {r.get('trigger', 'use')})")
        elif r["kind"] == "limited":
            k = f"{r['id']}:D{game.ledger['day']}" if r.get("per") == "day" else f"{r['id']}:{r.get('per')}"
            left = r.get("uses", 1) - data["uses"].get(k, 0)
            lines.append(f"{r.get('item', r['id'])}: {left} use(s) left this {r.get('per')}")
    return total, lines


def dice(game):
    """What the log says about the dice: luck, and how hard the rolls offered were."""
    rolls = []
    for line in game.log:
        m = re.search(r"roll (\w+) (\S*) ?d(\d+) need (-?\d+) \((\d+)%\)", line)
        if m:
            rolls.append({"action": m.group(1), "foe": m.group(2), "d": int(m.group(3)), "need": int(m.group(4)), "p": int(m.group(5))})
    if not rolls:
        return None
    won = sum(1 for r in rolls if r["d"] != 1 and (r["d"] == 20 or r["d"] >= r["need"]))
    fights = [r for r in rolls if r["foe"]]
    return {"n": len(rolls), "mean": round(sum(r["d"] for r in rolls) / len(rolls), 1), "won": won,
            "expected": round(sum(r["p"] for r in rolls) / 100, 1), "avg_chance": round(sum(r["p"] for r in rolls) / len(rolls)),
            "under_half": sum(1 for r in rolls if r["p"] < 50), "ones": sum(1 for r in rolls if r["d"] == 1),
            "twenties": sum(1 for r in rolls if r["d"] == 20),
            "defence": sum(1 for r in fights if r["action"] in DEFENCE), "attack": sum(1 for r in fights if r["action"] in ("hit", "throw", "grapple"))}


def audit(game, data):
    L, finds = game.ledger, []
    add = lambda sev, msg: finds.append((sev, msg))
    raw = [l for l in game.log if re.search(HARVEST, l) and l not in data["seen"]]
    if raw:
        add("WARN", f"{len(raw)} ruling(s) or correction(s) in the log are not in rulings.json: run `rules scan --write`")
    todo = [r["id"] for r in data["rulings"] if r.get("reviewed") is False]
    if todo:
        add("NOTE", f"{len(todo)} ruling(s) still unreviewed (ids: {', '.join(todo[:8])}{'...' if len(todo) > 8 else ''})")
    # skills and techniques that change no number
    known = " ".join([e.get("id", "") + " " + e.get("note", "") for e in L.get("effects", [])] + [r["text"] for r in data["rulings"]]).lower()
    for skill, val in L.get("skills", {}).items():
        names = [re.sub(r"\s*\(.*", "", skill)]
        inside = re.search(r"\((.*)\)", str(val))
        if inside:
            for clause in inside.group(1).split(";"):
                if "used early" in clause:
                    continue                                  # a one-off stunt, not an unlocked technique
                names += [n.strip() for n in re.sub(r"\bunlocked\b", "", clause).split(",")
                          if re.fullmatch(r"(?:[A-Z][\w'-]+ ?){1,4}", n.strip())]
        for n in names:
            words = [w for w in re.findall(r"[a-z]+", n.lower()) if len(w) > 3]
            if words and not any(w in known for w in words):
                add("WARN", f"'{n}' is on the sheet but no effect or ruling gives it a number: choosing it changes nothing on a roll. "
                    "Add an effect with `gm.py effect add`, or a ruling saying how it is applied")
    # is the engine's bookkeeping actually running?
    d = dice(game)
    if d and d["n"] >= 10:
        if not L.get("counters") and L.get("fatigue", 0) < d["n"]:
            add("WARN", f"the log has {d['n']} rolls but the ledger's use-counters are empty and fatigue is {L.get('fatigue', 0)}: "
                "rolls are not being run with `--apply`, so fatigue, mastery-by-use and milestones never move")
        if d["attack"] and d["defence"] / d["attack"] > 1.4:
            add("NOTE", f"in fights the log shows {d['defence']} defensive rolls for {d['attack']} attacks ({d['defence'] / d['attack']:.1f} per attack). "
                f"Fights cost about that many times the HP the forecast shows; use `fight <foe> --defences 2`, or rule one defence per exchange")
        if d["avg_chance"] < 45:
            add("NOTE", f"the average roll offered a {d['avg_chance']}% chance and {d['under_half']} of {d['n']} were under 50%. "
                "If that is harsher than intended, reward set-ups with gm.py's `shift=-3` (off-balance or unaware target) and weak points")
    for k, v in data["uses"].items():
        rid = k.split(":")[0]
        r = next((r for r in data["rulings"] if r["id"] == rid), None)
        if r and r["kind"] == "limited" and v > r.get("uses", 1):
            add("FAIL", f"{r.get('item', rid)} was used {v}x in one {r.get('per')}")
    return finds


def scene_findings(data, lines):
    out = []
    for r in data["rulings"]:
        if r.get("pattern"):
            for i, l in enumerate(lines, 1):
                if re.search(r["pattern"], l, re.I):
                    out.append((r.get("severity", "FAIL"), f"line {i}: breaks ruling '{r['id']}' ({r['source']}): {r['text'][:90]}"))
                    break
    return out
