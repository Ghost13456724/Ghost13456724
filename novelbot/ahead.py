"""Lookahead: is there a fair way through what is coming?

Looks a few days ahead at everything Mori is committed to and says which of it he cannot
survive or afford as things stand, and what honest ways back exist. It never changes a number:
the point is to see a dead end coming early enough to put a real choice in front of the player.
"""
import re

from . import beats as BE
from . import quests as QU
from . import scale as S
from . import world as W


def _amount(text):
    m = re.search(r"(\d{1,3}(?:,\d{3})+|\d{4,})", text)
    return int(m.group(1).replace(",", "")) if m else None


def report(game, days=3, sims=300):
    L, out, ways = game.ledger, [], []
    add = lambda sev, msg: out.append((sev, msg))
    day = L["day"]
    hp = L["hp"] / max(1, L["hp_max"])
    inj = L.get("injuries", [])
    pen = sum(i["mod"] for i in inj)
    cond = f"HP {L['hp']}/{L['hp_max']}, fatigue {L.get('fatigue', 0)}, {len(inj)} injuries ({pen:+d} on every roll)" if inj else \
        f"HP {L['hp']}/{L['hp_max']}, fatigue {L.get('fatigue', 0)}, no injuries in the ledger"
    add("NOTE", "Mori now: " + cond)

    # what he can actually fight today
    now, rested = [], []
    for fid, f in game.foes.items():
        try:
            m = S.matchup(game, fid, sims=sims)
        except KeyError:
            continue
        if m["fresh"]["win"] >= 50:
            rested.append(f["name"])
            if m["now"] and m["now"]["win"] >= 50:
                now.append(f["name"])
    if rested and len(now) < len(rested):
        add("WARN" if not now else "NOTE", f"of the {len(rested)} foes a rested Mori beats more often than not, he beats {len(now)} as he is right now"
            + ("" if now else ": any fight today is likely his last"))

    # the daily, and what missing it costs
    dq = L.get("daily", {})
    if L.get("flags", {}).get("system") and not L.get("flags", {}).get("system_deleted") and not dq.get("done_today"):
        h, m = (int(x) for x in str(L.get("time", "06:00")).split(":"))
        left = 24 - h - m / 60
        hard = pen <= -2 or hp < 0.3
        add("WARN" if hard else "NOTE", f"Daily Discipline is not done; {left:.1f} hours to midnight"
            + (". In his condition the physical tasks are in doubt: this needs a scene, not an assumption" if hard else ""))
        zone = [(fid, f) for fid, f in game.foes.items() if f.get("type") == "penalty" or "penalty zone" in f.get("notes", "").lower()
                or any(k.startswith(fid + "_") or fid.startswith(k + "_") for k, x in game.foes.items() if x.get("type") == "penalty")]
        worst = None
        for fid, f in zone:
            m = S.matchup(game, fid, sims=sims)
            w = m["now"]["win"] if m["now"] else 0
            worst = w if worst is None else max(worst, w)
        if zone:
            add("FAIL" if (worst or 0) < 25 else "WARN", f"if it is missed: the Penalty Zone. Against what lives there his best fight right now is {worst}%"
                + (". Sent there as he is, he most likely dies: he needs a way to finish the daily, or a way to survive without fighting" if (worst or 0) < 25 else ""))
        ways.append("finish the Daily Discipline: full recovery, +3 points and a box")

    # dated obligations
    money = L.get("won", 0)
    for e in sorted((e for e in game.events if isinstance(e.get("day"), (int, float)) and not e.get("done") and day <= e["day"] <= day + days),
                    key=lambda e: e["day"]):
        amt = _amount(e["text"]) if re.search(r"rent|due|fee|pay|debt|bill", e["text"], re.I) else None
        if amt and amt > money:
            add("WARN", f"D{e['day']} {e.get('time', '')}: {e['text']} — he has {money:,} won, {amt - money:,} short")
        else:
            add("NOTE", f"D{e['day']} {e.get('time', '')}: {e['text']}")
    for q in QU.load(game):
        if q["status"] == "open" and q.get("due") and day <= q["due"]["day"] <= day + days:
            todo = sum(1 for s in q.get("steps", []) if not s["done"])
            add("WARN" if q.get("price") else "NOTE", f"quest '{q['title']}' due D{q['due']['day']} {q['due']['time']}"
                + (f", {todo} step(s) open" if todo else "") + (f"; price: {q['price']}" if q.get("price") and not q.get("secret") else ""))
    steps = [s for _, _, s in W.pending(W.load(game)) if day <= s["day"] <= day + days]
    if steps:
        add("NOTE", f"{len(steps)} off-screen faction step(s) come due in this window (`world status --gm`)")

    # the plan's pace
    bdata = BE.load(game)
    p = BE.pace(game, bdata)
    if p and p["xp"]:
        add("WARN" if p["per_day"] > 100 * L["level"] else "NOTE", f"the arc plan expects about Lv{p['level']} by D{p['day']}: {p['xp']:,} XP in {p['days']} days "
            f"({p['per_day']:,} a day; a level is {100 * L['level']:,} right now). Kills alone will not do it: quests and trials have to pay XP")
    late = [f for f in BE.status(game, bdata)[1] if f[0] == "WARN"]
    if late:
        add("NOTE", f"{len(late)} planned beat item(s) are past their window and still pending (`beats status --gm`)")

    # honest ways back
    need = 100 * L["level"] - L.get("xp", 0)
    ways.append(f"level up: {need} XP away, and a level-up restores him fully")
    try:
        from . import people as PE
        healers = [k for k, x in PE.load(game)["people"].items() if re.search(r"healer|nurse|doctor|acupunctur", x.get("role", ""), re.I) and x.get("status") == "alive"]
        if healers:
            ways.append("people who can treat him: " + ", ".join(healers[:4]))
    except Exception:
        pass
    pots = [i for i in L.get("items", []) if re.search(r"potion|draught|elixir|pill|bandage", i, re.I)]
    if pots:
        ways.append("items: " + "; ".join(pots))
    ways.append("time: sleep heals slowly (GM ruling on how much per night)")
    open_q = [q for q in QU.load(game) if q["status"] == "open" and q.get("reward", {}).get("xp") and not q.get("secret")]
    if open_q:
        ways.append("open quests that pay XP: " + ", ".join(q["title"] for q in open_q[:4]))
    return out, ways
