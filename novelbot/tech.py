"""Arsenal and fight referee.

The player chooses what Mori is trying to do (attack, defend, read). Mori chooses
how: every technique he owns is tried against gm.py's numbers and the best one
for this moment is used. Picking the flavour of kick is his job, not the player's.

techniques.json = {id: {"name", "action": "hit|dodge|read", "strike", "needs": {"skill", "mastery"},
                        "effect": {<gm.py effect payload>}, "when": {"unshown", "read", "opening"},
                        "cost": {"fatigue", "hp_pct"}, "opens": bool, "note"}}
fight.json      = the running state of one fight: what the foe has seen, whether Mori has read its
                  rhythm, whether it is off balance, how many exchanges he has lost.
"""
import copy
import re

from . import rulings as RU
from . import scale as S

PREFIX = "t_"
INTENT = {"attack": "hit", "defend": "dodge", "read": "read"}
PROPOSED = {
    "three_stage_hoechook": {
        "name": "Three-Stage Hoechook", "action": "hit", "strike": "kick", "needs": {"skill": "Renewal Taekwondo", "mastery": 4},
        "effect": {"kp_mult": 1.5, "dc_shift": 2}, "cost": {"fatigue": 3},
        "note": "three kicks in one rotation: half again the damage, harder to land, tiring"},
    "lowest_hoechook": {
        "name": "Lowest Hoechook", "action": "hit", "strike": "kick", "needs": {"skill": "Renewal Taekwondo", "mastery": 4},
        "effect": {"dc_shift": -3, "kp_mult": 0.8}, "when": {"unshown": True}, "opens": True,
        "note": "a sweep swapped in where they expect a Hoechook: easy to land the first time a foe sees it, lighter, and a clean hit puts the foe off balance"},
    "counter_hoechook": {
        "name": "Counter Hoechook (Erase the Rhythm)", "action": "hit", "strike": "kick", "needs": {"skill": "Erase the Rhythm"},
        "effect": {"tech": 1, "kp_mult": 1.2}, "when": {"read": True},
        "note": "once he has read the enemy's beat: no tell, and it lands as they commit"},
    "x_guard": {
        "name": "X Guard", "action": "dodge", "needs": {"skill": "Renewal Taekwondo", "mastery": 1},
        "effect": {"taken_mult": 0.7, "dc_shift": 1}, "note": "crossed fists: takes the hit on the forearms instead of slipping it; less damage, no escape"},
    "erase_the_rhythm": {
        "name": "Erase the Rhythm", "action": "read", "needs": {"skill": "Erase the Rhythm"},
        "effect": {"tech": 1}, "note": "hold the breath, go loose: reading from stillness"},
}


def load(game):
    return game.json("techniques.json", None) or {}


def fight_state(game):
    return game.json("fight.json", None)


def mastery(L, skill):
    for name, val in L.get("skills", {}).items():
        if skill.lower() in name.lower():
            m = re.match(r"\s*(\d+)", str(val))
            return int(m.group(1)) if m else 1
    return None


def owned(L, techs):
    out = {}
    for tid, t in techs.items():
        need = t.get("needs", {})
        have = mastery(L, need["skill"]) if need.get("skill") else 99
        if have is not None and have >= need.get("mastery", 1):
            out[tid] = t
    return out


def with_effects(L, techs):
    """A copy of the sheet in which every owned technique exists as a callable gm.py effect."""
    L = copy.deepcopy(L)
    have = {e["id"] for e in L.get("effects", [])}
    for tid, t in owned(L, techs).items():
        if PREFIX + tid not in have:
            L.setdefault("effects", []).append(dict(t.get("effect", {}), id=PREFIX + tid, src="technique", on=True, passive=False,
                                                    when={"actions": [t["action"]]}, note=t.get("note", "")))
    return L


def usable(t, state):
    w = t.get("when", {})
    if w.get("unshown") and state and t["_id"] in state.get("shown", []):
        return False
    if w.get("read") and not (state and state.get("read")):
        return False
    if w.get("opening") and not (state and state.get("opening")):
        return False
    return True


def options(game, L, techs, action, foe_id, state=None, mod=0, shift=0):
    """Every way Mori could do this action right now, best first."""
    L2, out = with_effects(L, techs), []
    cands = [(None, None)] + [(tid, dict(t, _id=tid)) for tid, t in owned(L, techs).items() if t["action"] == action]
    for tid, t in cands:
        if t and not usable(t, state):
            continue
        kw = {"use": (PREFIX + tid,)} if tid else {}
        if t and t.get("strike"):
            kw["strike"] = t["strike"]
        variants = [False, True] if action == "hit" and game.foes[foe_id].get("T_weak") else [False]
        for weak in variants:
            try:
                R = game.gm.compute(L2, game.foes, action, foe_id, weak=weak, extra=mod, shift=shift, **kw)
            except SystemExit:
                continue
            ch = S.chances(game.gm, R)
            if action == "hit":
                if "kr" not in R:
                    continue
                value = sum(ch.get(k, 0) / 100 * S.wound(R["kr"], k) for k in ("STRONG", "CLEAN", "PARTIAL"))
                if t and t.get("opens"):                      # a clean hit also sets up the next attack
                    value += 0.15 * (ch.get("STRONG", 0) + ch.get("CLEAN", 0)) / 100
            else:
                lo, hi = R.get("dmg", (0, 0))
                loss = (lo + hi) / 2
                value = -(ch.get("FAIL", 0) * loss + ch.get("PARTIAL", 0) * loss * 0.5 + ch.get("FAIL+", 0) * loss * 1.5) / 100 if action == "dodge" else R["p"] / 100
            cost = (t or {}).get("cost", {})
            value -= cost.get("fatigue", 0) * 0.004 + cost.get("hp_pct", 0) * 0.01
            out.append({"id": tid, "tech": t, "weak": weak, "R": R, "value": value, "chances": ch})
    return sorted(out, key=lambda o: (-o["value"], o["id"] is not None))


def recommend(game, techs, intent, foe=None):
    """The exact gm.py line for this exchange."""
    state = fight_state(game)
    foe_id = game.foe(foe) if foe else (state or {}).get("foe")
    if not foe_id:
        raise KeyError("name a foe, or start a fight with `move start <foe>`")
    action = INTENT[intent]
    rdata = RU.load(game)
    mod = RU.mods(game, rdata, foe_id)[0] if intent != "read" or True else 0
    shift = -3 if (state and state.get("opening") and action == "hit") else 0
    opts = options(game, game.sheet(), techs, action, foe_id, state, mod, shift)
    if not opts:
        raise KeyError(f"gm.py cannot compute {action} against {foe_id}")
    return foe_id, state, mod, shift, opts


def gm_line(action, foe_id, opt, mod, shift):
    parts = [f"python3 gm.py roll {action} foe={foe_id}"]
    t = opt["tech"]
    if opt["id"]:
        parts.append(f"use={PREFIX}{opt['id']}")
    if t and t.get("strike"):
        parts.append(f"strike={t['strike']}")
    if mod:
        parts.append(f"mod={mod:+d}")
    if shift:
        parts.append(f"shift={shift}")
    if opt["weak"]:
        parts.append("--weak")
    parts.append(f"label=\"{t['name'] if t else action.capitalize()}\"")
    parts.append("--apply")
    return " ".join(parts)


def install(game, techs, plan):
    """Put every owned technique into the ledger as a gm.py effect, so `use=` works on real rolls."""
    L = game.sheet()
    before = {e["id"]: e for e in L.get("effects", [])}
    L2 = with_effects(L, techs)
    L2["effects"] = [e for e in L2["effects"] if not (e["id"].startswith(PREFIX) and e["id"][len(PREFIX):] not in owned(L, techs))]
    for e in L2["effects"]:
        if e["id"].startswith(PREFIX):
            t = techs[e["id"][len(PREFIX):]]
            e.update(dict(t.get("effect", {}), note=t.get("note", "")))
            if e != before.get(e["id"]):
                plan.note(f"effect {e['id']}: {t['name']} {t.get('effect', {})}")
    plan.put_json("ledger.json", L2)


def record(game, techs, intent, tier, tid, plan):
    """Write down how an exchange went, so the next recommendation knows."""
    state = fight_state(game)
    if not state:
        return plan.error("no fight in progress: `move start <foe>`"), None
    tier = tier.upper()
    if tier not in ("STRONG", "CLEAN", "PARTIAL", "FAIL", "FAIL+"):
        return plan.error("result must be STRONG, CLEAN, PARTIAL, FAIL or FAIL+"), None
    good = tier in ("STRONG", "CLEAN")
    state["exchanges"] = state.get("exchanges", 0) + 1
    if intent == "attack":
        state["opening"] = False
        if tid:
            tid = tid[len(PREFIX):] if tid.startswith(PREFIX) else tid
            if tid not in techs:
                return plan.error(f"unknown technique {tid}"), None
            if tid not in state["shown"]:
                state["shown"].append(tid)
                plan.note(f"the foe has now seen {techs[tid]['name']}")
            if good and techs[tid].get("opens"):
                state["opening"] = True
                plan.note("the foe is off balance: the next attack is rolled with shift=-3")
    elif intent == "read" and good:
        state["read"] = True
        plan.note("Mori has read its rhythm: counters and adaptation are now open")
    if intent == "defend":
        state["opening"] = False                              # the foe has had its turn and found its feet
    if intent in ("defend", "read") and tier in ("FAIL", "FAIL+"):
        state["lost"] = state.get("lost", 0) + 1
        rdata = RU.load(game)
        bonus = next((r for r in rdata["rulings"] if r["kind"] == "bonus"), None)
        if bonus and state.get("read"):
            RU.bump(game, rdata, bonus["id"], state["foe"], plan)
            plan.put_json("rulings.json", rdata)
        elif bonus:
            plan.note(f"lost exchange, but no tell spotted yet, so {bonus['id']} does not grow (it needs a successful read)")
    return state, tier


def scene_findings(techs, skill_names, lines):
    """Options must offer intentions. Naming a technique in an option makes the player pick the kick."""
    names = [t["name"].split(" (")[0] for t in techs.values()] + list(skill_names)
    tail = [(i, l) for i, l in enumerate(lines, 1) if l.strip()][-8:]
    for i, l in tail:
        if re.match(r"\s*\**\d+[.)]", l):
            hit = next((n for n in names if len(n) > 5 and re.search(rf"\b{re.escape(n)}\b", l, re.I)), None)
            if hit:
                return [("WARN", f"line {i}: an option names a technique ('{hit}'). Offer the intent (attack, press, hold, read) "
                         "and let Mori pick the move from his arsenal")]
    return []
