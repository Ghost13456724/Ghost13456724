"""Scene review: check a scene's claims against canon, then commit them.

The reviewing agent reads the prose and writes down what the scene claims
happened (see examples/claims.json). This module decides whether those
claims fit canon. Splitting it this way keeps the judgment calls with the
reader and the bookkeeping with code that cannot forget.
"""
from . import canon as C
from . import scale as S

SEVERITY = {"error": 0, "warn": 1, "note": 2}


def _normalize(scale, claims):
    """Let the reviewer write feat ratings as realms ('TE 3') as well as numbers."""
    for ev in claims.get("events", []):
        if ev.get("type") == "feat":
            ev["rating"] = S.parse_rating(scale, ev["rating"])
    return claims


def check(scale, canon, claims):
    claims = _normalize(scale, claims)
    out = []
    add = lambda sev, code, msg: out.append((sev, code, msg))
    rules = scale["matchup"]
    day = claims.get("day")
    now = canon.get("clock", {}).get("day", 0)
    if day is not None and day < now:
        add("error", "time-reversal", f"Scene is set on day {day} but the world clock is already at day {now}.")

    place = claims.get("location")
    present, learned, moved, powered = [], {}, set(), {}
    for ev in claims.get("events", []):
        if ev["type"] == "travel":
            moved.add(C.resolve(canon, ev["who"]))
        if ev["type"] == "learns":
            learned.setdefault(C.resolve(canon, ev["who"]), set()).add(ev["fact"])
        if ev["type"] == "power_up":
            powered.setdefault((C.resolve(canon, ev["who"]), ev["stat"]), 0)
            powered[(C.resolve(canon, ev["who"]), ev["stat"])] += ev.get("delta", 0)

    for raw in claims.get("present", []):
        key = C.resolve(canon, raw)
        if key is None:
            add("note", "new-character", f"{raw} is not in canon. Add a sheet before the next scene if they matter.")
            continue
        present.append(key)
        char = canon["characters"][key]
        if char.get("status") == "dead":
            add("error", "dead-character", f"{key} is dead ({char.get('died', 'earlier')}) but appears in this scene.")
        last = char.get("location")
        if place and last and last != place and key not in moved:
            add("warn", "teleport", f"{key} was last at {last}; the scene puts them at {place} with no travel shown.")
        for cond in char.get("conditions", []):
            add("note", "active-condition", f"{key} still carries: {cond['name']}. The prose should show it.")

    def who(ev, field="who"):
        key = C.resolve(canon, ev.get(field))
        if key is None:
            add("warn", "unknown-character", f"{ev.get(field)} ({ev['type']}) has no sheet, so this cannot be checked.")
        elif key not in present:
            add("warn", "not-present", f"{key} acts ({ev['type']}) but is not listed as present.")
        return key

    for ev in claims.get("events", []):
        t = ev["type"]
        if t == "fight":
            w, l = who(ev, "winner"), who(ev, "loser")
            if not (w and l):
                continue
            m = S.matchup(scale, canon, w, l, ev.get("winner_form"), ev.get("loser_form"))
            why = ev.get("conditions") or []
            if m["band"] == "impossible" or m["a_blocked"]:
                sev = "warn" if why else "error"
                add(sev, "impossible-win", f"{w} beats {l} at a gap of {m['gap']:+} ({m['band']}). "
                    + ("Stated reasons: " + "; ".join(why) + ". Make sure they truly cover a gap this size."
                       if why else "Nothing in the scene explains it."))
            elif m["gap"] <= -rules["upset_gap"]:
                if not why:
                    add("error", "unexplained-upset", f"{w} beats {l} at a gap of {m['gap']:+} ({m['band']}, "
                        f"{m['chance']:.0%}) with no conditions given.")
                elif not ev.get("cost"):
                    add("warn", "free-upset", f"{w} beats {l} against the odds ({m['gap']:+}) and pays nothing for it.")
            elif m["gap"] >= rules["upset_gap"] and ev.get("close"):
                add("warn", "false-tension", f"{w} outclasses {l} by {m['gap']:+}; writing it as a close fight undersells {w}.")
            if ev.get("rolled") is False and m["band"] not in ("auto", "impossible"):
                add("warn", "no-roll", f"{w} vs {l} is a {m['band']} fight (DC {m['dc']}); it should have been rolled.")
        elif t == "feat":
            k = who(ev)
            if not k:
                continue
            stats, _ = S.effective(canon["characters"][k], ev.get("form"))
            have = stats[ev["stat"]] + powered.get((k, ev["stat"]), 0)
            over = ev["rating"] - have
            if over > scale["evidence"]["tolerance"]:
                add("error", "feat-above-stats", f"{k} shows {ev['stat']} {ev['rating']} ({S.tier_of(scale, ev['rating'])}) "
                    f"but sits at {have}: {ev.get('desc', '')}".rstrip(": "))
            elif over < -rules["upset_gap"] and ev.get("struggled"):
                add("warn", "jobbing", f"{k} struggles with a {ev['stat']} {ev['rating']} task despite being {have}.")
        elif t == "power_up":
            k = who(ev)
            if not ev.get("earned_by"):
                add("error", "unearned-power", f"{k or ev['who']} gains {ev['stat']} {ev.get('delta', 0):+} with no cause in the story.")
            if not ev.get("cost"):
                add("warn", "free-power", f"{k or ev['who']} gains {ev['stat']} {ev.get('delta', 0):+} at no cost.")
            if ev.get("delta", 0) > scale["evidence"]["max_jump"]:
                add("warn", "big-jump", f"{k or ev['who']} jumps {ev['delta']} in one scene (more than a full tier).")
        elif t == "uses_item":
            k = who(ev)
            if k and ev["item"] not in canon["characters"][k].get("items", []):
                add("error", "missing-item", f"{k} uses {ev['item']} but does not own it.")
        elif t == "uses_ability":
            k = who(ev)
            if k and ev["ability"] not in canon["characters"][k].get("abilities", []):
                add("error", "unknown-ability", f"{k} uses {ev['ability']} but has never learned it.")
        elif t in ("knows", "learns", "reveal"):
            fact = canon.get("facts", {}).get(ev["fact"])
            if fact is None:
                add("note", "new-fact", f"Fact '{ev['fact']}' is not in canon yet.")
                continue
            if t == "knows":
                k = who(ev)
                if k and ev["fact"] not in canon["characters"][k].get("knows", []) and ev["fact"] not in learned.get(k, ()):
                    add("error", "knowledge-leak", f"{k} acts on '{fact['text']}' but has no way of knowing it.")
            elif fact.get("rung") is not None and fact["rung"] > canon.get("rung", 0) + 1:
                add("error", "early-reveal", f"'{fact['text']}' is rung {fact['rung']}; the story is at rung "
                    f"{canon.get('rung', 0)}. Clues first.")
        elif t in ("injury", "death", "travel", "gains_item", "loses_item", "recovers", "learns_ability"):
            who(ev)
        else:
            add("warn", "unknown-event", f"Unrecognized event type: {t}")
    return sorted(out, key=lambda f: SEVERITY[f[0]])


def commit(canon, claims):
    """Apply a reviewed scene to canon. Returns a list of what changed."""
    log = []
    scene = claims.get("scene", "?")
    if claims.get("day") is not None:
        canon.setdefault("clock", {})["day"] = max(claims["day"], canon.get("clock", {}).get("day", 0))
    for raw in claims.get("present", []):
        key = C.resolve(canon, raw)
        if key and claims.get("location"):
            canon["characters"][key]["location"] = claims["location"]
    for ev in claims.get("events", []):
        t = ev["type"]
        key = C.resolve(canon, ev.get("who")) if ev.get("who") else None
        char = canon["characters"].get(key) if key else None
        if t == "fight":
            canon.setdefault("results", []).append({
                "winner": C.resolve(canon, ev["winner"]) or ev["winner"],
                "loser": C.resolve(canon, ev["loser"]) or ev["loser"],
                "conditions": ev.get("conditions", []), "scene": scene})
            log.append(f"result: {ev['winner']} beat {ev['loser']}")
        elif char is None:
            continue
        elif t == "feat":
            char.setdefault("feats", []).append({"stat": ev["stat"], "rating": ev["rating"],
                                                 "kind": ev.get("kind", "shown"), "desc": ev.get("desc", ""), "scene": scene})
            log.append(f"feat: {key} {ev['stat']} {ev['rating']}")
        elif t == "power_up":
            char.setdefault("stats", {})[ev["stat"]] = char.get("stats", {}).get(ev["stat"], 0) + ev.get("delta", 0)
            log.append(f"stat: {key} {ev['stat']} -> {char['stats'][ev['stat']]}")
        elif t == "injury":
            char.setdefault("conditions", []).append({"name": ev["name"], "mods": ev.get("mods", {}), "scene": scene})
            log.append(f"condition: {key} + {ev['name']}")
        elif t == "recovers":
            char["conditions"] = [c for c in char.get("conditions", []) if c["name"] != ev["name"]]
            log.append(f"condition: {key} - {ev['name']}")
        elif t == "death":
            char["status"], char["died"] = "dead", scene
            log.append(f"death: {key}")
        elif t == "travel":
            char["location"] = ev.get("to", claims.get("location"))
        elif t == "gains_item":
            char.setdefault("items", []).append(ev["item"])
            log.append(f"item: {key} + {ev['item']}")
        elif t in ("loses_item",) or (t == "uses_item" and ev.get("consumed")):
            if ev["item"] in char.get("items", []):
                char["items"].remove(ev["item"])
                log.append(f"item: {key} - {ev['item']}")
        elif t == "learns_ability":
            char.setdefault("abilities", []).append(ev["ability"])
            log.append(f"ability: {key} + {ev['ability']}")
        elif t == "learns":
            if ev["fact"] not in char.setdefault("knows", []):
                char["knows"].append(ev["fact"])
                log.append(f"knowledge: {key} learns {ev['fact']}")
        if t == "reveal":
            fact = canon.get("facts", {}).get(ev["fact"])
            if fact and fact.get("rung") is not None:
                canon["rung"] = max(canon.get("rung", 0), fact["rung"])
                log.append(f"secret ladder: rung {canon['rung']}")
    canon.setdefault("scenes", []).append(scene)
    return log
