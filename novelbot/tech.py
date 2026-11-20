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
    "ground_drawer": {
        "name": "Ground Drawer", "action": "dodge", "needs": {"skill": "Renewal Taekwondo", "mastery": 5},
        "effect": {"taken_mult": 0.6}, "cost": {"fatigue": 2},
        "note": "a dust arc torn up from the floor that bleeds off what is coming at him"},
    "dragon_catcher": {
        "name": "Dragon Catcher", "action": "hit", "strike": "kick", "needs": {"skill": "Renewal Taekwondo", "mastery": 5},
        "effect": {"kp_mult": 1.7, "dc_shift": 1}, "when": {"opening": True}, "cost": {"fatigue": 4},
        "note": "hook the neck of an off-balance foe and drop it head first"},
    "true_hoechook": {
        "name": "True Hoechook", "action": "hit", "strike": "kick", "needs": {"skill": "Renewal Taekwondo", "mastery": 7},
        "effect": {"kp_mult": 2.5, "dc_shift": 1}, "cost": {"fatigue": 30, "hp_pct": 10},
        "note": "palm up, fist clenched, then the vortex. It costs him a tenth of his health and most of his wind"},
    "erase_the_rhythm": {
        "name": "Erase the Rhythm", "action": "read", "needs": {"skill": "Erase the Rhythm"},
        "effect": {"tech": 1}, "note": "hold the breath, go loose: reading from stillness"},
}


RANKS = (8, 25, 60, 120, 250)        # successful uses at which a technique gains a rank of its own


def load(game):
    return game.json("techniques.json", None) or {}


def level(L, t):
    """How far past the unlock point he is: mastery of the art beyond what the technique needs, plus its own rank from use."""
    need = t.get("needs", {})
    have = mastery(L, need["skill"]) if need.get("skill") else None
    return max(0, (have or 0) - need.get("mastery", 1)) + rank(t)


def rank(t):
    return sum(1 for r in RANKS if t.get("used", 0) >= r)


def scaled(L, t):
    """The card at his current skill: stronger where it was strong, less awkward where it was awkward, cheaper to use.

    Per level past the unlock: a damage bonus grows by a tenth of itself; a damage or accuracy penalty shrinks;
    technique +1 per two levels; fatigue cost -1 and health cost -2 per level. A card's own "growth" overrides this."""
    lv, g = level(L, t), t.get("growth", {})
    e, c = dict(t.get("effect", {})), dict(t.get("cost", {}))
    if lv:
        if "kp_mult" in e:
            k = e["kp_mult"]
            e["kp_mult"] = round(k + lv * g.get("kp_mult", (k - 1) * 0.1 if k > 1 else 0.05), 2) if k > 1 else round(min(1.0, k + lv * g.get("kp_mult", 0.05)), 2)
        if "taken_mult" in e:
            e["taken_mult"] = round(max(0.3, e["taken_mult"] - lv * g.get("taken_mult", 0.04)), 2)
        if "dc_shift" in e:
            d = e["dc_shift"]
            step = lv * g.get("dc_shift", 0.5)
            e["dc_shift"] = int(max(0, d - step)) if d > 0 else int(d - (step if g.get("dc_shift") else 0))
            if e["dc_shift"] == 0:
                del e["dc_shift"]
        e["tech"] = e.get("tech", 0) + int(lv * g.get("tech", 0.5))
        if not e["tech"]:
            del e["tech"]
        if "fatigue" in c:
            c["fatigue"] = max(0, c["fatigue"] - lv * g.get("fatigue", 1))
        if "hp_pct" in c:
            c["hp_pct"] = max(0, c["hp_pct"] - lv * g.get("hp_pct", 2))
    return e, {k: v for k, v in c.items() if v}


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
    L["effects"] = [e for e in L.get("effects", []) if not e["id"].startswith(PREFIX)]
    for tid, t in owned(L, techs).items():
        L["effects"].append(dict(scaled(L, t)[0], id=PREFIX + tid, src="technique", on=True, passive=False,
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
            cost = scaled(L, t)[1] if t else {}
            value -= cost.get("fatigue", 0) * 0.004 + cost.get("hp_pct", 0) * 0.01
            out.append({"id": tid, "tech": t, "weak": weak, "R": R, "value": value, "chances": ch, "cost": cost})
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
    """Write every owned technique into the ledger at its current strength, so `use=` works on real rolls."""
    L = game.sheet()
    before = {e["id"]: e for e in L.get("effects", [])}
    L2 = with_effects(L, techs)
    for e in L2["effects"]:
        if e["id"].startswith(PREFIX) and e != before.get(e["id"]):
            t = techs[e["id"][len(PREFIX):]]
            plan.note(f"effect {e['id']}: {t['name']} {scaled(L, t)[0]}" + (f" cost {scaled(L, t)[1]}" if scaled(L, t)[1] else ""))
    for old in before:
        if old.startswith(PREFIX) and old not in {e["id"] for e in L2["effects"]}:
            plan.note(f"effect {old} removed (no longer owned)")
    plan.put_json("ledger.json", L2)
    return L2


def stale(game, techs):
    """True when the ledger's technique effects are behind his current skill."""
    L = game.sheet()
    return [e for e in L.get("effects", []) if e["id"].startswith(PREFIX)] != [e for e in with_effects(L, techs)["effects"] if e["id"].startswith(PREFIX)]


def missing_cards(game, techs):
    """Techniques his mastery has opened in SKILL_TREES.md, and skills on his sheet, that have no card yet."""
    from . import scene as SC
    L, out = game.ledger, []
    names = " ".join(t["name"].lower() for t in techs.values())
    art = mastery(L, "Renewal Taekwondo") or 0
    for name, need in SC.technique_levels(game).items():
        if need <= art and name not in names:
            out.append(f"{name.title()} (opened at mastery {need})")
    for skill in L.get("skills", {}):
        base = re.sub(r"\s*\(.*", "", skill).lower()
        if "taekwondo" not in base and base not in names and not any(base in (t.get("needs", {}).get("skill", "").lower()) for t in techs.values()):
            out.append(f"{skill} (a skill on the sheet)")
    return out


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
            if good:
                t = techs[tid]
                was = rank(t)
                t["used"] = t.get("used", 0) + 1
                if rank(t) > was:
                    plan.note(f"[{t['name']}: mastery through use. Rank {rank(t)}.]  It now hits harder and costs less; "
                              "run `tech install --write` so gm.py has the new numbers")
                plan.put_json("techniques.json", techs)
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
