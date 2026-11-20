"""Beat tracker: which planned story beats have happened.

Arc cards list beats that "happen unless the player changes them". beats.json records, for each
planned item, whether it was delivered, changed by the player, skipped, or is still pending,
so a planned event cannot be silently forgotten. The text is GM-side: shown only with --gm.
"""
import os
import re

STATES = ("pending", "delivered", "changed", "skipped")


def load(game):
    return game.json("beats.json", None) or {"beats": []}


def init(game, data):
    """Read every ARC_*.md: '## Beat 4 — The climb (D3-D30, Lv1 → ~12)' and its top-level bullets."""
    have = {b["text"] for b in data["beats"]}
    added = 0
    for name in sorted(os.listdir(game.dir)):
        if not (name.startswith("ARC_") and name.endswith(".md")):
            continue
        arc = re.match(r"ARC_(\d+)", name).group(1)
        beat = None
        for line in game.text(name).splitlines():
            h = re.match(r"## Beat (\d+)\s*[—–-]\s*(.*)", line)
            if h:
                head = h.group(2)
                days = re.search(r"D(\d+)(?:\s*-\s*D?(\d+))?", head)
                lv = re.search(r"Lv\s*~?(\d+)(?:\s*(?:→|->|-)\s*~?(\d+))?", head)
                beat = {"arc": arc, "beat": int(h.group(1)), "title": re.sub(r"\s*\(.*", "", head).strip(),
                        "from": int(days.group(1)) if days else None,
                        "to": int(days.group(2) or days.group(1)) if days else None,
                        "level": int(lv.group(2) or lv.group(1)) if lv else None, "n": 0}
                continue
            if line.startswith("## "):
                beat = None
            b = re.match(r"- (.+)", line)
            if beat and b and b.group(1).strip() not in have:
                beat["n"] += 1
                data["beats"].append({"id": f"a{int(arc)}b{beat['beat']}.{beat['n']}", "arc": arc, "beat": beat["beat"],
                                      "title": beat["title"], "from": beat["from"], "to": beat["to"], "level": beat["level"],
                                      "text": b.group(1).strip(), "optional": bool(re.match(r"\*?\*?Optional|.*\(optional", b.group(1), re.I)),
                                      "status": "pending", "note": "", "stamp": None})
                have.add(b.group(1).strip())
                added += 1
    return added


def mark(data, bid, status, note, stamp, plan):
    b = next((b for b in data["beats"] if b["id"] == bid), None)
    if b is None:
        return plan.error(f"no beat item '{bid}'")
    if status not in STATES:
        return plan.error(f"status must be one of {', '.join(STATES)}")
    if status in ("changed", "skipped") and not note:
        return plan.error(f"'{status}' needs a note: what the player did instead, or why it no longer happens")
    b.update(status=status, note=note, stamp=stamp)
    plan.note(f"{bid} ({b['title']}): {status}" + (f" — {note}" if note else ""))


def status(game, data, gm=False):
    day, rows, finds, groups = game.ledger["day"], [], [], {}
    for b in data["beats"]:
        groups.setdefault((b["arc"], b["beat"]), []).append(b)
    for (arc, n), items in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        b = items[0]
        win = f"D{b['from']}" + (f"-D{b['to']}" if b["to"] != b["from"] else "") if b["from"] is not None else "no date"
        count = {s: sum(1 for i in items if i["status"] == s) for s in STATES}
        when = "past" if b["to"] is not None and b["to"] < day else "now" if b["from"] is not None and b["from"] <= day else "ahead"
        rows.append(f"  arc {int(arc)} beat {n} ({win}, {when})" + (f" {b['title']}" if gm else "") + ": "
                    + ", ".join(f"{v} {k}" for k, v in count.items() if v) + (f" | plan expects ~Lv{b['level']}" if b["level"] else ""))
        for i in items:
            if gm:
                rows.append(f"      {i['id']} [{i['status']}] {i['text'][:150]}" + (f"  <- {i['note']}" if i["note"] else ""))
            if i["status"] == "pending" and not i["optional"] and i["to"] is not None and i["to"] < day:
                finds.append(("WARN", f"{i['id']} was planned for {win} and is still pending on D{day}: deliver it, or mark it changed or skipped with the reason"))
    if not data["beats"]:
        finds.append(("NOTE", "no beats tracked: run `beats init --write`"))
    return rows, finds


def pace(game, data):
    """The next level the plan expects, and what that needs from here."""
    L = game.ledger
    ahead = sorted({(b["to"], b["level"]) for b in data["beats"] if b["level"] and b["to"] is not None and b["to"] >= L["day"]})
    if not ahead:
        return None
    day, level = ahead[0]
    need = sum(100 * lv for lv in range(L["level"], level)) - L.get("xp", 0) if level > L["level"] else 0
    days = max(1, day - L["day"])
    return {"day": day, "level": level, "xp": max(0, need), "per_day": round(max(0, need) / days), "days": days}
