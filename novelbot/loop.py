"""The GM's routine in three commands: setup (once), before (each scene), after (each scene).

Each prints only what needs doing, so the GM does not have to remember which of the bots to run."""
from . import ahead as AH
from . import archive as AR
from . import beats as BE
from . import book as B
from . import clues as CL
from . import growth as GR
from . import lore as LO
from . import people as PE
from . import quests as QU
from . import rulings as RU
from . import sync as SY
from . import tech as TE
from . import world as W
from .game import Game, Plan


def setup(folder, write):
    """Everything the first-time setup needs, in order. Safe to run again: each step only adds what is missing."""
    steps = []

    def step(name, fn):
        g = Game(folder)                      # re-open so each step sees the last one's files
        plan = Plan(g)
        print(f"- {name}")
        if fn(g, plan) is not False:
            steps.append(plan.finish(write))

    def people(g, plan):
        data, added = PE.init(g)
        for key, name, delta, _ in PE.scan(g, data):
            PE.apply_update(data, name, {"trust": f"{delta:+d}"}, g.stamp(), plan)
            data.setdefault("counted", []).append(key)
        plan.notes[:] = [f"{len(added)} people from the bible, {len(data.get('counted', []))} trust changes from the log"]
        plan.put_json("people.json", data)

    def clues(g, plan):
        data = CL.init(g)
        plan.note(f"{len(data['ladder'])} rungs, {len(data['pool'])} unassigned clues, story at rung {data['rung']}")
        plan.put_json("clues.json", data)

    def world(g, plan):
        data, added = W.init(g)
        plan.note(f"{len(data['factions'])} factions")
        plan.put_json("factions.json", data)

    def rules(g, plan):
        data = RU.load(g)
        RU.scan(g, data, plan)
        plan.notes[:] = [f"{len(data['rulings'])} rulings and lessons on file"]
        plan.put_json("rulings.json", data)

    def tech(g, plan):
        techs = TE.load(g)
        techs.update({k: v for k, v in TE.PROPOSED.items() if k not in techs})
        plan.put_json("techniques.json", techs)
        TE.install(g, techs, plan)
        plan.notes[:] = [f"{len(techs)} technique cards, {len(TE.owned(g.ledger, techs))} owned and installed"]

    def beats(g, plan):
        data = BE.load(g)
        n = BE.init(g, data)
        plan.note(f"{len(data['beats'])} planned items ({n} new)")
        plan.put_json("beats.json", data)

    def lore(g, plan):
        data = LO.load(g)
        n = LO.init(g, data)
        plan.note(f"{len(data['places'])} places ({n} new)")
        plan.put_json("lore.json", data)

    print("SETUP" + ("" if write else " (dry run: add --write)"))
    step("date and deadline flags", lambda g, plan: bool(B.fix(g, write)) and False)
    step("people", people)
    step("clue ladder", clues)
    step("factions", world)
    step("rulings and lessons", rules)
    step("technique cards", tech)
    step("planned beats", beats)
    step("places and lore", lore)
    print("Next, in this order: bots/CLUE_KEEPER.md, bots/WORLD_CLOCK.md and bots/RULINGS_KEEPER.md once each; "
          "`archive import <story file> --write`; then `bot.py after`.")
    return max(steps or [0])


def after(g):
    """What the scene just played leaves to do."""
    todo, ok = [], []
    fails = [m for s, m in SY.audit(g) if s == "FAIL"]
    warns = [m for s, m in SY.audit(g) if s == "WARN"]
    (todo if fails or warns else ok).append(("STATE", fails + warns, "write the scene's delta and run `book apply <delta> --write`; `book fix --write` repairs dates"))
    due = GR.check(g)[0]
    (todo if due else ok).append(("GROWTH", [f"{d['skill']} {d['from'] or 'new'} -> {d['to']}: show {' '.join(d['message'])} then `{d['cmd']}`" for d in due],
                                  "announce it in the next scene, unasked"))
    q = [m for s, m in QU.findings(g, QU.load(g)) if s == "WARN"]
    (todo if q else ok).append(("QUESTS", q, "complete or fail them; and ask: did Mori just do something the System would reward? (`quest add ... secret=1`, `quest done`)"))
    b = [m for s, m in BE.status(g, BE.load(g))[1] if s == "WARN"]
    (todo if b else ok).append(("BEATS", [f"{len(b)} planned item(s) past their window and still pending"] if b else [], "`beats status --gm`, then mark each delivered, changed or skipped"))
    r = [m for s, m in RU.audit(g, RU.load(g)) if s in ("FAIL", "WARN")]
    (todo if r else ok).append(("RULINGS", r, "`rules scan --write`, give inert skills a number, roll with --apply"))
    t = [f"no card for {m}" for m in TE.missing_cards(g, TE.load(g))] + (["ledger technique effects are stale"] if TE.stale(g, TE.load(g)) else [])
    (todo if t else ok).append(("ARSENAL", t, "`tech add` for new skills, then `tech install --write`"))
    if TE.fight_state(g):
        todo.append(("FIGHT", [f"a fight against {TE.fight_state(g)['foe']} is still open"], "`move end --write` when it is over"))
    w = [m for s, m in W.status(g, W.load(g))[1] if s == "WARN"]
    (todo if w else ok).append(("WORLD", w, "`world tick`, rule on held steps, write agendas for idle factions"))
    c = [m for s, m in CL.status(CL.load(g))[1] if s == "WARN"] if g.text("clues.json") else ["no clues.json"]
    (todo if c else ok).append(("CLUES", c, "`clues place <id>` for clues shown; `clues reveal <rung>` when a truth came out"))
    arch = AR.live(AR.load(g))
    last = arch[-1] if arch else None
    a = [] if last and last.get("summary") and (last["day"], last.get("time")) >= (g.ledger["day"] - 1, "") else \
        ["the scene just played is not archived, or has no summary"] if last else ["the archive is empty"]
    (todo if a else ok).append(("ARCHIVE", a, "`archive add <scene file> --choice \"...\" --write`, then `archive summary <n> \"...\" --write`"))
    ld = LO.load(g)
    lo = ["no lore has been recorded from play yet"] if not ld["entries"] else []
    (todo if lo else ok).append(("LORE", lo, "record what this scene established (a stall, a price, a habit, a headline): `lore add \"<term>\" kind=.. text=\"...\" [place=..] --write`"))
    finds, ways = AH.report(g, 3, sims=200)
    danger = [m for s, m in finds if s == "FAIL"]
    (todo if danger else ok).append(("AHEAD", danger + (["ways back: " + "; ".join(ways[:4])] if danger else []),
                                     "the next scene must put a real way out in front of the player; never change a number"))
    print(f"AFTER SCENE  D{g.ledger['day']} {g.ledger.get('time', '')}  HP {g.ledger['hp']}/{g.ledger['hp_max']}")
    for name, lines, how in todo:
        print(f"  TODO {name}: {how}")
        for line in lines[:5]:
            print(f"       - {line}")
        if len(lines) > 5:
            print(f"       - (+{len(lines) - 5} more)")
    print("  clear: " + (", ".join(n for n, _, _ in ok) or "nothing"))
    return 1 if todo else 0


def before(g, foe=None):
    """What to have in hand before writing the next scene."""
    L = g.ledger
    print(f"BEFORE SCENE  D{L['day']} {L.get('time', '')}  HP {L['hp']}/{L['hp_max']}  fatigue {L.get('fatigue', 0)}  Lv {L['level']}  XP {L.get('xp', 0)}/{100 * L['level']}")
    for line in AR.recap(AR.load(g), 2):
        print("  previously: " + line)
    inj = L.get("injuries", [])
    if inj:
        print("  injuries to show in the prose: " + "; ".join(f"{i['name']} ({i['mod']:+d})" for i in inj))
    lost = L.get("flags", {}).get("memories_lost", [])
    if lost:
        print("  he has lost: " + "; ".join(lost))
    for q in QU.load(g):
        if q["status"] == "open" and not q.get("secret"):
            print(f"  open quest: {q['title']}" + (f" (due D{q['due']['day']} {q['due']['time']})" if q.get("due") else ""))
    dq = L.get("daily", {})
    if L.get("flags", {}).get("system") and not dq.get("done_today"):
        print("  Daily Discipline: not done today")
    n = len(CL.next_clues(CL.load(g)))
    print(f"  clues ready for the next rung: {n} (`clues next --gm`); offer at most one this scene")
    wd = W.load(g)
    due = [s for _, _, s in W.pending(wd) if s["day"] <= L["day"]]
    fresh = [t for t in wd.get("traces", []) if not t.get("surfaced")]
    print(f"  world: {len(due)} faction step(s) due (`world tick`), {len(fresh)} trace(s) Mori has not met (`world status --gm`)")
    bd = BE.load(g)
    now = [b for b in bd["beats"] if b["status"] == "pending" and b["from"] is not None and b["from"] <= L["day"] <= (b["to"] or b["from"])]
    print(f"  planned beats in their window now: {len(now)} (`beats status --gm`)")
    for s, m in AH.report(g, 2, sims=200)[0]:
        if s in ("FAIL", "WARN"):
            print(f"  {s}: {m}")
    for line in LO.ambient(g, LO.load(g)):
        print("  " + line)
    if foe:
        from . import scale as S
        m = S.matchup(g, foe)
        print(f"  fight forecast vs {m['foe']['name']}: rested {m['fresh']['win']}%"
              + (f", as he is now {m['now']['win']}%" if m["now"] else "") + f" -> {m['class'].upper()}. Run it with the FIGHT REFEREE (`move start`)")
    print("  remember: options are intentions, never techniques; every roll through gm.py with --apply; System text in [brackets]")
    return 0
