"""Clue ladder keeper: clues before truths, one rung at a time.

clues.json is a GM-side file. Its text is never printed unless --gm is given,
so running these commands in front of the player spoils nothing.
"""
import re

NEEDED = 2   # clues that must be on the page before a rung's truth may be revealed


def load(game):
    return game.json("clues.json", None) or {"rung": 0, "needed": NEEDED, "ladder": [], "pool": []}


def init(game):
    """Seed from GM_SECRETS (the numbered reveal ladder) and the arc cards ('Clues to place' bullets)."""
    data = load(game)
    if not data["ladder"]:
        sec = game.text("GM_SECRETS.md")
        m = re.search(r"^## \d+\. Reveal ladder.*?$(.*?)(?=^## |\Z)", sec, re.M | re.S | re.I)
        for line in (m.group(1) if m else "").splitlines():
            r = re.match(r"\s*(\d+)\.\s+(.*)", line)
            if r:
                data["ladder"].append({"rung": int(r.group(1)), "truth": r.group(2).strip(), "patterns": [], "clues": []})
    import os
    have = {c["text"] for c in data["pool"]} | {c["text"] for r in data["ladder"] for c in r["clues"]}
    n = len(have)
    for name in sorted(os.listdir(game.dir)):
        if name.startswith("ARC_") and name.endswith(".md"):
            m = re.search(r"^## Clues to place.*?$(.*?)(?=^## |\Z)", game.text(name), re.M | re.S)
            for line in (m.group(1) if m else "").splitlines():
                b = re.match(r"- (.+)", line)
                if b and b.group(1).strip() not in have:
                    n += 1
                    data["pool"].append({"id": f"c{n}", "text": b.group(1).strip(), "placed": None, "arc": name[:6]})
                    have.add(b.group(1).strip())
    data["rung"] = max([data.get("rung", 0)] + [int(x) for line in game.log for x in re.findall(r"rung (\d+)", line)])
    return data


def all_clues(data):
    for r in data["ladder"]:
        for c in r["clues"]:
            yield r["rung"], c
    for c in data["pool"]:
        yield None, c


def status(data, gm=False):
    rows, finds = [], []
    need = data.get("needed", NEEDED)
    rows.append(f"reveal ladder: rung {data['rung']} of {len(data['ladder'])}; {need} placed clues open a rung")
    for r in data["ladder"]:
        placed = [c for c in r["clues"] if c.get("placed")]
        state = "REVEALED" if r["rung"] <= data["rung"] else "next" if r["rung"] == data["rung"] + 1 else "locked"
        rows.append(f"  rung {r['rung']:>2} {state:<8} clues placed {len(placed)}/{len(r['clues'])}, watch patterns {len(r['patterns'])}"
                    + (f"  | {r['truth']}" if gm else ""))
        if gm:
            for c in r["clues"]:
                rows.append(f"       {c['id']} [{'placed ' + c['placed'] if c.get('placed') else 'unplaced'}] {c['text']}")
        if r["rung"] <= data["rung"] and len(placed) < need and r["clues"]:
            finds.append(("WARN", f"rung {r['rung']} was revealed with only {len(placed)} clue(s) placed"))
        if r["rung"] == data["rung"] + 1:
            if not r["clues"]:
                finds.append(("WARN", f"the next rung ({r['rung']}) has no clues written: it cannot be reached fairly"))
            elif len(placed) >= need:
                finds.append(("NOTE", f"rung {r['rung']} is ready: {len(placed)} clues are on the page, so its truth may now be shown"))
    blind = [str(r["rung"]) for r in data["ladder"] if r["rung"] > data["rung"] and not r["patterns"]]
    if blind:
        finds.append(("NOTE", f"rungs {', '.join(blind)} have no watch patterns, so the scene check cannot catch a leak of them"))
    loose = [c for c in data["pool"]]
    if loose:
        rows.append(f"  unassigned clues: {len(loose)} ({sum(1 for c in loose if c.get('placed'))} placed)")
        if gm:
            for c in loose:
                rows.append(f"       {c['id']} [{'placed ' + c['placed'] if c.get('placed') else 'unplaced'}] {c['text']}")
        finds.append(("NOTE", f"{len(loose)} clue(s) are not assigned to a rung; the keeper should assign them"))
    return rows, finds


def next_clues(data, gm=False):
    """Unplaced clues for the next rung, then loose ones: what the next scene could carry."""
    out = []
    for rung, c in all_clues(data):
        if not c.get("placed") and (rung is None or rung == data["rung"] + 1):
            out.append(f"{c['id']} (rung {rung if rung else '?'})" + (f": {c['text']}" if gm else ""))
    return out


def place(data, cid, stamp, plan):
    for rung, c in all_clues(data):
        if c["id"] == cid:
            if c.get("placed"):
                plan.note(f"{cid} was already placed {c['placed']}")
            c["placed"] = stamp
            plan.note(f"clue {cid} placed at {stamp}" + (f" (rung {rung})" if rung else ""))
            return
    plan.error(f"no clue with id {cid}")


def reveal(data, rung, plan, force=False):
    need = data.get("needed", NEEDED)
    row = next((r for r in data["ladder"] if r["rung"] == rung), None)
    if not row:
        return plan.error(f"no rung {rung}")
    if rung <= data["rung"]:
        return plan.note(f"rung {rung} is already revealed")
    placed = sum(1 for c in row["clues"] if c.get("placed"))
    problems = []
    if rung != data["rung"] + 1:
        problems.append(f"it skips from rung {data['rung']} to {rung}")
    if placed < need:
        problems.append(f"only {placed} of its clues are on the page ({need} needed)")
    if problems and not force:
        return plan.error(f"cannot reveal rung {rung}: " + " and ".join(problems) + ". Place clues first, or --force if the player earned it another way")
    data["rung"] = rung
    plan.note(f"reveal ladder -> rung {rung}" + (" (forced: " + "; ".join(problems) + ")" if problems else ""))
    plan.log(f"Reveal ladder: rung {rung} shown in play" + (" (forced)" if problems else ""))


def watch_list(data):
    return [{"pattern": p, "rung": r["rung"]} for r in data["ladder"] for p in r["patterns"]]
