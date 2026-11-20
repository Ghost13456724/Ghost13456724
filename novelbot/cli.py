"""Command line for novelbot. Run `python3 bot.py help`."""
import argparse
import json
import random
import sys

from . import canon as C
from . import lint as L
from . import review as R
from . import scale as S

MARK = {"error": "FAIL", "warn": "WARN", "note": "note"}


def _report(findings, as_json=False):
    findings = sorted(findings, key=lambda f: R.SEVERITY[f[0]])
    if as_json:
        print(json.dumps([{"severity": s, "code": c, "message": m} for s, c, m in findings], indent=2))
    else:
        for s, c, m in findings:
            print(f"  {MARK[s]:4} [{c}] {m}")
        errors = sum(1 for f in findings if f[0] == "error")
        warns = sum(1 for f in findings if f[0] == "warn")
        verdict = "REJECT" if errors else "REVISE" if warns else "PASS"
        print(f"\n{verdict}: {errors} errors, {warns} warnings, {len(findings) - errors - warns} notes")
    return 1 if any(f[0] == "error" for f in findings) else 0


def _fmt_stats(stats):
    return "  ".join(f"{k} {v}" for k, v in stats.items())


def cmd_show(a, scale, canon):
    key, char = C.get(canon, a.name)
    stats, applied = S.effective(char, a.form)
    realm = f"{char['realm']}, fights as " if char.get("realm") else ""
    print(f"{key}  ({realm}{S.tier_of(scale, S.overall(stats))}, overall {S.overall(stats)})  "
          f"{char.get('status', 'alive')} at {char.get('location', '?')}")
    print("  " + _fmt_stats(stats))
    for line in applied:
        print("  + " + line)
    ev = S.evidence(scale, char)
    for s in S.STATS:
        e = ev[s]
        print(f"  evidence {s}: {e['supported']} ({e['basis']}, {e['count']} feats, {len(e['outliers'])} outliers)")
    for k in ("abilities", "items", "knows"):
        if char.get(k):
            print(f"  {k}: " + ", ".join(char[k]))
    return 0


def _print_matchup(m):
    print(f"{m['a']} ({m['a_tier']}, {m['a_overall']})  vs  {m['b']} ({m['b_tier']}, {m['b_overall']})")
    print(f"  {m['a']}: {_fmt_stats(m['a_stats'])}")
    print(f"  {m['b']}: {_fmt_stats(m['b_stats'])}")
    for line in m["applied"]:
        print("  + " + line)
    dc = "no roll" if m["dc"] is None else f"DC {m['dc']}"
    print(f"  gap {m['gap']:+}  band {m['band']} ({dc})  tech {m['tech_mod']:+}  "
          f"{m['a']} wins {m['chance']:.0%}")
    print("  " + m["verdict"])
    for n in m["notes"]:
        print("  - " + n)


def cmd_compare(a, scale, canon):
    _print_matchup(S.matchup(scale, canon, a.a, a.b, a.a_form, a.b_form))
    return 0


def cmd_roll(a, scale, canon):
    m = S.matchup(scale, canon, a.a, a.b, a.a_form, a.b_form)
    _print_matchup(m)
    if m["dc"] is None:
        print(f"  no roll: {'automatic win' if m['band'] == 'auto' else 'cannot win as things stand'}")
        return 0
    seed = a.seed if a.seed is not None else random.SystemRandom().randrange(10 ** 9)
    die = random.Random(seed).randint(1, 20)
    total = die + m["tech_mod"]
    win = die != 1 and (die == 20 or total >= m["dc"])
    margin = total - m["dc"]
    grade = ("critical success" if die == 20 else "critical failure" if die == 1 else
             "clean win" if margin >= 5 else "narrow win" if win else
             "narrow loss" if margin >= -4 else "heavy loss")
    print(f"  d20 {die} {m['tech_mod']:+} = {total} vs DC {m['dc']}: {grade}  (seed {seed})")
    return 0


def cmd_rate(a, scale, canon):
    rating = S.parse_rating(scale, " ".join(a.rating))
    print(f"{rating}: {S.tier_of(scale, rating)}")
    return 0


def cmd_new(a, scale, canon):
    if C.resolve(canon, a.name) in canon["characters"] and C.resolve(canon, a.name).lower() == a.name.lower():
        print(f"error: {a.name} already has a sheet", file=sys.stderr)
        return 2
    base = S.parse_rating(scale, a.realm)
    canon["characters"][a.name] = {
        "aliases": [], "status": "alive", "location": a.location or "?", "realm": a.realm,
        "stats": {s: round(base + a.edge, 1) for s in S.STATS},
        "feats": [], "abilities": [], "items": [], "knows": [], "conditions": []}
    C.save("canon.json", canon, a.data)
    print(f"Added {a.name}: {a.realm} = {base}, edge {a.edge:+} -> all stats {round(base + a.edge, 1)}. "
          "Record feats to justify anything above the realm baseline.")
    return 0


def cmd_rules(a, scale, canon):
    for i, rule in enumerate(C.load("rules.json", a.data).get("house_rules", []), 1):
        print(f"  {i}. {rule}")
    return 0


def cmd_ladder(a, scale, canon):
    for t in sorted(scale["tiers"], key=lambda t: t["floor"]):
        stages = f"{t['stages']} stages" if t.get("stages", 1) > 1 else ""
        print(f"  {t['floor']:>4}+  {t['name']:<24} {t.get('abbr', ''):<4} {stages:<10} {t.get('benchmark', '')}")
    print("\nRanking by overall rating:")
    rows = sorted(((S.overall(S.effective(c)[0]), n, c) for n, c in canon["characters"].items()), key=lambda r: -r[0])
    for score, name, c in rows:
        print(f"  {score:>6}  {name:<20} {S.tier_of(scale, score)}" + ("  (dead)" if c.get("status") == "dead" else ""))
    return 0


def cmd_audit(a, scale, canon):
    return _report(S.audit(scale, canon), a.json)


def _claims(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cmd_check(a, scale, canon):
    return _report(R.check(scale, canon, _claims(a.claims)), a.json)


def cmd_commit(a, scale, canon):
    claims = _claims(a.claims)
    findings = R.check(scale, canon, claims)
    if any(f[0] == "error" for f in findings) and not a.force:
        _report(findings)
        print("Not committed. Fix the errors, or pass --force if the GM has ruled on them.")
        return 1
    for line in R.commit(canon, claims):
        print("  " + line)
    C.save("canon.json", canon, a.data)
    print(f"Committed scene {claims.get('scene', '?')}.")
    return 0


def cmd_lint(a, scale, canon):
    with open(a.scene, encoding="utf-8") as f:
        return _report(L.lint(f.read(), C.load("rules.json", a.data)), a.json)


def cmd_status(a, scale, canon):
    print(f"Day {canon.get('clock', {}).get('day', 0)}, secret ladder rung {canon.get('rung', 0)}, "
          f"{len(canon.get('scenes', []))} scenes committed")
    for name, c in canon["characters"].items():
        conds = ", ".join(x["name"] for x in c.get("conditions", [])) or "none"
        print(f"  {name:<20} {c.get('status', 'alive'):<6} {c.get('location', '?'):<22} conditions: {conds}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="bot.py", description="Canon keeper, power scaler and scene reviewer.")
    p.add_argument("--data", help="directory holding scale.json, canon.json and rules.json")
    p.add_argument("--campaign", "-c", help="use campaigns/<name>/ as the data directory")
    sub = p.add_subparsers(dest="cmd")

    def add(name, fn, help_):
        sp = sub.add_parser(name, help=help_)
        sp.set_defaults(fn=fn)
        return sp

    add("status", cmd_status, "world clock, who is where, who is hurt")
    add("ladder", cmd_ladder, "the tier ladder and the current ranking")
    sp = add("show", cmd_show, "one character's sheet and the evidence behind it")
    sp.add_argument("name"); sp.add_argument("--form")
    sp = add("rate", cmd_rate, "convert between a rating and a tier or realm, e.g. `rate B-rank` or `rate 46.7`")
    sp.add_argument("rating", nargs="+")
    sp = add("new", cmd_new, "add a character sheet from a tier or realm")
    sp.add_argument("name"); sp.add_argument("realm"); sp.add_argument("--edge", type=float, default=0)
    sp.add_argument("--location")
    add("rules", cmd_rules, "the campaign's house rules, for the reviewer to check by reading")
    for name, fn, h in (("compare", cmd_compare, "judge a matchup"), ("roll", cmd_roll, "judge a matchup and roll it")):
        sp = add(name, fn, h)
        sp.add_argument("a"); sp.add_argument("b")
        sp.add_argument("--a-form"); sp.add_argument("--b-form")
        if name == "roll":
            sp.add_argument("--seed", type=int)
    sp = add("audit", cmd_audit, "find inflated stats, outliers and contradictory results")
    sp.add_argument("--json", action="store_true")
    sp = add("check", cmd_check, "check a scene's claims against canon")
    sp.add_argument("claims"); sp.add_argument("--json", action="store_true")
    sp = add("commit", cmd_commit, "check, then write a scene's claims into canon")
    sp.add_argument("claims"); sp.add_argument("--force", action="store_true")
    sp = add("lint", cmd_lint, "format and prose checks on a scene file")
    sp.add_argument("scene"); sp.add_argument("--json", action="store_true")
    sub.add_parser("help", help="show this help")

    a = p.parse_args(argv)
    if not getattr(a, "fn", None):
        p.print_help()
        return 0
    if a.campaign:
        a.data = C.campaign_dir(a.campaign)
    try:
        scale, canon = C.load("scale.json", a.data), C.load("canon.json", a.data)
        return a.fn(a, scale, canon)
    except (KeyError, FileNotFoundError) as e:  # bad name, realm or data directory
        print(f"error: {e.args[0] if isinstance(e, KeyError) else e}", file=sys.stderr)
        return 2
