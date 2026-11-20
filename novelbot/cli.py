"""Command line. Run `python3 bot.py help`."""
import argparse
import json
import os
import sys

from . import archive as AR
from . import book as B
from . import clues as CL
from . import people as PE
from . import rulings as RU
from . import scale as S
from . import world as W
from .game import Plan
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
    if m.get("defences", 1) > 1:
        print(f"  (played with {m['defences']} defensive rolls per attack)")
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
    sp.add_argument("--defences", type=int, default=1, help="defensive rolls Mori makes per attack of his own (default 1)")
    sub.add_parser("foes", help="audit every foe card and rank them by danger")
    sp = sub.add_parser("design", help="build a foe card for the fight you want")
    sp.add_argument("role", help="grunt | even | elite | boss")
    sp.add_argument("--level", type=int); sp.add_argument("--name", default="New Foe"); sp.add_argument("--type", default="beast")
    sp.add_argument("--rank", help="scale the card into a rank band, e.g. C-rank")
    sub.add_parser("rank", help="where Mori and every foe sit on the rank ladder")
    sub.add_parser("sync", help="check the ledger, STATE_NOW, log and event clock against each other")
    sp = sub.add_parser("scene", help="mechanical check of a scene file against the ledger and log")
    sp.add_argument("file", nargs="?", default="LAST_SCENES.md"); sp.add_argument("--turn", action="store_true", help="a full player-facing turn: require the options block")
    sub.add_parser("all", help="sync + foes + scene on LAST_SCENES.md + people, clues and world checks")
    sp = sub.add_parser("book", help="bookkeeper: apply <delta.json> | fix | template | save <name> | load <name>")
    sp.add_argument("verb", choices=["apply", "fix", "template", "save", "load"]); sp.add_argument("arg", nargs="?")
    sp.add_argument("--write", action="store_true", help="actually change the files (default is a dry run)")
    sp = sub.add_parser("people", help="people tracker: init | show [name] | scan | set <name> k=v ...")
    sp.add_argument("verb", choices=["init", "show", "scan", "set"]); sp.add_argument("args", nargs="*")
    sp.add_argument("--write", action="store_true")
    sp = sub.add_parser("clues", help="clue ladder: init | status | next | place <id> | reveal <rung> | watch")
    sp.add_argument("verb", choices=["init", "status", "next", "place", "reveal", "watch"]); sp.add_argument("arg", nargs="?")
    sp.add_argument("--write", action="store_true"); sp.add_argument("--force", action="store_true")
    sp.add_argument("--gm", action="store_true", help="print the secret text too (GM eyes only)")
    sp = sub.add_parser("rules", help="rulings and lessons: list | scan | import <file> | add <id> k=v.. | set <id> k=v.. | rm <id> | "
                                      "bump <id> <foe> | reset <id> <foe> | use <id> | mods <foe> | dice | audit")
    sp.add_argument("verb", choices=["list", "scan", "import", "add", "set", "rm", "bump", "reset", "use", "mods", "dice", "audit"])
    sp.add_argument("args", nargs="*"); sp.add_argument("--write", action="store_true")
    sp = sub.add_parser("archive", help="archivist: add <scene file> | list | book | recap [n] | choice <n> <text> | summary <n> <text> | chapter <n> <name>")
    sp.add_argument("verb", choices=["add", "list", "book", "recap", "choice", "summary", "chapter", "title"])
    sp.add_argument("args", nargs="*"); sp.add_argument("--write", action="store_true")
    sp.add_argument("--title"); sp.add_argument("--chapter"); sp.add_argument("--choice"); sp.add_argument("--day", type=int); sp.add_argument("--time")
    sp.add_argument("--raw", action="store_true", help="book: keep dice lines and option menus")
    sp = sub.add_parser("world", help="world clock: init | status | tick | seen <trace id>")
    sp.add_argument("verb", choices=["init", "status", "tick", "seen"]); sp.add_argument("arg", nargs="?")
    sp.add_argument("--rule", action="append", default=[], help="for a step Mori could have stopped: <step id>=stopped|happened")
    sp.add_argument("--write", action="store_true"); sp.add_argument("--gm", action="store_true")
    sub.add_parser("help")
    a = p.parse_args(argv)
    if a.cmd in (None, "help"):
        p.print_help()
        return 0
    try:
        g = Game(a.game)
        code = 0
        if a.cmd == "fight":
            show_matchup(S.matchup(g, a.foe, a.level, defences=a.defences))
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
        if a.cmd == "book":
            if a.verb == "template":
                print(json.dumps(B.TEMPLATE, indent=1, ensure_ascii=False))
            elif a.verb == "fix":
                code = B.fix(g, a.write)
            elif a.verb == "apply":
                with open(a.arg, encoding="utf-8") as f:
                    code = B.apply(g, json.load(f), a.write)
            else:
                code = B.save_slot(g, a.verb, a.arg)
        if a.cmd == "people":
            data, plan = PE.load(g), Plan(g)
            if a.verb == "init":
                data, added = PE.init(g)
                plan.note(f"{len(added)} people seeded from the bible: {', '.join(added) or '-'}")
            elif a.verb == "show":
                print("\n".join(PE.show(data, a.args[0] if a.args else None)) or "  nobody yet: run `people init`")
            elif a.verb == "scan":
                for key, name, delta, where in PE.scan(g, data):
                    if PE.find(data, name):
                        PE.apply_update(data, name, {"trust": f"{delta:+d}"}, g.stamp(), plan)
                        data.setdefault("counted", []).append(key)
                    else:
                        plan.note(f"{name} is in the log but not in the bible's cast: adding them")
                        PE.apply_update(data, name, {"trust": f"{delta:+d}"}, g.stamp(), plan)
                        data.setdefault("counted", []).append(key)
            elif a.verb == "set":
                upd = dict(x.split("=", 1) for x in a.args[1:])
                for k in ("learn",):
                    if k in upd:
                        upd[k] = upd[k].split(",")
                PE.apply_update(data, a.args[0], upd, g.stamp(), plan)
            if a.verb != "show":
                plan.put_json("people.json", data)
                code = plan.finish(a.write)
        if a.cmd == "clues":
            data, plan = CL.load(g), Plan(g)
            if a.verb == "init":
                data = CL.init(g)
                plan.note(f"{len(data['ladder'])} rungs and {len(data['pool'])} unassigned clues read from the GM files; story is at rung {data['rung']}")
            if a.verb in ("status", "init"):
                rows, finds = CL.status(data, a.gm)
                print("\n".join(rows))
                for sev, msg in finds:
                    print(f"  {sev} {msg}")
            elif a.verb == "next":
                print("\n".join("  " + r for r in CL.next_clues(data, a.gm)) or "  no unplaced clue for the next rung: the keeper must write some")
            elif a.verb == "place":
                CL.place(data, a.arg, g.stamp(), plan)
            elif a.verb == "reveal":
                CL.reveal(data, int(a.arg), plan, a.force)
            elif a.verb == "watch":
                plan.note(f"{len(CL.watch_list(data))} watch patterns are active for the scene check (read straight from clues.json)")
            if a.verb in ("init", "place", "reveal"):
                plan.put_json("clues.json", data)
                code = plan.finish(a.write)
            elif a.verb == "watch":
                plan.finish(False)
        if a.cmd == "world":
            data, plan = W.load(g), Plan(g)
            if a.verb == "init":
                data, added = W.init(g)
                plan.note(f"{len(added)} factions seeded from the bible: {', '.join(added) or '-'}")
            elif a.verb == "status":
                rows, finds = W.status(g, data, a.gm)
                print("\n".join(rows))
                for sev, msg in finds:
                    print(f"  {sev} {msg}")
            elif a.verb == "tick":
                W.tick(g, data, plan, dict(r.split("=", 1) for r in a.rule))
            elif a.verb == "seen":
                W.surface(data, a.arg, g.stamp(), plan)
            if a.verb != "status":
                plan.put_json("factions.json", data)
                code = plan.finish(a.write)
        if a.cmd == "rules":
            data, plan, v, r = RU.load(g), Plan(g), a.verb, a.args
            kv = dict(x.split("=", 1) for x in r[1:] if "=" in x)
            for k in ("step", "max", "uses"):
                if k in kv:
                    kv[k] = int(kv[k])
            if "reviewed" in kv:
                kv["reviewed"] = kv["reviewed"].lower() in ("1", "true", "yes")
            if v == "list":
                for x in data["rulings"]:
                    tag = "" if x.get("reviewed", True) else " (unreviewed)"
                    print(f"  {x['id']:<24} {x['kind']:<8} {x['source']:<12}{tag} {x['text'][:110]}")
                print(f"  {len(data['rulings'])} rulings") if data["rulings"] else print("  none yet: run `rules scan --write`")
            elif v == "scan":
                RU.scan(g, data, plan)
            elif v == "import":
                with open(r[0], encoding="utf-8") as f:
                    RU.import_lessons(data, f.read(), os.path.basename(os.path.dirname(os.path.abspath(r[0]))) + "/" + os.path.basename(r[0]), plan)
            elif v == "add":
                if any(x["id"] == r[0] for x in data["rulings"]):
                    plan.error(f"ruling '{r[0]}' already exists; use `rules set`")
                elif kv.get("kind") not in ("bonus", "limited", "lesson", "rule") or not kv.get("text"):
                    plan.error("a ruling needs kind=bonus|limited|lesson|rule and text=...")
                else:
                    data["rulings"].append(dict({"id": r[0], "source": g.stamp(), "reviewed": True}, **kv))
                    plan.note(f"ruling {r[0]} added")
            elif v == "set":
                RU.get(data, r[0]).update(dict({"reviewed": True}, **kv))
                plan.note(f"ruling {r[0]} updated")
            elif v == "rm":
                RU.get(data, r[0])
                data["rulings"] = [x for x in data["rulings"] if x["id"] != r[0]]
                plan.note(f"ruling {r[0]} removed")
            elif v in ("bump", "reset"):
                RU.bump(g, data, r[0], g.foe(r[1]), plan, reset=(v == "reset"))
            elif v == "use":
                RU.use(g, data, r[0], plan)
            elif v == "mods":
                total, lines = RU.mods(g, data, g.foe(r[0]))
                for line in lines:
                    print("  " + line)
                print(f"  add to the next roll against {g.foe(r[0])}: mod={total:+d}")
            elif v == "dice":
                d = RU.dice(g)
                if d:
                    print(f"  {d['n']} rolls logged; average die {d['mean']} (a fair d20 averages 10.5); natural 1s: {d['ones']}, natural 20s: {d['twenties']}")
                    print(f"  succeeded {d['won']}; the odds offered predicted {d['expected']}")
                    print(f"  average chance offered: {d['avg_chance']}%; {d['under_half']} of {d['n']} rolls were under 50%")
                    print(f"  in fights: {d['attack']} attacks, {d['defence']} defensive rolls")
                else:
                    print("  no rolls in the log yet")
            if v == "audit":
                finds = RU.audit(g, data)
                for sev, msg in finds:
                    print(f"  {sev} {msg}")
                line, code = verdict(finds); print("  " + line)
            elif v not in ("list", "mods", "dice"):
                plan.put_json("rulings.json", data)
                code = plan.finish(a.write)
        if a.cmd == "archive":
            data, plan, v, r = AR.load(g), Plan(g), a.verb, a.args
            if v == "add":
                path = r[0] if os.path.exists(r[0]) else g.path(r[0])
                with open(path, encoding="utf-8") as f:
                    AR.add(g, data, f.read(), plan, a.title, a.chapter, a.choice, a.day, a.time)
            elif v in ("choice", "summary", "chapter", "title"):
                sc = next((x for x in data["scenes"] if x["n"] == int(r[0])), None)
                if sc is None:
                    plan.error(f"no scene {r[0]}")
                else:
                    sc[v] = " ".join(r[1:])
                    plan.note(f"scene {r[0]}: {v} set")
            elif v == "list":
                print("\n".join(AR.listing(data)) or "  the archive is empty: `archive add <scene file> --write`")
            elif v == "recap":
                print("\n".join("  " + x for x in AR.recap(data, int(r[0]) if r else 5)) or "  the archive is empty")
            elif v == "book":
                md, words = AR.build(g, data, novel=not a.raw)
                plan.put_text("archive/BOOK.md", md)
                plan.put_text("archive/BOOK.html", AR.to_html(data["title"], md))
                plan.note(f"book: {len(AR.chapters(data))} chapters, {len(AR.live(data))} scenes, {words:,} words")
            if v not in ("list", "recap"):
                if v != "book":
                    plan.put_json(AR.INDEX, data)
                code = plan.finish(a.write)
        if a.cmd == "all":
            print("RULINGS")
            rfinds = RU.audit(g, RU.load(g))
            for sev, msg in rfinds:
                print(f"  {sev} {msg}")
            line, c = verdict(rfinds); print("  " + line); code |= c
            print("PEOPLE / CLUES / WORLD")
            extra = [("NOTE", f"log has {len(PE.scan(g, PE.load(g)))} trust change(s) not in people.json: run `people scan`")] if PE.scan(g, PE.load(g)) else []
            extra += CL.status(CL.load(g))[1] if g.text("clues.json") else [("NOTE", "no clues.json: run `clues init`")]
            extra += W.status(g, W.load(g))[1]
            arch = AR.load(g)
            if not arch["scenes"]:
                extra.append(("NOTE", "the archive is empty: scenes are not being saved in full (`archive add`)"))
            for sev, msg in extra:
                print(f"  {sev} {msg}")
            print("  " + verdict(extra)[0])
        return code
    except (KeyError, FileNotFoundError, ValueError) as e:
        print(f"error: {e.args[0] if isinstance(e, KeyError) else e}", file=sys.stderr)
        return 2
