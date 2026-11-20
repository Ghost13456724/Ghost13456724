"""Command line. Run `python3 bot.py help`."""
import argparse
import json
import os
import sys

from . import scale as S
from . import scene as SC
from . import sync as SY
from .game import Game


def verdict(finds):
    fails = sum(1 for f in finds if f[0] == "FAIL")
    warns = sum(1 for f in finds if f[0] == "WARN")
    word = "FIX" if fails else "LOOK" if warns else "CLEAN"
    return f"{word}: {fails} errors, {warns} warnings, {len(finds) - fails - warns} notes", 1 if fails else 0


def show_matchup(m):
    f = m["foe"]
    print(f"{f.get('name', m['id'])} [{f.get('type', '?')}] SPD {f.get('SPD')} ATK {f.get('ATK')} T {f.get('T')}/{f.get('T_weak')} "
          f"| card: {f.get('dc')} | {S.rank_of(S.foe_index(f)) if S.foe_index(f) else '?'} band")
    for line in m["lines"]:
        print("  " + line)
    if "taken" in m:
        lo, hi, tr = m["taken"]
        a, b = m["hits_to_down"]
        print(f"  its hit on Mori: {lo}-{hi} HP (TR {tr:.2f}); from full, down in {a}" + (f"-{b}" if b and b != a else "") + " clean hits")
    fr = m["fresh"]
    print(f"  whole fight, rested Lv{m['level']}: Mori wins {fr['win']}%"
          + (f" in ~{fr['rounds']} rounds, ending on ~{fr['hp_left']}% HP" if fr["rounds"] else ""))
    if m["now"]:
        print(f"  whole fight, as he is right now: Mori wins {m['now']['win']}%")
    print(f"  verdict: {m['class'].upper()}" + ("; he cannot wound it, so a win needs help, a trick or a rule to break" if m["cant_hurt"] else ""))


def main(argv=None):
    p = argparse.ArgumentParser(prog="bot.py", description="Power scaling, state audit and scene checks for a gm.py game folder.")
    p.add_argument("--game", "-g", default=os.environ.get("RPG_GAME", "."), help="game folder (has ledger.json and gm.py); or set RPG_GAME")
    sub = p.add_subparsers(dest="cmd")
    sp = sub.add_parser("fight", help="forecast a whole fight against a foe card")
    sp.add_argument("foe"); sp.add_argument("--level", type=int, help="project Mori to this level (+1 every stat per level)")
    sub.add_parser("foes", help="audit every foe card and rank them by danger")
    sp = sub.add_parser("design", help="build a foe card for the fight you want")
    sp.add_argument("role", help="grunt | even | elite | boss")
    sp.add_argument("--level", type=int); sp.add_argument("--name", default="New Foe"); sp.add_argument("--type", default="beast")
    sp.add_argument("--rank", help="scale the card into a rank band, e.g. C-rank")
    sub.add_parser("rank", help="where Mori and every foe sit on the rank ladder")
    sub.add_parser("sync", help="check the ledger, STATE_NOW, log and event clock against each other")
    sp = sub.add_parser("scene", help="mechanical check of a scene file against the ledger and log")
    sp.add_argument("file", nargs="?", default="LAST_SCENES.md"); sp.add_argument("--turn", action="store_true", help="a full player-facing turn: require the options block")
    sub.add_parser("all", help="sync + foes + scene on LAST_SCENES.md")
    sub.add_parser("help")
    a = p.parse_args(argv)
    if a.cmd in (None, "help"):
        p.print_help()
        return 0
    try:
        g = Game(a.game)
        code = 0
        if a.cmd == "fight":
            show_matchup(S.matchup(g, a.foe, a.level))
        if a.cmd == "design":
            card, m = S.design(g, a.role, a.level, a.name, a.type, a.rank)
            show_matchup(m)
            if m["target"] is not None and abs(m["fresh"]["win"] - m["target"]) > 15:
                print(f"  note: aimed for {m['target']}% and this is the closest card. At these stats one point of "
                      "toughness flips the kill table, so adjust T or T_weak by hand if you want it in between.")
            fid = a.name.lower().replace(" ", "_")
            print(f"\nadd it with:\n  python3 gm.py foe add {fid} '{json.dumps(card, ensure_ascii=False)}'")
        if a.cmd == "rank":
            idx = S.mori_index(g.ledger)
            print(f"Jin Mori Lv{g.ledger['level']}: index {idx} -> {S.rank_of(idx)}")
            rows = sorted(((S.foe_index(f) or 0, k, f) for k, f in g.foes.items()), key=lambda r: r[0])
            for i, k, f in rows:
                print(f"  {i:>8}  {S.rank_of(i):<15} {f.get('name', k)} [{f.get('type', '?')}]")
            print("(bands are a proposed ruling in novelbot/ranks.json; edit them there)")
        if a.cmd in ("sync", "all"):
            finds = SY.audit(g)
            print("STATE")
            for sev, msg in finds:
                print(f"  {sev} {msg}")
            line, c = verdict(finds); print("  " + line); code |= c
        if a.cmd in ("foes", "all"):
            finds, results = S.audit(g)
            print("FOES (rested Mori, whole fight)")
            for fid, m in sorted(results.items(), key=lambda kv: -kv[1]["fresh"]["win"]):
                f = m["foe"]
                print(f"  {m['fresh']['win']:>3}%  {m['class']:<13} {f['name']:<26} card: {f['dc']}")
            for sev, fid, msg in finds:
                print(f"  {sev} {fid}: {msg}")
            line, c = verdict(finds); print("  " + line); code |= c
        if a.cmd in ("scene", "all"):
            name = getattr(a, "file", "LAST_SCENES.md")
            path = name if os.path.exists(name) else g.path(name)
            with open(path, encoding="utf-8") as f:
                finds = SC.check(g, f.read(), getattr(a, "turn", False))
            print(f"SCENE {os.path.basename(path)}")
            for sev, msg in finds:
                print(f"  {sev} {msg}")
            line, c = verdict(finds); print("  " + line); code |= c
        return code
    except (KeyError, FileNotFoundError) as e:
        print(f"error: {e.args[0] if isinstance(e, KeyError) else e}", file=sys.stderr)
        return 2
