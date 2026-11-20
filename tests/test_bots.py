import json
import os
import random
import shutil
import tempfile
import unittest

from novelbot import book as B, clues as CL, people as PE, scene as SC, sync as SY, world as W
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


if __name__ == "__main__":
    unittest.main()
