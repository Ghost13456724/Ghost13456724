"""World clock: off-screen factions act on their own schedule.

factions.json = {"factions": {id: {"name", "goal", "steps": [step]}}, "traces": [...]}
step = {"id", "day", "text", "trace", "chance", "else_delay", "stops_if", "then": [{"after", ...}], "done"}
  text      what the faction does off-screen (GM-side)
  trace     what the world shows afterwards: a rumour, a headline, a missing person
  chance    percent that it works when its day comes (default 100); a miss delays it
  stops_if  what Mori would have had to do to prevent it; the GM must rule on these
  then      follow-up steps scheduled when this one succeeds
Text is GM-side and printed only with --gm.
"""
import random
import re


def load(game):
    return game.json("factions.json", None) or {"factions": {}, "traces": []}


def init(game):
    """Seed faction names from the bible's 'powers that be' section; agendas are for the GM bot to write."""
    import os
    data = load(game)
    bible = next((game.text(n) for n in sorted(os.listdir(game.dir)) if "BIBLE" in n.upper() and n.endswith(".md") and "draft" not in n), "")
    m = re.search(r"^## [IVXL]+\. The powers that be.*?$(.*?)(?=^## |\Z)", bible, re.M | re.S)
    added = []
    for line in (m.group(1) if m else "").splitlines():
        b = re.match(r"(?:- |\| ?)\*\*([^*]+?)[,.:]?\*\*", line)
        if b:
            fid = re.sub(r"[^a-z0-9]+", "_", b.group(1).lower()).strip("_")
            if fid and fid not in data["factions"]:
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                goal = re.sub(r"\*\*", "", cells[2]) if line.lstrip().startswith("|") and len(cells) >= 3 else ""
                data["factions"][fid] = {"name": b.group(1).strip(), "goal": goal, "steps": []}
                added.append(b.group(1).strip())
    return data, added


def pending(data):
    for fid, f in data["factions"].items():
        for s in f.get("steps", []):
            if not s.get("done"):
                yield fid, f, s


def status(game, data, gm=False, ahead=7):
    day, rows, finds = game.ledger["day"], [], []
    for fid, f in data["factions"].items():
        todo = sorted((s for s in f.get("steps", []) if not s.get("done")), key=lambda s: s["day"])
        done = sum(1 for s in f.get("steps", []) if s.get("done"))
        nxt = f"next D{todo[0]['day']}" if todo else "nothing planned"
        rows.append(f"  {f['name']:<28} {done} done, {len(todo)} planned, {nxt}" + (f" | goal: {f.get('goal', '')}" if gm else ""))
        if gm:
            for s in todo:
                rows.append(f"      D{s['day']} {s['id']}: {s['text']}" + (f" [stops if: {s['stops_if']}]" if s.get("stops_if") else ""))
        if not todo:
            finds.append(("WARN", f"{f['name']} has nothing planned: off-screen it is standing still"))
        for s in todo:
            if s["day"] < day:
                finds.append(("WARN", f"{f['name']} had a step due D{s['day']} that never ran: run `world tick`"))
    if not data["factions"]:
        finds.append(("WARN", "no factions: run `world init`, then have the world-clock bot write their agendas"))
    soon = [e for e in game.events if isinstance(e.get("day"), (int, float)) and day <= e["day"] <= day + ahead and not e.get("done")]
    steps = [s for _, _, s in pending(data) if day <= s["day"] <= day + ahead]
    if not soon and not steps:
        finds.append(("NOTE", f"nothing at all is scheduled in the next {ahead} days: the world is waiting on Mori"))
    fresh = [t for t in data.get("traces", []) if not t.get("surfaced")]
    if fresh:
        rows.append(f"  traces Mori has not run into yet: {len(fresh)}")
        if gm:
            for t in fresh:
                rows.append(f"      {t['id']} D{t['day']} {t['faction']}: {t['trace']}")
    return rows, finds


def tick(game, data, plan, rule=None, rng=None):
    """Run every step whose day has come. rule = {step id: 'stopped' | 'happened'} for steps Mori could have prevented."""
    rng, rule, day = rng or random.Random(), rule or {}, game.ledger["day"]
    ran = 0
    for fid, f, s in sorted(pending(data), key=lambda x: x[2]["day"]):
        if s["day"] > day:
            continue
        ran += 1
        if s.get("stops_if") and s["id"] not in rule:
            plan.note(f"HOLD {s['id']} ({f['name']}, D{s['day']}): Mori could have stopped this. Rule on it: "
                      f"`world tick --rule {s['id']}=stopped` or `={'happened'}` (see it with `world status --gm`)")
            continue
        if rule.get(s["id"]) == "stopped":
            s["done"], s["result"] = game.stamp(), "stopped by Mori"
            plan.note(f"{s['id']} ({f['name']}): stopped by Mori; its follow-ups are cancelled")
            plan.log(f"[W] {f['name']}: plan {s['id']} was stopped by Mori")
            continue
        roll = rng.randint(1, 100)
        if roll > s.get("chance", 100):
            s["day"] = day + s.get("else_delay", 2)
            s["misses"] = s.get("misses", 0) + 1
            plan.note(f"{s['id']} ({f['name']}): failed its roll ({roll} > {s.get('chance')}%), tries again D{s['day']}")
            continue
        s["done"], s["result"] = game.stamp(), "happened"
        plan.note(f"{s['id']} ({f['name']}): happened off-screen" + (f" (rolled {roll} <= {s['chance']}%)" if "chance" in s else ""))
        plan.log(f"[W] {f['name']}: {s['text']}")
        if s.get("trace"):
            data.setdefault("traces", []).append({"id": f"t{len(data.get('traces', [])) + 1}", "day": day, "faction": f["name"],
                                                  "trace": s["trace"], "surfaced": None})
        for n, nxt in enumerate(s.get("then", []), 1):
            step = {k: v for k, v in nxt.items() if k != "after"}
            step.setdefault("id", f"{s['id']}.{n}")
            step["day"] = day + nxt.get("after", 1)
            f["steps"].append(step)
            plan.note(f"  -> follow-up {step['id']} scheduled for D{step['day']}")
    if not ran:
        plan.note(f"no faction step is due on or before D{day}")


def surface(data, tid, stamp, plan):
    for t in data.get("traces", []):
        if t["id"] == tid:
            t["surfaced"] = stamp
            return plan.note(f"trace {tid} marked as seen by Mori at {stamp}")
    plan.error(f"no trace {tid}")
