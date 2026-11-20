"""Command line. Run `python3 bot.py help`."""
import argparse
import json
import os
import sys

from . import archive as AR
from . import ahead as AH
from . import beats as BE
from . import book as B
from . import clues as CL
from . import lore as LO
from . import loop as LP
from . import growth as GR
from . import people as PE
from . import rulings as RU
from . import quests as QU
from . import scale as S
from . import tech as TE
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
    sp = sub.add_parser("archive", help="archivist: add <scene file> | import <story file> | list | book | recap [n] | choice <n> <text> | summary <n> <text> | chapter <n> <name>")
    sp.add_argument("verb", choices=["add", "import", "list", "book", "recap", "choice", "summary", "chapter", "title"])
    sp.add_argument("args", nargs="*"); sp.add_argument("--write", action="store_true")
    sp.add_argument("--title"); sp.add_argument("--chapter"); sp.add_argument("--choice"); sp.add_argument("--day", type=int); sp.add_argument("--time")
    sp.add_argument("--raw", action="store_true", help="book: keep dice lines and option menus")
    sp = sub.add_parser("tech", help="arsenal: init | list | install | add <id> name=.. action=.. skill=.. [mastery=N] [effect.kp_mult=1.3] [cost.fatigue=2] [when.read=1] [opens=1] [note=..] | rm <id>")
    sp.add_argument("verb", choices=["init", "list", "install", "add", "rm"]); sp.add_argument("args", nargs="*")
    sp.add_argument("--write", action="store_true")
    sp = sub.add_parser("move", help="fight referee: start <foe> | attack | defend | read | result <intent> <TIER> [technique] | status | end")
    sp.add_argument("verb", choices=["start", "attack", "defend", "read", "result", "status", "end"])
    sp.add_argument("args", nargs="*"); sp.add_argument("--write", action="store_true")
    sp = sub.add_parser("quest", help="quest log: list | add <id> k=v.. | step <id> <n> | done <id> | fail <id> | sizes")
    sp.add_argument("verb", choices=["list", "add", "step", "done", "fail", "sizes"]); sp.add_argument("args", nargs="*")
    sp.add_argument("--write", action="store_true"); sp.add_argument("--gm", action="store_true")
    sp = sub.add_parser("beats", help="beat tracker: init | status | mark <id> delivered|changed|skipped [note]")
    sp.add_argument("verb", choices=["init", "status", "mark"]); sp.add_argument("args", nargs="*")
    sp.add_argument("--write", action="store_true"); sp.add_argument("--gm", action="store_true")
    sp = sub.add_parser("lore", help="lore keeper: init | add <term> kind=.. text=.. [place=..] | find <words> | unseen | callbacks | places")
    sp.add_argument("verb", choices=["init", "add", "find", "unseen", "callbacks", "places"]); sp.add_argument("args", nargs="*")
    sp.add_argument("--write", action="store_true")
    sp = sub.add_parser("ambient", help="world dresser: date, weather, place, regulars, a callback, unseen lore, the wider world")
    sp.add_argument("place", nargs="?"); sp.add_argument("--gm", action="store_true")
    sp = sub.add_parser("setup", help="first-time setup of every tracker, in one go (safe to repeat)")
    sp.add_argument("--write", action="store_true")
    sp = sub.add_parser("before", help="what to have in hand before writing the next scene")
    sp.add_argument("--foe", help="also forecast a fight against this foe")
    sub.add_parser("after", help="what the scene just played leaves to do")
    sub.add_parser("growth", help="skill growth that is due from what Mori has done, with the System message and gm.py command")
    sp = sub.add_parser("ahead", help="lookahead: what is coming, what he cannot survive or afford, and the honest ways back")
    sp.add_argument("days", nargs="?", type=int, default=3)
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
        if a.cmd == "setup":
            return LP.setup(a.game, a.write)
        g = Game(a.game)
        code = 0
        if a.cmd == "ambient":
            print("\n".join(LO.ambient(g, LO.load(g), a.place, a.gm)))
            return 0
        if a.cmd == "lore":
            data, plan, v, r = LO.load(g), Plan(g), a.verb, a.args
            if v == "init":
                plan.note(f"{LO.init(g, data)} places read from the bible")
            elif v == "add":
                LO.add(g, data, r[0], dict(x.split("=", 1) for x in r[1:]), plan)
            elif v == "find":
                print("\n".join("  " + x for x in LO.find(g, data, " ".join(r))) or "  nothing established about that: you are free to invent it, then record it with `lore add`")
            elif v == "unseen":
                for section, items in LO.unseen(g).items():
                    print(f"  {section}: " + ", ".join(t["term"] for t in items[:14]) + (f" (+{len(items) - 14})" if len(items) > 14 else ""))
            elif v == "callbacks":
                for e, n, last in LO.callbacks(g, data, 8):
                    print(f"  {e['id']} [{e['kind']}] {e['term']}: {e['text'][:90]} | seen in {n} scene(s)" + (f", last scene {last}" if last else ""))
            elif v == "places":
                for realm, card in data.get("realms", {}).items():
                    here = {k: pl for k, pl in data["places"].items() if pl.get("realm", "Earth") == realm}
                    print(f"  {realm}: {len(card['entries'])} lore entries, {len(here)} places" + (f" | {card['desc'][:90]}" if card["desc"] else ""))
                    for k, pl in here.items():
                        print(f"      {k}: {len(pl['details'])} details, {len(pl['regulars'])} regulars, {len(pl['changes'])} changes")
            if v in ("init", "add"):
                plan.put_json("lore.json", data)
                return plan.finish(a.write)
            return 0
        if a.cmd == "before":
            return LP.before(g, a.foe)
        if a.cmd == "after":
            return LP.after(g)
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
            print(f"Jin Mori Lv{g.ledger['level']}: index {idx} -> {S.rank_of(idx)} on Earth; {S.rank_of(idx, 'murim')} by the Murim's measure (body alone, no gi)")
            rows = sorted(((S.foe_index(f) or 0, k, f) for k, f in g.foes.items()), key=lambda r: r[0])
            for i, k, f in rows:
                print(f"  {i:>8}  {S.rank_of(i):<15} {S.rank_of(i, 'murim'):<15} {f.get('name', k)} [{f.get('type', '?')}]")
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
            elif v == "import":
                with open(r[0] if os.path.exists(r[0]) else g.path(r[0]), encoding="utf-8") as f:
                    AR.import_story(g, data, f.read(), plan)
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
        if a.cmd == "tech":
            techs, plan = TE.load(g), Plan(g)
            if a.verb == "init":
                new = {k: v for k, v in TE.PROPOSED.items() if k not in techs}
                techs.update(json.loads(json.dumps(new)))
                plan.note(f"{len(new)} proposed technique cards added: {', '.join(new) or '-'}. The numbers are a proposal: edit techniques.json")
                plan.put_json("techniques.json", techs)
                code = plan.finish(a.write)
            elif a.verb == "install":
                TE.install(g, techs, plan)
                code = plan.finish(a.write)
            elif a.verb == "rm":
                if techs.pop(a.args[0], None) is None:
                    plan.error(f"no technique {a.args[0]}")
                plan.put_json("techniques.json", techs)
                code = plan.finish(a.write)
            elif a.verb == "add":
                kv = dict(x.split("=", 1) for x in a.args[1:])
                card = {"name": kv.get("name", a.args[0]), "action": kv.get("action", "hit"), "needs": {}, "effect": {}, "note": kv.get("note", "")}
                if card["action"] not in ("hit", "dodge", "read", "grapple", "endure", "sense", "chase", "throw"):
                    plan.error("action must be a gm.py action: hit, dodge, read, grapple, endure, sense, chase or throw")
                if "skill" in kv:
                    card["needs"] = {"skill": kv["skill"], "mastery": int(kv.get("mastery", 1))}
                else:
                    plan.error("skill=<the skill on his sheet that grants it> is required, so the card unlocks and grows with that skill")
                for k, v in kv.items():
                    if "." in k:
                        group, key = k.split(".", 1)
                        if group not in ("effect", "cost", "when", "growth"):
                            plan.error(f"unknown field {k}")
                        else:
                            card.setdefault(group, {})[key] = json.loads(v) if v.replace(".", "", 1).lstrip("-").isdigit() else v
                if "strike" in kv:
                    card["strike"] = kv["strike"]
                if kv.get("opens") in ("1", "true"):
                    card["opens"] = True
                if "when" in card:
                    card["when"] = {k: bool(v) for k, v in card["when"].items()}
                if not card["effect"]:
                    plan.error("a technique must change a number: give at least one effect.<key>=<value> (kp_mult, dc_shift, tech, taken_mult, strike_mult...)")
                techs[a.args[0]] = card
                plan.note(f"technique card {a.args[0]}: {card}")
                plan.put_json("techniques.json", techs)
                code = plan.finish(a.write)
            else:
                own = TE.owned(g.ledger, techs)
                for tid, t in techs.items():
                    need = t.get("needs", {})
                    if tid in own:
                        e, c = TE.scaled(g.ledger, t)
                        lv = TE.level(g.ledger, t)
                        print(f"  OWNED  {t['name']:<36} {t['action']:<5} now {e} cost {c or '-'}"
                              + (f"  (base {t.get('effect', {})} cost {t.get('cost', {}) or '-'}; +{lv} from mastery and use)" if lv else "")
                              + f" | used {t.get('used', 0)}x, rank {TE.rank(t)}")
                    else:
                        print(f"  locked {t['name']:<36} {t['action']:<5} opens at {need.get('skill', '-')} mastery {need.get('mastery', '')}")
                    print(f"         {t.get('note', '')}" + (f"  [only when: {', '.join(t['when'])}]" if t.get("when") else ""))
                if not techs:
                    print("  no technique cards: run `tech init --write`")
                for m in TE.missing_cards(g, techs):
                    print(f"  WARN no card for {m}: he owns it but cannot use it in a fight. Add one with `tech add`")
                if TE.stale(g, techs):
                    print("  WARN the ledger's technique effects are behind his current skill: run `tech install --write`")
        if a.cmd == "move":
            techs, plan, v, r = TE.load(g), Plan(g), a.verb, a.args
            if v == "start":
                fid = g.foe(r[0])
                plan.put_json("fight.json", {"foe": fid, "shown": [], "read": False, "opening": False, "lost": 0, "exchanges": 0, "started": g.stamp()})
                plan.note(f"fight started against {g.foes[fid]['name']}. Each exchange is ONE `move attack` and ONE `move defend` (or `move read` in place of the attack)")
                code = plan.finish(a.write)
            elif v in ("attack", "defend", "read"):
                fid, state, mod, shift, opts = TE.recommend(g, techs, v, r[0] if r else None)
                best = opts[0]
                name = best["tech"]["name"] if best["tech"] else {"attack": "plain kick", "defend": "plain dodge", "read": "plain read"}[v]
                print(f"  Mori uses: {name}" + (" at the weak point" if best["weak"] else "") + f"  ({best['R']['p']}% to succeed)")
                if best["tech"]:
                    print(f"    why: {best['tech'].get('note', '')}")
                    if best["cost"]:
                        print(f"    cost after the roll: {best['cost']}")
                if mod:
                    print(f"    includes mod={mod:+d} from rulings (adaptation and the like)")
                if shift:
                    print("    includes shift=-3: the foe is off balance")
                for o in opts[1:4]:
                    n = o["tech"]["name"] if o["tech"] else "plain"
                    print(f"    passed over: {n}{' (weak point)' if o['weak'] else ''} at {o['R']['p']}%")
                print("  roll it with:\n    " + TE.gm_line(TE.INTENT[v], fid, best, mod, shift))
                print(f"  then record it: bot.py move result {v} <STRONG|CLEAN|PARTIAL|FAIL>" + (f" {best['id']}" if best["id"] else "") + " --write")
                if TE.stale(g, techs):
                    print("  !! the ledger's technique effects are behind his current skill: run `bot.py tech install --write` first")
            elif v == "result":
                state, tier = TE.record(g, techs, r[0], r[1], r[2] if len(r) > 2 else None, plan)
                if state:
                    plan.put_json("fight.json", state)
                code = plan.finish(a.write)
            elif v == "status":
                st = TE.fight_state(g)
                print(f"  {st}" if st else "  no fight in progress")
            elif v == "end":
                st = TE.fight_state(g)
                if st:
                    rdata = RU.load(g)
                    for x in rdata["rulings"]:
                        if x["kind"] == "bonus":
                            rdata["uses"].pop(f"{x['id']}:{st['foe']}", None)
                    plan.put_json("rulings.json", rdata)
                    plan.put_text("fight.json", "")
                    plan.note(f"fight against {st['foe']} closed after {st.get('exchanges', 0)} rolls; per-foe bonuses cleared")
                code = plan.finish(a.write)
        if a.cmd == "quest":
            data, plan, v, r = QU.load(g), Plan(g), a.verb, a.args
            if v == "list":
                print("\n".join(QU.listing(g, data, a.gm)))
                for sev, msg in QU.findings(g, data):
                    print(f"  {sev} {msg}")
            elif v == "sizes":
                for k, pct in QU.SIZES.items():
                    print(f"  {k:<7} {pct:>3}% of a level = {QU.xp_value(g.ledger, k)} XP at Lv{g.ledger['level']}")
            else:
                if v == "add":
                    QU.add(g, data, r[0], dict(x.split("=", 1) for x in r[1:]), plan)
                elif v == "step":
                    q = QU.get(data, r[0])
                    q["steps"][int(r[1]) - 1]["done"] = True
                    plan.note(f"{r[0]}: step {r[1]} done ({sum(s['done'] for s in q['steps'])}/{len(q['steps'])})")
                else:
                    QU.finish(g, data, r[0], plan, a.write, failed=(v == "fail"))
                plan.put_json("quests.json", data)
                code = plan.finish(a.write)
        if a.cmd == "beats":
            data, plan, v, r = BE.load(g), Plan(g), a.verb, a.args
            if v == "init":
                plan.note(f"{BE.init(g, data)} planned items read from the arc cards")
            elif v == "mark":
                BE.mark(data, r[0], r[1], " ".join(r[2:]), g.stamp(), plan)
            if v == "status":
                rows, finds = BE.status(g, data, a.gm)
                print("\n".join(rows))
                for sev, msg in finds:
                    print(f"  {sev} {msg}")
            else:
                plan.put_json("beats.json", data)
                code = plan.finish(a.write)
        if a.cmd in ("growth", "all"):
            print("GROWTH")
            due, progress = GR.check(g)
            for d in due:
                print(f"  DUE {d['skill']}: {d['from'] or 'not owned'} -> {d['to']} ({d['count']} counted). Announce it now, unasked:")
                for line in d["message"]:
                    print("      " + line)
                print("      then: " + d["cmd"] + (" ; bot.py tech install --write" if "Taekwondo" in d["skill"] else ""))
                if d["note"]:
                    print("      note: " + d["note"])
            for line in progress:
                print("  " + line)
            if not due:
                print("  nothing due")
        if a.cmd in ("ahead", "all"):
            print("AHEAD" + (f" (next {a.days} days)" if a.cmd == "ahead" else ""))
            finds, ways = AH.report(g, getattr(a, "days", 3))
            for sev, msg in finds:
                print(f"  {sev} {msg}")
            print("  honest ways back:")
            for w in ways:
                print(f"    - {w}")
            line, c = verdict(finds); print("  " + line)
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
            extra += [("WARN", f"no technique card for {m}") for m in TE.missing_cards(g, TE.load(g))]
            extra += [("WARN", "technique effects in the ledger are behind his skill: run `tech install --write`")] if TE.stale(g, TE.load(g)) else []
            extra += [f for f in QU.findings(g, QU.load(g))] + [f for f in BE.status(g, BE.load(g))[1]]
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
