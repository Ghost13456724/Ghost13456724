"""Power scaling: forecast a fight, audit foe cards, design new foes, name ranks.

Every probability and damage figure is produced by the game's gm.compute().
What this adds is the part gm.py leaves to the GM's head: playing the whole
fight forward many times to see who actually wins and what it costs.
"""
import json
import math
import os
import random

LADDER = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ranks.json"), encoding="utf-8"))
FATIGUE = {"trivial": 1, "easy": 1, "even": 2, "hard": 5, "desperate": 5, "beyond": 6}
CLASSES = [(90, "fodder"), (65, "favoured"), (35, "even fight"), (10, "dangerous"), (0, "do not fight")]
ROLES = {  # the fight each role should give a rested Mori alone, and the shape of the foe (speed, hit, toughness)
    "grunt": {"win": 95, "shape": (0.9, 0.9, 0.8), "dc": "easy"},
    "even": {"win": 50, "shape": (1.0, 1.0, 1.0), "dc": "even"},
    "elite": {"win": 25, "shape": (1.05, 1.1, 1.2), "dc": "hard"},
    "boss": {"win": 8, "shape": (1.0, 1.3, 1.8), "dc": "desperate"},
}


def rank_of(index, ladder="ranks"):
    """ladder: 'ranks' for Earth's KAB scale, 'murim' for the Murim's realms."""
    name = LADDER[ladder][0]["name"]
    for r in LADDER[ladder]:
        if index >= r["from"]:
            name = r["name"]
    return name


def mori_index(L):
    s = L["stats"]
    return round((s["Str"] * (s["Str"] + s["Agi"]) / 2) ** 0.5, 1)


def foe_index(f):
    if not (f.get("SPD") and f.get("ATK")):
        return None
    return round((f["SPD"] * f["ATK"]) ** 0.5, 1)


def wound(kr, tier):
    """Share of the foe's health one landed strike removes, from gm.py's kill table."""
    table = [(2.0, (1, 1, 0.6)), (1.5, (1, 0.75, 0.45)), (1.0, (1, 0.4, 0.12)),
             (0.67, (0.3, 0.15, 0)), (0.5, (0.12, 0, 0)), (0, (0, 0, 0))]
    for lim, vals in table:
        if kr >= lim:
            return vals[("STRONG", "CLEAN", "PARTIAL").index(tier)]


def outcome(gm, R, d):
    if R["edge"] == "auto":
        return "CLEAN" if d != 1 else "PARTIAL"
    if R["edge"] == "autofail":
        return "FAIL"
    return gm.tier(d, d + R["ev"] + R["tech"] + R["msum"], R["dc"])


def chances(gm, R):
    out = {}
    for d in range(1, 21):
        t = outcome(gm, R, d)
        out[t] = out.get(t, 0) + 5
    return out


def _compute(game, L, action, foe_id, **kw):
    try:
        return game.gm.compute(L, game.foes, action, foe_id, **kw)
    except SystemExit as e:
        raise KeyError(f"gm.py refused {action} vs {foe_id}: {e}")


def best_attack(game, L, foe_id):
    """The attack that removes most health per attempt: body or weak point, plain or with a technique he owns."""
    from . import tech as T
    techs = T.load(game)
    if techs:
        opts = [o for o in T.options(game, L, techs, "hit", foe_id, {"shown": [o for o, t in techs.items() if t.get("when", {}).get("unshown")]})]
        if opts:
            o = opts[0]
            exp = sum(o["chances"].get(t, 0) / 100 * wound(o["R"]["kr"], t) for t in ("STRONG", "CLEAN", "PARTIAL"))
            return (exp, o["weak"], o["R"], o["id"])
    best = None
    for weak in (False, True):
        if weak and not game.foes[foe_id].get("T_weak"):
            continue
        R = _compute(game, L, "hit", foe_id, weak=weak)
        if "kr" not in R:
            continue
        ch = chances(game.gm, R)
        exp = sum(ch.get(t, 0) / 100 * wound(R["kr"], t) for t in ("STRONG", "CLEAN", "PARTIAL"))
        if best is None or exp > best[0]:
            best = (exp, weak, R)
    return best


def simulate(game, L0, foe_id, fights=600, max_rounds=40, seed=7, defences=1):
    """Play the fight forward: each round Mori strikes once and defends once.

    HP, fatigue and the penalties gm.py hangs on them change as the fight goes,
    so a long fight is harder than its first exchange suggests."""
    rng = random.Random(seed)
    gm, wins, rounds, hp_left = game.gm, 0, 0, 0
    cache = {}

    plan = best_attack(game, L0, foe_id)

    def odds(L, action, weak=False):
        hp = L["hp"] / max(1, L["hp_max"])
        key = (action, weak, min(L["fatigue"], 90) // 10, 0 if hp < 0.1 else 1 if hp < 0.3 else 2 if hp < 0.5 else 3)
        if key not in cache:
            if action == "hit" and plan and len(plan) > 3 and plan[3]:
                from . import tech as T
                L2 = T.with_effects(L, T.load(game))
                t = T.load(game)[plan[3]]
                cache[key] = game.gm.compute(L2, game.foes, "hit", foe_id, weak=weak, use=(T.PREFIX + plan[3],), **({"strike": t["strike"]} if t.get("strike") else {}))
            else:
                cache[key] = _compute(game, L, action, foe_id, weak=weak)
        return cache[key]

    for _ in range(fights):
        L = dict(L0, hp=L0["hp"], fatigue=L0.get("fatigue", 0))
        foe_hp, r = 1.0, 0
        while r < max_rounds and L["hp"] > 0 and foe_hp > 0:
            r += 1
            if plan:
                R = odds(L, "hit", plan[1])
                t = outcome(gm, R, rng.randint(1, 20))
                if t in ("STRONG", "CLEAN", "PARTIAL"):
                    foe_hp -= wound(R["kr"], t)
                L["fatigue"] = min(100, L["fatigue"] + FATIGUE.get(R["band"], 2))
                if foe_hp <= 0:
                    break
            for _ in range(defences):
                R = odds(L, "dodge")
                t = outcome(gm, R, rng.randint(1, 20))
                if t in ("PARTIAL", "FAIL", "FAIL+") and "dmg" in R:
                    lo, hi = R["dmg"]
                    hurt = rng.randint(lo, hi) if hi > lo else lo
                    L["hp"] -= round(hurt * (0.5 if t == "PARTIAL" else 1.5 if t == "FAIL+" else 1))
                L["fatigue"] = min(100, L["fatigue"] + FATIGUE.get(R["band"], 2))
        if foe_hp <= 0 and L["hp"] > 0:
            wins += 1
            rounds += r
            hp_left += L["hp"] / L["hp_max"]
    return {"win": round(100 * wins / fights), "rounds": round(rounds / wins, 1) if wins else None,
            "hp_left": round(100 * hp_left / wins) if wins else None}


def classify(win, hp_left=100):
    name = next(name for lim, name in CLASSES if win >= lim)
    return "favoured" if name == "fodder" and (hp_left or 0) < 85 else name   # fodder does not cost a quarter of his health


def matchup(game, foe_id, level=None, sims=600, defences=1):
    foe_id = game.foe(foe_id)
    f = game.foes[foe_id]
    now, fresh = game.sheet(level), game.sheet(level, fresh=True)
    out = {"id": foe_id, "foe": f, "level": fresh["level"], "lines": []}
    for label, action, weak in (("kick", "hit", False), ("kick, weak point", "hit", True), ("dodge", "dodge", False),
                                ("read", "read", False), ("endure", "endure", False)):
        if weak and not f.get("T_weak"):
            continue
        R = _compute(game, fresh, action, foe_id, weak=weak)
        line = f"{label:<17} DC {R['dc']:>2} ({R['band']}) edge {game.gm.fmt_e(R['edge']):>4} tech {R['tech']:+} -> {R['p']:>3}%"
        if "kr" in R and action == "hit":
            line += f" | KP {R['kp']:.0f} vs T {R['T']} = {R['kr']:.2f}: {R['kill']['CLEAN']}"
        out["lines"].append(line)
        out[label] = R
    R = out["dodge"]
    if "dmg" in R:
        lo, hi = R["dmg"]
        out["hits_to_down"] = (max(1, -(-fresh["hp_max"] // max(1, hi))), max(1, -(-fresh["hp_max"] // max(1, lo))) if lo else None)
        out["taken"] = (lo, hi, R["tr"])
    out["fresh"] = simulate(game, fresh, foe_id, sims, defences=defences)
    out["now"] = simulate(game, now, foe_id, sims, defences=defences) if not level and now["hp"] > 0 else None
    out["defences"] = defences
    out["class"] = classify(out["fresh"]["win"], out["fresh"]["hp_left"])
    out["cant_hurt"] = best_attack(game, fresh, foe_id) is None or best_attack(game, fresh, foe_id)[0] == 0
    return out


def audit(game, sims=300):
    """Check every foe card for missing numbers, internal contradictions and a
    difficulty label that the numbers do not support."""
    finds = []
    add = lambda sev, foe, msg: finds.append((sev, foe, msg))
    results = {}
    for fid, f in game.foes.items():
        missing = [k for k in ("SPD", "ATK", "T", "type", "dc", "name") if f.get(k) in (None, "")]
        if missing:
            add("FAIL", fid, "card is missing " + ", ".join(missing))
            continue
        if f.get("T_weak") and f["T_weak"] >= f["T"] and f["T"] < 9999:
            add("FAIL", fid, f"weak point (T_weak {f['T_weak']}) is not softer than the body (T {f['T']})")
        if not f.get("STEALTH"):
            add("WARN", fid, "no STEALTH: sense rolls against it will fail to compute")
        try:
            m = results[fid] = matchup(game, fid, sims=sims)
        except KeyError as e:
            add("FAIL", fid, f"gm.py cannot compute a fight from this card ({e.args[0][-60:]})")
            continue
        label = f["dc"] if isinstance(f["dc"], str) else None
        win = m["fresh"]["win"]
        if (label in ("trivial", "easy") and win < 50) or (label in ("hard", "desperate", "beyond") and win >= 80):
            add("WARN", fid, f"card says '{label}' but a rested Lv{m['level']} Mori wins {win}% of whole fights ({m['class']})")
        if m["cant_hurt"] and label not in ("beyond", "desperate") and "unwinnable" not in f.get("notes", ""):
            add("WARN", fid, f"a rested Lv{m['level']} Mori cannot wound it even on its weak point; the card only says "
                f"'{label}'. Note on the card what beats it (allies, a trick, a level) so it is not played as a fair solo fight")
        typ = f.get("type", "")
        if typ.startswith("human_"):
            want, got = typ.split("_", 1)[1] + "-rank", rank_of(foe_index(f))
            if want != got:
                add("NOTE", fid, f"typed {want} but its numbers sit in the {got} band (index {foe_index(f)})")
    # members of one family should get stronger with their title
    ids = sorted(game.foes)
    for a in ids:
        for b in ids:
            if b.startswith(a + "_") and a in results and b in results:
                fa, fb = game.foes[a], game.foes[b]
                weaker = [k for k in ("ATK", "T") if fb.get(k, 0) < fa.get(k, 0)]
                if weaker and not b.endswith(("hatchling", "pup", "larva", "minion")):
                    add("WARN", b, f"is a senior form of {a} but has lower {', '.join(weaker)}")
                if b.endswith(("hatchling", "pup", "larva", "minion")) and fb.get("ATK", 0) > fa.get("ATK", 0):
                    add("WARN", b, f"is a junior form of {a} but hits harder")
    return finds, results


def _logit(pct):
    p = min(99, max(1, pct)) / 100
    return math.log(p / (1 - p))


def design(game, role, level=None, name="New Foe", ftype="beast", rank=None, sims=300):
    """Build a foe card from the fight it should give.

    The card is grown step by step and the whole fight is replayed with gm.py's
    numbers at each step; the card whose win rate lands closest to the role's
    target is returned. With rank=, the card is scaled into that rank's band
    instead and the forecast shows what that means for Mori."""
    if role not in ROLES:
        raise KeyError(f"role must be one of {', '.join(ROLES)}")
    spec, L = ROLES[role], game.sheet(level, fresh=True)
    saved = game.foes
    game.foes = dict(saved, _probe={"name": name, "SPD": 10, "ATK": 10, "T": 10, "type": ftype})
    try:
        kp = _compute(game, L, "hit", "_probe")["kp"]
        pace, con, sense = (L["stats"]["Str"] + L["stats"]["Agi"]) / 2, L["stats"]["Con"], L["stats"]["Sense"]
        fs, fa, ft = spec["shape"]

        def card(k):
            return {"name": name, "SPD": max(1, round(pace * fs * k)), "ATK": max(1, round(con * fa * k)),
                    "T": max(2, round(kp * ft * k)), "T_weak": max(1, round(kp * ft * k / 1.5)),
                    "STEALTH": max(1, round(sense * fs * k)), "type": ftype, "dc": spec["dc"],
                    "notes": f"designed as {role} for a Lv{L['level']} Mori"}

        if rank:
            band = next((r for lad in ("ranks", "murim") for r in LADDER[lad] if r["name"].lower() == rank.lower()), None)
            if not band:
                raise KeyError(f"unknown rank '{rank}'")
            lad = next(l for l in ("ranks", "murim") if band in LADDER[l])
            nxt = next((r["from"] for r in LADDER[lad] if r["from"] > band["from"]), band["from"] * 1.7)
            base = card(1.0)
            best = card((band["from"] + nxt) / 2 / (base["SPD"] * base["ATK"]) ** 0.5)   # middle of the band
            best["notes"] = f"{band['name']} {role}"
        else:
            best, gap = None, None
            for step in range(8, 61):                       # k from 0.40 to 3.00
                c = card(step / 20)
                game.foes["_probe"] = c
                g = abs(_logit(simulate(game, L, "_probe", sims)["win"]) - _logit(spec["win"]))
                if gap is None or g < gap:
                    best, gap = c, g
        game.foes["_probe"] = best
        m = matchup(game, "_probe", level, max(sims, 600))
    finally:
        game.foes = saved
    m["target"] = None if rank else spec["win"]
    return best, m
