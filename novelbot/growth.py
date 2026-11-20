"""Growth check: skills improve because of what Mori did, not because the player asked.

Every roll gm.py logged is counted. Each track turns a kind of experience into levels of a skill;
when the count passes the next threshold the growth is DUE and the tool prints the System message
and the gm.py command. growth.json can replace or extend the default tracks.

track = {"skill": name on the sheet, "counts": {"actions": [...], "result": "success|fail|any"},
         "levels": {level: count needed}, "new": bool (may be acquired if absent), "why": System wording}
"""
import re

DEFAULT = [
    {"skill": "Renewal Taekwondo", "counts": {"actions": ["hit", "dodge", "read", "grapple", "chase", "throw"], "result": "any"},
     "levels": {"4": 20, "5": 60, "6": 140, "7": 300, "8": 600},
     "why": "Through repeated combat, the skill \"Renewal Taekwondo\" has improved.",
     "note": "from mastery 5 up, the skill tree also asks for a trial or a teacher: growth is due, the GM supplies the moment"},
    {"skill": "Erase the Rhythm", "new": True, "counts": {"actions": ["read"], "result": "success"},
     "levels": {"1": 1, "2": 6, "3": 15, "4": 35, "5": 70},
     "why": "You have read an enemy's rhythm and struck within it."},
    {"skill": "Endurance", "new": True, "counts": {"actions": ["dodge", "read", "endure"], "result": "fail"},
     "levels": {"1": 8, "2": 20, "3": 45, "4": 90, "5": 160},
     "why": "You have endured what should have stopped you."},
    {"skill": "Keen Senses", "new": True, "counts": {"actions": ["sense"], "result": "success"},
     "levels": {"1": 5, "2": 15, "3": 40},
     "why": "You have noticed what was hidden, again and again."},
]


def tracks(game):
    return game.json("growth.json", None) or DEFAULT


def tally(game):
    out = {}
    for line in game.log:
        m = re.search(r"roll (\w+) (\S*) ?d(\d+) need (-?\d+)", line)
        if m:
            d, need = int(m.group(3)), int(m.group(4))
            ok = d != 1 and (d == 20 or d >= need)
            out.setdefault(m.group(1), {"success": 0, "fail": 0})["success" if ok else "fail"] += 1
    return out


def level_on_sheet(L, skill):
    for name, val in L.get("skills", {}).items():
        if skill.lower() in name.lower():
            m = re.match(r"\s*(\d+)", str(val))
            return int(m.group(1)) if m else 1
    return 0


def check(game):
    """Returns (due, progress): growth owed right now, and how far each track is from its next level."""
    T, due, progress = tally(game), [], []
    for t in tracks(game):
        c = t["counts"]
        n = sum(sum(v for k, v in T.get(a, {}).items() if c.get("result", "any") in ("any", k)) for a in c["actions"])
        have = level_on_sheet(game.ledger, t["skill"])
        if not have and not t.get("new"):
            continue
        earned = max([int(lv) for lv, need in t["levels"].items() if n >= need] + [0])
        nxt = min((int(lv) for lv in t["levels"] if int(lv) > max(have, earned)), default=None)
        if earned > have:
            cmd = f'python3 gm.py skill "{t["skill"]}" "{earned}"'
            msg = [f"[{t['why']}]", f"[{t['skill']}: {'Lv.' + str(have) + ' → ' if have else 'acquired, '}Lv.{earned}]"]
            due.append({"skill": t["skill"], "from": have, "to": earned, "count": n, "message": msg, "cmd": cmd, "note": t.get("note", "")})
        if nxt:
            progress.append(f"{t['skill']}: {n} of {t['levels'][str(nxt)]} toward Lv.{nxt}")
    return due, progress
