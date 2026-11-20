import json
import os
import random
import shutil
import tempfile
import unittest

from novelbot import ahead as AH, archive as AR, beats as BE, book as B, quests as QU, tech as TE, clues as CL, people as PE, rulings as RU, scale as S, scene as SC, sync as SY, world as W
from novelbot.game import Game, Plan

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.dir = os.path.join(self.tmp, "g")
        shutil.copytree(SRC, self.dir)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def game(self):
        return Game(self.dir)

    def put(self, name, obj):
        with open(os.path.join(self.dir, name), "w") as f:
            json.dump(obj, f)

    def get(self, name):
        with open(os.path.join(self.dir, name)) as f:
            return json.load(f) if name.endswith(".json") else f.read()

    def run_plan(self, fn, write=True):
        g = self.game()
        plan = Plan(g)
        fn(g, plan)
        return g, plan, plan.finish(write)


class BookTests(Base):
    DELTA = {"time": "10:30", "where": "ward", "with": ["Hana"], "now": "resting", "pending": "sleep or leave",
             "hp": "-30", "won": "-2000", "items_add": ["business card"], "items_remove": ["license"],
             "injuries_add": [{"name": "cracked ribs", "mod": -1}],
             "events_add": [{"day": 3, "time": "09:00", "text": "Check-up"}], "events_done": ["Rent"],
             "facts": {"temple": {"text": "what happened", "pattern": "arhat"}},
             "people": {"Hana": {"trust": "+2", "told": {"temple": "a statue fell"}}},
             "threads_add": ["the crow"], "log": "Rested."}

    def test_dry_run_changes_nothing(self):
        before = self.get("ledger.json")
        self.assertEqual(B.apply(self.game(), dict(self.DELTA)), 0)
        self.assertEqual(self.get("ledger.json"), before)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "scene_state.json")))

    def test_apply_updates_everything_together(self):
        g = self.game()
        PE.init(g)
        self.put("people.json", PE.init(g)[0])
        self.assertEqual(B.apply(self.game(), dict(self.DELTA), write=True), 0)
        L = self.get("ledger.json")
        self.assertEqual((L["hp"], L["time"], L["won"]), (70, "10:30", 200000))
        self.assertEqual(L["injuries"], [{"name": "cracked ribs", "mod": -1}])
        self.assertEqual(L["items"], ["business card"])
        ev = self.get("events.json")
        self.assertTrue(next(e for e in ev if "Rent" in e["text"])["done"])
        self.assertEqual(ev[0]["text"], "Check-up")
        hana = self.get("people.json")["people"]["Jin Hana"]
        self.assertEqual((hana["trust"], hana["told"]["temple"], hana["last_seen"]), (2, "a statue fell", "D1 10:30"))
        state = self.get("STATE_NOW.md")
        for want in ("D1 Fri 15 Mar 2047 10:30 | ward | with: Hana", "HP 70/100", "cracked ribs (-1)", "NOW: resting",
                     "PENDING PLAYER CHOICE: sleep or leave", "OPEN THREAD: the crow", "DUE D3 09:00: Check-up",
                     "HERE Jin Hana: trust +2; told (temple): a statue fell"):
            self.assertIn(want, state)
        self.assertIn("- D1 10:30: Rested.", self.get("LOG.md"))
        self.assertTrue(os.listdir(os.path.join(self.dir, ".novelbot_bak")))
        g = self.game()
        self.assertEqual([f for f in SY.audit(g) if f[0] == "FAIL"], [])
        self.assertIn(("cracked ribs", -1), g.gm.mods(g.ledger))      # the engine now penalises rolls for it

    def test_bad_delta_writes_nothing(self):
        before = self.get("ledger.json")
        bad = {"day": 5, "time": "08:00", "hp": "-10", "items_remove": ["sword"], "won": "-999999999",
               "injuries_add": [{"name": "x"}], "events_done": ["nothing like this"], "bogus": 1,
               "people": {"Hana": {"learn": ["no-such-fact"]}}}
        self.assertEqual(B.apply(self.game(), bad, write=True), 1)
        self.assertEqual(self.get("ledger.json"), before)

    def test_zero_hp_and_bounds(self):
        B.apply(self.game(), {"hp": "-500", "where": "x"}, write=True)
        self.assertEqual(self.get("ledger.json")["hp"], 0)
        self.assertIn("DOWN", self.get("STATE_NOW.md"))
        B.apply(self.game(), {"hp": "=250"}, write=True)
        self.assertEqual(self.get("ledger.json")["hp"], 100)

    def test_fix_repairs_only_the_certain_things(self):
        L = self.get("ledger.json")
        L["day"], L["hp_max"] = 3, 999
        L["flags"]["rent_due"] = "D5"
        self.put("ledger.json", L)
        hand = self.get("STATE_NOW.md")
        self.assertEqual(B.fix(self.game(), write=True), 0)
        L = self.get("ledger.json")
        self.assertEqual((L["flags"]["date"], L["flags"]["rent_due"], L["hp_max"]), ("2047-03-17", "D7", 100))
        self.assertEqual(self.get("STATE_NOW.md"), hand)             # hand-written state is not overwritten

    def test_save_and_load_carry_the_extra_files(self):
        os.makedirs(os.path.join(self.tmp, "saves"))
        self.put("people.json", {"people": {"A": PE.new_person("A", trust=1)}, "facts": {}})
        self.assertEqual(B.save_slot(self.game(), "save", "t"), 0)
        self.put("people.json", {"people": {"A": PE.new_person("A", trust=9)}, "facts": {}})
        self.put("clues.json", {"rung": 7, "ladder": [], "pool": []})
        self.assertEqual(B.save_slot(self.game(), "load", "t"), 0)
        self.assertEqual(self.get("people.json")["people"]["A"]["trust"], 1)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "clues.json")))
        auto = os.path.join(self.tmp, "saves", "sl__autosave_before_load")
        self.assertTrue(os.path.exists(os.path.join(auto, "clues.json")))


class PeopleTests(Base):
    def test_init_from_bible(self):
        data, added = PE.init(self.game())
        self.assertEqual(added, ["Jin Hana", "Jin Taejin", "Kang Daeil", "Inspector Ha Sion"])
        self.assertEqual(data["people"]["Jin Taejin"]["status"], "dead")
        self.assertEqual(data["people"]["Jin Hana"]["group"], "Family")
        self.assertEqual(PE.find(data, "ha sion"), "Inspector Ha Sion")
        self.assertEqual(PE.find(data, "Daeil"), "Kang Daeil")
        self.assertIsNone(PE.find(data, "Jin"))                       # two Jins: ambiguous

    def test_scan_counts_each_log_line_once(self):
        with open(os.path.join(self.dir, "LOG.md"), "a") as f:
            f.write("- D1 09:10: Shared food. Daeil respect +2, crew fed.\n")
        g = self.game()
        data = PE.init(g)[0]
        found = PE.scan(g, data)
        self.assertEqual([(n, d) for _, n, d, _ in found], [("Daeil", 2)])
        data["counted"] = [found[0][0]]
        self.assertEqual(PE.scan(g, data), [])

    def test_scene_flags_people_out_of_the_know(self):
        data = PE.init(self.game())[0]
        data["facts"]["temple"] = {"text": "t", "pattern": "arhat"}
        data["people"]["Kang Daeil"]["knows"] = ["temple"]
        data["people"]["Inspector Ha Sion"]["told"] = {"temple": "a statue fell"}
        self.put("people.json", data)
        scene = "Daeil nods.\n\"The arhats moved,\" Ha Sion says.\nTaejin's photo hangs on the wall.\n"
        text = " | ".join(m for _, m in SC.check(self.game(), scene))
        self.assertIn("fact 'temple' surfaces. In the scene but not in the know: Jin Taejin, Inspector Ha Sion", text)
        self.assertIn("cover story: Inspector Ha Sion", text)
        self.assertIn("Jin Taejin is recorded as dead", text)
        self.assertNotIn("not in the know: Kang Daeil", text)


class ClueTests(Base):
    def setUp(self):
        super().setUp()
        data = CL.init(self.game())
        data["ladder"][2]["clues"] = [data["pool"].pop(0), data["pool"].pop(0)]
        data["ladder"][2]["patterns"] = ["third hidden"]
        self.put("clues.json", data)

    def test_init_reads_ladder_and_pool(self):
        data = self.get("clues.json")
        self.assertEqual((len(data["ladder"]), len(data["pool"]), data["rung"]), (3, 1, 2))
        self.assertEqual(data["ladder"][0]["truth"], "First hidden truth.")

    def test_status_hides_secret_text_without_gm(self):
        data = self.get("clues.json")
        plain = "\n".join(CL.status(data)[0] + CL.next_clues(data))
        self.assertNotIn("hidden truth", plain)
        self.assertNotIn("crow", plain)
        self.assertIn("hidden truth", "\n".join(CL.status(data, gm=True)[0]))

    def test_no_reveal_without_clues_and_no_skipping(self):
        _, plan, code = self.run_plan(lambda g, p: CL.reveal(CL.load(g), 3, p))
        self.assertEqual(code, 1)
        self.assertIn("only 0 of its clues", plan.errors[0])
        data = self.get("clues.json")
        data["rung"] = 1
        self.put("clues.json", data)
        _, plan, _ = self.run_plan(lambda g, p: CL.reveal(CL.load(g), 3, p))
        self.assertIn("skips from rung 1 to 3", plan.errors[0])

    def test_place_then_reveal(self):
        def go(g, plan):
            data = CL.load(g)
            CL.place(data, "c1", g.stamp(), plan)
            CL.place(data, "c2", g.stamp(), plan)
            CL.reveal(data, 3, plan)
            plan.put_json("clues.json", data)
        _, _, code = self.run_plan(go)
        self.assertEqual(code, 0)
        self.assertEqual(self.get("clues.json")["rung"], 3)
        self.assertIn("Reveal ladder: rung 3", self.get("LOG.md"))

    def test_scene_check_uses_the_ladder(self):
        text = " | ".join(m for _, m in SC.check(self.game(), "He learns the third hidden thing.\n"))
        self.assertIn("secret leak: a rung-3 truth", text)
        data = self.get("clues.json")
        data["rung"] = 3
        self.put("clues.json", data)
        text = " | ".join(m for _, m in SC.check(self.game(), "He learns the third hidden thing.\n"))
        self.assertNotIn("secret leak", text)


class WorldTests(Base):
    STEPS = [{"id": "a", "day": 1, "text": "files a report", "trace": "a clerk asks for signatures",
              "then": [{"after": 2, "text": "docks pay", "stops_if": "Mori confronts the boss"}]},
             {"id": "b", "day": 1, "text": "long shot", "chance": 10, "else_delay": 3},
             {"id": "c", "day": 9, "text": "later"}]

    def setUp(self):
        super().setUp()
        data, added = W.init(self.game())
        self.assertEqual(added, ["Harbour Union", "The Bureau"])
        self.assertEqual(data["factions"]["harbour_union"]["goal"], "The port")
        data["factions"]["harbour_union"]["steps"] = json.loads(json.dumps(self.STEPS))
        self.put("factions.json", data)

    def tick(self, rule=None, seed=1):
        def go(g, plan):
            data = W.load(g)
            W.tick(g, data, plan, rule, random.Random(seed))
            plan.put_json("factions.json", data)
        return self.run_plan(go)

    def test_tick_runs_due_steps_and_schedules_follow_ups(self):
        _, plan, _ = self.tick(seed=3)
        steps = {s["id"]: s for s in self.get("factions.json")["factions"]["harbour_union"]["steps"]}
        self.assertEqual(steps["a"]["result"], "happened")
        self.assertEqual((steps["a.1"]["day"], steps["a.1"]["stops_if"]), (3, "Mori confronts the boss"))
        self.assertEqual((steps["b"]["day"], steps["b"]["misses"]), (4, 1))          # failed its 10% roll: delayed
        self.assertNotIn("done", steps["c"])
        self.assertEqual(self.get("factions.json")["traces"][0]["trace"], "a clerk asks for signatures")
        self.assertIn("[W] Harbour Union: files a report", self.get("LOG.md"))

    def test_steps_mori_could_stop_wait_for_a_ruling(self):
        self.tick(seed=3)
        L = self.get("ledger.json")
        L["day"] = 3
        self.put("ledger.json", L)
        _, plan, _ = self.tick()
        self.assertTrue(any(n.startswith("HOLD a.1") for n in plan.notes))
        self.tick(rule={"a.1": "stopped"})
        step = next(s for s in self.get("factions.json")["factions"]["harbour_union"]["steps"] if s["id"] == "a.1")
        self.assertEqual(step["result"], "stopped by Mori")

    def test_status_flags_idle_and_overdue_and_hides_text(self):
        L = self.get("ledger.json")
        L["day"] = 2
        self.put("ledger.json", L)
        g = self.game()
        rows, finds = W.status(g, W.load(g))
        text = " | ".join(m for _, m in finds)
        self.assertIn("The Bureau has nothing planned", text)
        self.assertIn("Harbour Union had a step due D1 that never ran", text)
        self.assertNotIn("files a report", "\n".join(rows))
        self.assertIn("files a report", "\n".join(W.status(g, W.load(g), gm=True)[0]))


class RulingTests(Base):
    def setUp(self):
        super().setUp()
        with open(os.path.join(self.dir, "LOG.md"), "a") as f:
            f.write("- D1 09:05: Rules added: adaptation (+1 per lost exchange vs same foe, max +3, needs a spotted tell).\n"
                    "- D1 09:06: Correction (user): the teacher never says 'lie with your shoulders'.\n")
        L = self.get("ledger.json")
        L["items"].append("Horn-ring (brass. Once per day: reroll a natural 1)")
        L["skills"]["Renewal Taekwondo"] = "4 (Three-Stage Hoechook, Lowest Hoechook unlocked; Ground Drawer used early)"
        self.put("ledger.json", L)

    def scan(self):
        def go(g, plan):
            data = RU.load(g)
            RU.scan(g, data, plan)
            plan.put_json("rulings.json", data)
        self.run_plan(go)
        return self.get("rulings.json")

    def test_scan_structures_what_it_can(self):
        data = self.scan()
        kinds = {r["id"]: r["kind"] for r in data["rulings"]}
        self.assertEqual(kinds["adaptation"], "bonus")
        self.assertEqual(kinds["horn_ring"], "limited")
        self.assertEqual(sorted(kinds.values()).count("lesson"), 1)
        self.assertEqual(next(r for r in data["rulings"] if r["id"] == "adaptation")["max"], 3)
        self.assertEqual(len(self.scan()["rulings"]), len(data["rulings"]))      # a second scan adds nothing

    def test_bonus_grows_per_foe_and_caps(self):
        self.scan()
        g = self.game()
        data, plan = RU.load(g), Plan(g)
        for _ in range(5):
            RU.bump(g, data, "adaptation", "dokkaebi", plan)
        self.assertEqual(RU.mods(g, data, "dokkaebi")[0], 3)
        self.assertEqual(RU.mods(g, data, "union_thug")[0], 0)
        RU.bump(g, data, "adaptation", "dokkaebi", plan, reset=True)
        self.assertEqual(RU.mods(g, data, "dokkaebi")[0], 0)

    def test_limited_use_refuses_a_second_time_until_the_next_day(self):
        self.scan()
        g = self.game()
        data, plan = RU.load(g), Plan(g)
        RU.use(g, data, "horn_ring", plan)
        RU.use(g, data, "horn_ring", plan)
        self.assertEqual(len(plan.errors), 1)
        g.ledger["day"] += 1
        plan2 = Plan(g)
        RU.use(g, data, "horn_ring", plan2)
        self.assertEqual(plan2.errors, [])

    def test_lesson_with_pattern_is_enforced_in_scenes(self):
        data = self.scan()
        lesson = next(r for r in data["rulings"] if r["kind"] == "lesson")
        lesson["pattern"] = "lie with your shoulders"
        self.put("rulings.json", data)
        text = " | ".join(m for _, m in SC.check(self.game(), "\"Lie with your shoulders,\" Grandpa says.\n"))
        self.assertIn("breaks ruling", text)

    def test_audit_finds_inert_skills_and_unapplied_rolls(self):
        with open(os.path.join(self.dir, "LOG.md"), "a") as f:
            for i in range(12):
                f.write(f"- D1 09:1{i % 10}: roll {'dodge' if i % 4 else 'hit'} dokkaebi d{i + 3} need 12 (45%) dc11\n")
        g = self.game()
        text = " | ".join(m for _, m in RU.audit(g, RU.load(g)))
        self.assertIn("2 ruling(s) or correction(s) in the log are not in rulings.json", text)
        self.assertIn("'Three-Stage Hoechook' is on the sheet", text)
        self.assertIn("'Lowest Hoechook' is on the sheet", text)
        self.assertNotIn("Ground Drawer", text)
        self.assertNotIn("'Renewal Taekwondo'", text)                 # it has training effects
        self.assertIn("not being run with `--apply`", text)
        self.assertIn("defensive rolls", text)
        d = RU.dice(g)
        self.assertEqual((d["n"], d["attack"]), (14, 4))

    def test_import_lessons(self):
        g = self.game()
        data, plan = RU.load(g), Plan(g)
        RU.import_lessons(data, "# L\n1. Never choose for the player.\n2. Stats are heavy.\n", "old/LESSONS.md", plan)
        RU.import_lessons(data, "1. Never choose for the player.\n", "old/LESSONS.md", plan)
        self.assertEqual([r["reviewed"] for r in data["rulings"]], [False, False])

    def test_extra_defences_make_fights_harder(self):
        g = self.game()
        one = S.matchup(g, "dokkaebi_ringleader", sims=400)["fresh"]["win"]
        two = S.matchup(g, "dokkaebi_ringleader", sims=400, defences=2)["fresh"]["win"]
        self.assertLess(two, one)


class ArchiveTests(Base):
    S1 = "The ward is dark.\n\n[You have returned.]\n\n🎲 **Read:** d20 **15** = **17** vs DC 11 → **STRONG**\n\n1. Hide\n2. Sleep\n3. Something else\n"
    S2 = "Morning comes grey.\n\n1. Wake her\n2. Let her sleep\n"

    def add(self, text, **kw):
        def go(g, plan):
            data = AR.load(g)
            AR.add(g, data, text, plan, **kw)
            plan.put_json(AR.INDEX, data)
        return self.run_plan(go)

    def test_scenes_are_kept_verbatim_in_order(self):
        self.add(self.S1, title="The Ward", chapter="Chapter 1")
        self.add(self.S2, choice="Hide")
        self.add(self.S1)                                              # duplicate: ignored
        data = self.get("archive/index.json")
        self.assertEqual([(s["n"], s["chapter"], s["choice"]) for s in data["scenes"]], [(1, "Chapter 1", "Hide"), (2, "Chapter 1", None)])
        self.assertEqual(self.get("archive/scenes/0001_D1.md"), self.S1)
        self.assertEqual(data["scenes"][0]["date"], "2047-03-15")

    def test_book_reads_like_a_novel(self):
        self.add(self.S1, title="The Ward", chapter="Chapter 1")
        self.add(self.S2, choice="Hide", day=2)
        g = self.game()
        md, words = AR.build(g, AR.load(g))
        self.assertIn("## Chapter 1", md)
        self.assertIn("## Day 2", md)                                  # a new day opens a new chapter unless named
        self.assertIn("[You have returned.]", md)
        self.assertIn("> **You chose:** Hide", md)
        self.assertNotIn("🎲", md)
        self.assertNotIn("1. Hide", md)
        self.assertIn("🎲", AR.build(g, AR.load(g), novel=False)[0])
        page = AR.to_html("T", md)
        self.assertIn('<p class="sys">[You have returned.]</p>', page)
        self.assertIn('<p class="choice"><b>You chose:</b> Hide</p>', page)

    def test_loading_a_save_sets_later_scenes_aside(self):
        os.makedirs(os.path.join(self.tmp, "saves"))
        self.add(self.S1)
        B.save_slot(self.game(), "save", "t")
        self.add(self.S2)
        B.save_slot(self.game(), "load", "t")
        g = self.game()
        data = AR.load(g)
        self.assertEqual(len(AR.live(data)), 1)
        self.assertTrue(os.path.exists(os.path.join(self.dir, "archive/scenes/0002_D1.md")))
        self.assertNotIn("Morning", AR.build(g, data)[0])


class TechTests(Base):
    def setUp(self):
        super().setUp()
        L = self.get("ledger.json")
        L["skills"]["Erase the Rhythm"] = "1"
        self.put("ledger.json", L)
        self.put("techniques.json", TE.PROPOSED)
        self.put("rulings.json", {"rulings": [{"id": "adaptation", "kind": "bonus", "per": "foe", "step": 1, "max": 3,
                                                "text": "adaptation", "source": "t"}], "uses": {}, "seen": []})

    def start(self, foe="dokkaebi_ringleader"):
        self.put("fight.json", {"foe": foe, "shown": [], "read": False, "opening": False, "lost": 0, "exchanges": 0})

    def result(self, intent, tier, tid=None):
        def go(g, plan):
            state, _ = TE.record(g, TE.load(g), intent, tier, tid, plan)
            if state:
                plan.put_json("fight.json", state)
        return self.run_plan(go)

    def test_owned_follows_the_sheet(self):
        g = self.game()
        self.assertEqual(set(TE.owned(g.ledger, TE.load(g))), set(TE.PROPOSED) - {"ground_drawer", "dragon_catcher", "true_hoechook"})
        g.ledger["skills"] = {"Renewal Taekwondo": "2"}
        self.assertEqual(set(TE.owned(g.ledger, TE.load(g))), {"x_guard"})

    def test_mori_picks_and_the_pick_changes_with_the_fight(self):
        self.start()
        g = self.game()
        fid, state, mod, shift, opts = TE.recommend(g, TE.load(g), "attack")
        first = opts[0]["id"]
        self.assertEqual(opts[0]["value"], max(o["value"] for o in opts))
        self.assertNotIn("counter_hoechook", [o["id"] for o in opts])            # he has not read the foe yet
        line = TE.gm_line("hit", fid, opts[0], mod, shift)
        self.assertIn("python3 gm.py roll hit foe=dokkaebi_ringleader", line)
        self.assertIn("--apply", line)
        self.result("attack", "CLEAN", "lowest_hoechook")
        state = self.get("fight.json")
        self.assertEqual((state["shown"], state["opening"]), (["lowest_hoechook"], True))
        g = self.game()
        _, _, _, shift, opts = TE.recommend(g, TE.load(g), "attack")
        self.assertEqual(shift, -3)
        self.assertNotIn("lowest_hoechook", [o["id"] for o in opts])             # the foe has seen it now
        self.result("read", "STRONG")
        g = self.game()
        self.assertIn("counter_hoechook", [o["id"] for o in TE.recommend(g, TE.load(g), "attack")[4]])
        self.assertIsNotNone(first)

    def test_losing_an_exchange_grows_adaptation_only_after_a_read(self):
        self.start()
        self.result("defend", "FAIL")
        self.assertEqual(self.get("rulings.json")["uses"], {})
        self.result("read", "CLEAN")
        self.result("defend", "FAIL")
        self.assertEqual(self.get("rulings.json")["uses"], {"adaptation:dokkaebi_ringleader": 1})
        g = self.game()
        self.assertEqual(TE.recommend(g, TE.load(g), "defend")[2], 1)
        self.assertFalse(self.get("fight.json")["opening"])

    def test_install_makes_gm_py_accept_the_technique(self):
        def go(g, plan):
            TE.install(g, TE.load(g), plan)
        self.run_plan(go)
        g = self.game()
        ids = [e["id"] for e in g.ledger["effects"]]
        self.assertIn("t_three_stage_hoechook", ids)
        plain = g.gm.compute(g.ledger, g.foes, "hit", "dokkaebi")
        big = g.gm.compute(g.ledger, g.foes, "hit", "dokkaebi", use=("t_three_stage_hoechook",))
        self.assertAlmostEqual(big["kp"], plain["kp"] * 1.5)                      # only when called; passive rolls unchanged
        self.assertEqual(big["dc"], plain["dc"] + 2)

    def test_techniques_grow_with_mastery_and_use(self):
        g = self.game()
        t = TE.load(g)["three_stage_hoechook"]
        self.assertEqual(TE.scaled(g.ledger, t), ({"kp_mult": 1.5, "dc_shift": 2}, {"fatigue": 3}))
        g.ledger["skills"]["Renewal Taekwondo"] = "8"
        e, c = TE.scaled(g.ledger, t)
        self.assertEqual((e["kp_mult"], e.get("dc_shift"), e["tech"], c), (1.7, None, 2, {}))    # stronger, no longer awkward, free
        low = TE.load(g)["lowest_hoechook"]
        self.assertEqual(TE.scaled(g.ledger, low)[0]["kp_mult"], 1.0)                              # its weakness is trained out
        self.assertEqual(set(TE.owned(g.ledger, TE.load(g))), set(TE.PROPOSED))                    # mastery 8 opens every card
        true = TE.load(g)["true_hoechook"]
        self.assertEqual(TE.scaled(g.ledger, true)[1], {"fatigue": 29, "hp_pct": 8})

    def test_use_ranks_a_technique_up_and_install_follows(self):
        self.run_plan(lambda g, p: TE.install(g, TE.load(g), p))
        self.start()
        techs = self.get("techniques.json")
        techs["three_stage_hoechook"]["used"] = 7
        self.put("techniques.json", techs)
        _, plan, _ = self.result("attack", "CLEAN", "three_stage_hoechook")
        self.assertTrue(any("mastery through use. Rank 1" in n for n in plan.notes))
        g = self.game()
        self.assertTrue(TE.stale(g, TE.load(g)))
        self.run_plan(lambda g, p: TE.install(g, TE.load(g), p))
        g = self.game()
        self.assertFalse(TE.stale(g, TE.load(g)))
        eff = next(e for e in g.ledger["effects"] if e["id"] == "t_three_stage_hoechook")
        self.assertEqual((eff["kp_mult"], eff["dc_shift"]), (1.55, 1))
        self.result("attack", "FAIL", "three_stage_hoechook")
        self.assertEqual(self.get("techniques.json")["three_stage_hoechook"]["used"], 8)           # a miss teaches nothing

    def test_new_skills_are_noticed_and_stronger_stats_change_the_pick(self):
        L = self.get("ledger.json")
        L["skills"]["Limiter Needle"] = "1"
        self.put("ledger.json", L)
        with open(os.path.join(self.dir, "SKILL_TREES.md"), "a") as f:
            f.write("- M2 **Baekdu Chain** (two kicks)\n")
        g = self.game()
        miss = " | ".join(TE.missing_cards(g, TE.load(g)))
        self.assertIn("Baekdu Chain (opened at mastery 2)", miss)
        self.assertIn("Limiter Needle (a skill on the sheet)", miss)
        self.assertNotIn("True Hoechook", miss)                                                    # mastery 7: not his yet
        weak = TE.options(g, g.sheet(), TE.load(g), "hit", "stone_guard")[0]["R"]["p"]
        strong = TE.options(g, g.sheet(level=40), TE.load(g), "hit", "stone_guard")[0]["R"]["p"]
        self.assertGreater(strong, weak)

    def test_options_must_not_make_the_player_pick_the_kick(self):
        scene = "The club comes down.\n\n1. Use Lowest Hoechook\n2. Back off\n3. Something else\n"
        text = " | ".join(m for _, m in SC.check(self.game(), scene))
        self.assertIn("an option names a technique ('Lowest Hoechook')", text)
        ok = "The club comes down.\n\n1. Go for its legs\n2. Back off\n3. Something else\n"
        self.assertNotIn("names a technique", " | ".join(m for _, m in SC.check(self.game(), ok)))


class QuestTests(Base):
    def add(self, qid, **f):
        def go(g, plan):
            data = QU.load(g)
            QU.add(g, data, qid, f, plan)
            plan.put_json("quests.json", data)
        return self.run_plan(go)

    def finish(self, qid, write=True, failed=False):
        g = self.game()
        data, plan = QU.load(g), Plan(g)
        QU.finish(g, data, qid, plan, write, failed)
        plan.put_json("quests.json", data)
        return plan, plan.finish(write)

    def test_xp_sizes_scale_with_level(self):
        L = self.game().ledger
        self.assertEqual([QU.xp_value(L, k) for k in ("small", "medium", "large", "trial")], [15, 35, 60, 100])
        L["level"] = 10
        self.assertEqual(QU.xp_value(L, "trial"), 1000)
        self.assertEqual(QU.xp_value(L, 40), 40)

    def test_completing_a_quest_pays_through_gm_py_and_can_level_up(self):
        self.add("bet", kind="hidden", title="A Wager Honoured", xp="trial", points="3", items="Horn-ring")
        plan, code = self.finish("bet")
        self.assertEqual(code, 0)
        L = self.get("ledger.json")
        self.assertEqual((L["level"], L["points"]), (2, 3))                       # 100 XP at Lv1: a non-kill level-up
        self.assertIn("Horn-ring", L["items"])
        self.assertEqual(L["stats"]["Str"], 11)
        self.assertIn("[Quest complete: A Wager Honoured.]", plan.notes)
        self.assertEqual(self.get("quests.json")[0]["status"], "done")
        plan, code = self.finish("bet")
        self.assertEqual(code, 1)                                                  # cannot be paid twice

    def test_steps_secrets_and_failure(self):
        self.add("rec", kind="main", title="The Record", steps="sign|hand in", due="D0@17:00", price="the bed is lost", xp="small")
        self.add("eye", kind="hidden", title="Watcher", secret="1", xp="small")
        plan, code = self.finish("rec", write=False)
        self.assertEqual(code, 1)
        g = self.game()
        rows = "\n".join(QU.listing(g, QU.load(g)))
        self.assertIn("The Record 0/2 due D0 17:00", rows)
        self.assertNotIn("Watcher", rows)
        self.assertIn("Watcher", "\n".join(QU.listing(g, QU.load(g), gm=True)))
        self.assertIn("was due D0", " | ".join(m for _, m in QU.findings(g, QU.load(g))))
        plan, _ = self.finish("rec", failed=True)
        self.assertIn("PRICE: the bed is lost", plan.notes[0])
        self.assertEqual(self.get("ledger.json")["xp"], 0)


class BeatTests(Base):
    def setUp(self):
        super().setUp()
        with open(os.path.join(self.dir, "ARC_01_TEST.md"), "a") as f:
            f.write("\n## Beat 0 — Morning (D0, 05:30)\n- The bulb blows.\n- Optional: the courtyard.\n"
                    "\n## Beat 1 — The climb (D3-D30, Lv1 → ~12)\n- Training.\n  - a sub point\n- A rival appears.\n")
        g = self.game()
        data = BE.load(g)
        self.assertEqual(BE.init(g, data), 4)
        self.assertEqual(BE.init(g, data), 0)
        self.put("beats.json", data)

    def test_overdue_pending_items_are_flagged_and_text_is_hidden(self):
        g = self.game()
        rows, finds = BE.status(g, BE.load(g))
        self.assertEqual([m[:6] for _, m in finds], ["a1b0.1"])                   # the optional item is not chased
        self.assertNotIn("bulb", "\n".join(rows))
        self.assertIn("bulb", "\n".join(BE.status(g, BE.load(g), gm=True)[0]))

    def test_mark_needs_a_reason_for_changes(self):
        g = self.game()
        data, plan = BE.load(g), Plan(g)
        BE.mark(data, "a1b0.1", "changed", "", g.stamp(), plan)
        self.assertEqual(len(plan.errors), 1)
        BE.mark(data, "a1b0.1", "changed", "he left before dawn", g.stamp(), plan)
        self.assertEqual(data["beats"][0]["status"], "changed")
        self.put("beats.json", data)
        self.assertEqual(BE.status(self.game(), data)[1], [])

    def test_pace(self):
        p = BE.pace(self.game(), self.get("beats.json"))
        self.assertEqual((p["day"], p["level"], p["xp"]), (30, 12, 6600))


class AheadTests(Base):
    def test_sees_the_dead_end_and_the_ways_out(self):
        L = self.get("ledger.json")
        L.update(hp=3, won=100000, time="20:00", injuries=[{"name": "broken collarbone", "mod": -2}])
        self.put("ledger.json", L)
        foes = self.get("foes.json")
        foes["fire_centipede"] = {"SPD": 16, "ATK": 28, "T": 60, "T_weak": 40, "type": "penalty", "dc": "desperate",
                                  "STEALTH": 12, "name": "Fire Centipede", "notes": "Penalty Zone"}
        self.put("foes.json", foes)
        self.put("people.json", {"people": {"Han Seorin": PE.new_person("Han Seorin", role="C-rank Healer")}, "facts": {}})
        finds, ways = AH.report(self.game(), 7, sims=60)
        text = " | ".join(f"{s} {m}" for s, m in finds)
        self.assertIn("FAIL if it is missed: the Penalty Zone", text)
        self.assertIn("4.0 hours to midnight", text)
        self.assertIn("200,000 short", text)
        self.assertIn("he beats 0 as he is right now", text)
        joined = " | ".join(ways)
        self.assertIn("finish the Daily Discipline", joined)
        self.assertIn("level up: 100 XP away", joined)
        self.assertIn("Han Seorin", joined)

    def test_quiet_when_healthy(self):
        L = self.get("ledger.json")
        L["daily"]["done_today"] = True
        self.put("ledger.json", L)
        finds, _ = AH.report(self.game(), 2, sims=60)
        self.assertEqual([f for f in finds if f[0] in ("FAIL", "WARN")], [])


if __name__ == "__main__":
    unittest.main()
