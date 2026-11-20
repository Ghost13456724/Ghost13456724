"""Power scaling.

Every stat is a rating on one logarithmic scale: +10 is one full tier
(about ten times the output), +3 is about double. Ratings come from feats,
so a number nobody has shown on the page is flagged instead of trusted.

Stats:
  ap   attack potency (how hard they hit)
  dur  durability (what they can take)
  spd  combat speed and reactions
  sta  stamina / energy reserves
  tec  technique (skill; feeds the dice roll, not the raw gap)
"""
from . import canon as C

STATS = ("ap", "dur", "spd", "sta", "tec")
BAND_ORDER = ("auto", "trivial", "easy", "even", "hard", "desperate", "beyond", "impossible")


def tier_of(scale, rating):
    """Name the tier a rating falls in, with low/mid/high placement."""
    tiers = sorted(scale["tiers"], key=lambda t: t["floor"])
    if rating < tiers[0]["floor"]:
        return f"below {tiers[0]['name']}"
    i = max(k for k, t in enumerate(tiers) if rating >= t["floor"])
    width = tiers[i + 1]["floor"] - tiers[i]["floor"] if i + 1 < len(tiers) else 10
    pos = (rating - tiers[i]["floor"]) / width
    place = "low" if pos < 1 / 3 else "mid" if pos < 2 / 3 else "high"
    return f"{place} {tiers[i]['name']}"


def effective(char, form=None):
    """Stats after the active form and every current condition are applied."""
    stats = {s: char.get("stats", {}).get(s, 0) for s in STATS}
    applied = []
    if form:
        forms = {k.lower(): (k, v) for k, v in char.get("forms", {}).items()}
        if form.lower() not in forms:
            raise KeyError(f"unknown form: {form}")
        name, data = forms[form.lower()]
        for s, d in data.get("mods", {}).items():
            stats[s] += d
        applied.append(f"form {name}" + (f" (cost: {data['cost']})" if data.get("cost") else ""))
    for cond in char.get("conditions", []):
        for s, d in cond.get("mods", {}).items():
            stats[s] += d
        applied.append(f"condition {cond['name']}")
    return stats, applied


def overall(stats):
    return round(0.3 * stats["ap"] + 0.25 * stats["dur"] + 0.3 * stats["spd"] + 0.15 * stats["sta"], 1)


def evidence(scale, char):
    """What the feats on record actually support, stat by stat."""
    rules = scale["evidence"]
    out = {}
    for s in STATS:
        feats = [f for f in char.get("feats", []) if f["stat"] == s]
        shown = sorted((f for f in feats if f.get("kind", "shown") == "shown"),
                       key=lambda f: -f["rating"])
        stated = sorted((f for f in feats if f.get("kind") == "stated"), key=lambda f: -f["rating"])
        outliers = [f for f in shown if f.get("outlier")]
        shown = [f for f in shown if not f.get("outlier")]
        # A lone feat far above everything else is an outlier until repeated.
        while len(shown) >= 2 and shown[0]["rating"] - shown[1]["rating"] > rules["outlier_gap"]:
            outliers.append(shown.pop(0))
        supported, basis = None, "none"
        if shown:
            supported, basis = shown[0]["rating"], "shown"
            if stated and stated[0]["rating"] > supported:
                supported = min(stated[0]["rating"], supported + rules["statement_bonus"])
                basis = "shown+stated"
        elif stated:
            supported, basis = stated[0]["rating"], "stated only"
        out[s] = {"supported": supported, "basis": basis, "outliers": outliers,
                  "count": len(shown) + len(stated)}
    return out


def _band(scale, gap):
    for b in scale["bands"]:
        if gap >= b["min_gap"]:
            return b["name"]
    return "impossible"


def _shift(band, steps):
    i = max(0, min(len(BAND_ORDER) - 1, BAND_ORDER.index(band) + steps))
    return BAND_ORDER[i]


def win_chance(dc, mod):
    """Chance that d20 + mod meets dc. A natural 1 fails, a natural 20 succeeds."""
    need = dc - mod
    hits = sum(1 for r in range(1, 21) if r != 1 and (r == 20 or r >= need))
    return hits / 20


def matchup(scale, canon, a_name, b_name, a_form=None, b_form=None):
    """Judge A against B from A's side."""
    a_key, a = C.get(canon, a_name)
    b_key, b = C.get(canon, b_name)
    sa, a_applied = effective(a, a_form)
    sb, b_applied = effective(b, b_form)
    rules = scale["matchup"]
    notes = []

    a_dmg = sa["ap"] - sb["dur"]
    b_dmg = sb["ap"] - sa["dur"]
    spd = sa["spd"] - sb["spd"]
    sta = sa["sta"] - sb["sta"]
    gap = round(0.25 * (a_dmg - b_dmg) + 0.3 * spd + 0.2 * sta, 1)
    band = _band(scale, gap)

    a_blocked = a_dmg <= -rules["no_damage_gap"]
    b_blocked = b_dmg <= -rules["no_damage_gap"]
    if spd >= rules["blitz_gap"]:
        notes.append(f"{a_key} blitzes: {b_key} cannot react at this speed gap ({spd:+}).")
        band = _shift(band, -1)
    elif spd <= -rules["blitz_gap"]:
        notes.append(f"{b_key} blitzes: {a_key} cannot react at this speed gap ({spd:+}).")
        band = _shift(band, 1)

    def hax(user, user_key, target, target_stats, target_key):
        found = []
        for name in user.get("abilities", []):
            ab = canon.get("abilities", {}).get(name)
            if not ab or not ab.get("bypasses_durability"):
                continue
            resist = target.get("resist", {}).get(ab["kind"], target_stats["dur"] - rules["default_resist_penalty"])
            if ab["potency"] >= resist:
                found.append(f"{user_key}'s {name} ({ab['kind']} {ab['potency']}) beats {target_key}'s "
                             f"resistance ({resist}): a real win condition"
                             + (f", cost: {ab['cost']}" if ab.get("cost") else "") + ".")
        return found

    a_hax = hax(a, a_key, b, sb, b_key)
    b_hax = hax(b, b_key, a, sa, a_key)
    notes += a_hax + b_hax

    if a_blocked and not a_hax:
        notes.append(f"{a_key} cannot meaningfully damage {b_key} (AP {sa['ap']} vs DUR {sb['dur']}). "
                     "A win needs a weakness, an outside factor or a new power, and the scene must show it.")
        band = _shift(max(band, "beyond", key=BAND_ORDER.index), 0)
    elif a_hax and BAND_ORDER.index(band) > BAND_ORDER.index("hard"):
        band = _shift(band, -1)
    if b_blocked and not b_hax:
        notes.append(f"{b_key} cannot meaningfully damage {a_key} (AP {sb['ap']} vs DUR {sa['dur']}).")
        band = min(band, "trivial", key=BAND_ORDER.index)
    elif b_hax and BAND_ORDER.index(band) < BAND_ORDER.index("easy"):
        band = _shift(band, 1)

    tech_mod = max(-rules["tech_cap"], min(rules["tech_cap"], round((sa["tec"] - sb["tec"]) / rules["tech_divisor"])))
    if a_blocked and not a_hax:
        tech_mod = min(tech_mod, 0)  # skill alone does not get through hide it cannot cut
    dc = scale["difficulty"].get(band)
    if band == "auto":
        chance = 1.0
    elif band == "impossible":
        chance = 0.0
    else:
        chance = win_chance(dc, tech_mod)

    if abs(gap) < 3:
        verdict = "Even fight: skill, terrain and the dice decide it."
    elif gap > 0:
        verdict = f"{a_key} is favored" + (" overwhelmingly." if gap >= 15 else " clearly." if gap >= 8 else ".")
    else:
        verdict = f"{b_key} is favored" + (" overwhelmingly." if gap <= -15 else " clearly." if gap <= -8 else ".")

    return {
        "a": a_key, "b": b_key, "a_stats": sa, "b_stats": sb,
        "a_tier": tier_of(scale, overall(sa)), "b_tier": tier_of(scale, overall(sb)),
        "a_overall": overall(sa), "b_overall": overall(sb),
        "applied": a_applied + b_applied,
        "gap": gap, "band": band, "dc": dc, "tech_mod": tech_mod, "chance": chance,
        "a_blocked": a_blocked and not a_hax, "verdict": verdict, "notes": notes,
    }


def audit(scale, canon):
    """Find stats without evidence, lowballed stats, outliers and results that contradict the numbers."""
    findings = []
    tol = scale["evidence"]["tolerance"]
    for name, char in canon["characters"].items():
        ev = evidence(scale, char)
        for s in STATS:
            declared = char.get("stats", {}).get(s)
            e = ev[s]
            if declared is None:
                continue
            if e["supported"] is None:
                findings.append(("warn", "no-evidence", f"{name} {s} {declared}: no feat on record."))
            elif declared > e["supported"] + tol:
                findings.append(("error", "inflated", f"{name} {s} is {declared} but feats support {e['supported']} ({e['basis']})."))
            elif declared < e["supported"] - tol:
                findings.append(("warn", "lowballed", f"{name} {s} is {declared} but feats support {e['supported']}; raise the stat or mark the feat an outlier."))
            if e["basis"] == "stated only":
                findings.append(("note", "statement-only", f"{name} {s} rests on statements alone; show it in a scene."))
            for f in e["outliers"]:
                findings.append(("note", "outlier", f"{name} {s} {f['rating']} ({f.get('desc', '?')}) is an outlier and is not counted."))

    upset_gap = scale["matchup"]["upset_gap"]
    fair = {}
    for r in canon.get("results", []):
        w, l = C.resolve(canon, r["winner"]), C.resolve(canon, r["loser"])
        if not w or not l or r.get("conditions"):
            continue
        fair.setdefault(w, set()).add(l)
        m = matchup(scale, canon, w, l)
        if m["gap"] <= -upset_gap:
            findings.append(("error", "result-contradiction",
                             f"{w} beat {l} fair and square ({r.get('scene', '?')}) but the stats put {w} at {m['gap']:+}. "
                             f"Raise {w}, lower {l}, or record the conditions that made it possible."))
    for a, beaten in fair.items():
        for b in beaten:
            if a < b and a in fair.get(b, ()):
                findings.append(("warn", "split-results", f"{a} and {b} have both beaten each other with no conditions recorded."))
    return findings
