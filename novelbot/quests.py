"""Quest log: the System's tasks, their rewards and their prices.

quests.json = [{"id", "kind": daily|hidden|emergency|chain|trial, "title", "text", "given", "due": {"day", "time"},
                "steps": [{"text", "done"}], "reward": {"xp", "points", "won", "items", "boxes"}, "price", "status", "secret"}]

Experience is not only for kills. A reward's "xp" is either a number or a size, and a size is a share of the
level Mori is on (100 x level to level up), so a quest stays worth doing as he grows:
    small 15%   medium 35%   large 60%   trial 100%
Paying out goes through gm.py (`xp`, `set points`, `item`), so level-ups and full restores follow its rules.
"""
import subprocess
import sys

SIZES = {"small": 15, "medium": 35, "large": 60, "trial": 100}
KINDS = ("daily", "hidden", "emergency", "chain", "trial", "main")


def load(game):
    return game.json("quests.json", None) or []


def get(data, qid):
    q = next((q for q in data if q["id"] == qid), None)
    if q is None:
        raise KeyError(f"no quest '{qid}'")
    return q


def xp_value(L, xp):
    if isinstance(xp, str) and xp in SIZES:
        return round(100 * L["level"] * SIZES[xp] / 100)
    return int(xp or 0)


def add(game, data, qid, fields, plan):
    if any(q["id"] == qid for q in data):
        return plan.error(f"quest '{qid}' already exists")
    kind = fields.get("kind", "hidden")
    if kind not in KINDS:
        return plan.error(f"kind must be one of {', '.join(KINDS)}")
    if not fields.get("title"):
        return plan.error("a quest needs a title")
    reward = {k: fields[k] for k in ("xp", "points", "won", "boxes") if k in fields}
    for k in ("points", "won", "boxes"):
        if k in reward:
            reward[k] = int(reward[k])
    if "items" in fields:
        reward["items"] = [x.strip() for x in fields["items"].split("|")]
    if "xp" in reward and reward["xp"] not in SIZES:
        reward["xp"] = int(reward["xp"])
    due = None
    if "due" in fields:                                   # due=D4 or due=D4@17:00
        d, _, t = fields["due"].lstrip("D").partition("@")
        due = {"day": int(d), "time": t or "23:59"}
    q = {"id": qid, "kind": kind, "title": fields["title"], "text": fields.get("text", ""), "given": game.stamp(), "due": due,
         "steps": [{"text": s.strip(), "done": False} for s in fields.get("steps", "").split("|") if s.strip()],
         "reward": reward, "price": fields.get("price", ""), "status": "open",
         "secret": str(fields.get("secret", "")).lower() in ("1", "true", "yes")}
    data.append(q)
    plan.note(f"quest + {qid} [{kind}] {q['title']}" + (" (secret: not shown to the player until it triggers)" if q["secret"] else ""))
    if not reward:
        plan.note("  note: no reward set. Every quest has a reward and a price")


def window(L, q):
    """The System message for a finished quest, and the gm.py commands that pay it."""
    r, lines, cmds = q.get("reward", {}), [f"[Quest complete: {q['title']}.]"], []
    xp = xp_value(L, r.get("xp"))
    if xp:
        lines.append(f"[Experience gained: {xp}.]")
        cmds.append(["xp", f"+{xp}", f"quest: {q['title']}"])
    if r.get("points"):
        lines.append(f"[Reward: {r['points']} stat points.]")
        cmds.append(["set", f"points=+{r['points']}"])
    if r.get("won"):
        lines.append(f"[Reward: {r['won']:,} won.]")
        cmds.append(["set", f"won=+{r['won']}"])
    if r.get("boxes"):
        lines.append(f"[Reward: Random Box x{r['boxes']}.]")
        cmds.append(["set", f"boxes=+{r['boxes']}"])
    for it in r.get("items", []):
        lines.append(f"[Reward: {it}.]")
        cmds.append(["item", "+", it])
    return lines, cmds


def finish(game, data, qid, plan, write, failed=False):
    q = get(data, qid)
    if q["status"] != "open":
        return plan.error(f"quest '{qid}' is already {q['status']}")
    todo = [s["text"] for s in q.get("steps", []) if not s["done"]]
    if todo and not failed:
        return plan.error(f"quest '{qid}' still has open steps: {'; '.join(todo)}")
    q["status"], q["closed"] = ("failed" if failed else "done"), game.stamp()
    if failed:
        plan.note(f"[Quest failed: {q['title']}.]" + (f"  PRICE: {q['price']}" if q.get("price") else "  (no price was set)"))
        plan.log(f"Quest FAILED: {q['title']}" + (f" -> {q['price']}" if q.get("price") else ""))
        return
    lines, cmds = window(game.ledger, q)
    for line in lines:
        plan.note(line)
    plan.log(f"Quest done: {q['title']} ({', '.join(c[0] + ' ' + c[1] for c in cmds) or 'no reward'})")
    for c in cmds:
        if write:
            r = subprocess.run([sys.executable, "-B", game.path("gm.py")] + c, cwd=game.dir, capture_output=True, text=True)
            out = (r.stdout + r.stderr).strip().splitlines()
            plan.note("  gm.py " + " ".join(c[:2]) + " -> " + (out[0] if out else "ok"))
            for extra in out[1:]:
                if "leveled up" in extra or "!!" in extra:
                    plan.note("    " + extra.strip())
        else:
            plan.note("  would run: gm.py " + " ".join(f'"{x}"' if " " in x else x for x in c))


def listing(game, data, gm=False):
    L, rows = game.ledger, []
    dq = L.get("daily", {})
    if L.get("flags", {}).get("system"):
        rows.append(f"  daily      Daily Discipline: {'done today' if dq.get('done_today') else 'NOT DONE, deadline 00:00'} "
                    f"(completed {dq.get('count', 0)}, missed {dq.get('missed', 0)})")
    for q in data:
        if q.get("secret") and q["status"] == "open" and not gm:
            continue
        steps = q.get("steps", [])
        prog = f" {sum(s['done'] for s in steps)}/{len(steps)}" if steps else ""
        due = f" due D{q['due']['day']} {q['due']['time']}" if q.get("due") else ""
        rew = ", ".join(f"{k} {v}" for k, v in q.get("reward", {}).items())
        rows.append(f"  {q['status']:<6} {q['kind']:<9} {q['id']}: {q['title']}{prog}{due}" + (f" | reward: {rew}" if rew else "")
                    + (f" | price: {q['price']}" if q.get("price") and (gm or not q.get("secret")) else ""))
    hidden = sum(1 for q in data if q.get("secret") and q["status"] == "open")
    if hidden and not gm:
        rows.append(f"  (+{hidden} secret quest(s) not shown; use --gm)")
    return rows


def findings(game, data):
    L, out = game.ledger, []
    for q in data:
        if q["status"] != "open":
            continue
        if q.get("due") and q["due"]["day"] < L["day"]:
            out.append(("WARN", f"quest '{q['id']}' was due D{q['due']['day']} and is still open: complete or fail it"))
        if not q.get("reward"):
            out.append(("NOTE", f"quest '{q['id']}' has no reward"))
        if not q.get("price") and q["kind"] in ("daily", "emergency", "trial"):
            out.append(("NOTE", f"quest '{q['id']}' ({q['kind']}) has no price for failure"))
    if not data:
        out.append(("NOTE", "the quest log is empty: the System has set no task besides the daily"))
    return out
