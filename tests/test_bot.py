import os
import shutil
import tempfile
import unittest

from novelbot import scale as S, scene as SC, sync as SY
from novelbot.game import Game

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.dir = os.path.join(self.tmp, "g")
        shutil.copytree(SRC, self.dir)
        self.g = Game(self.dir)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def msgs(self, finds, sev=None):
        return " | ".join(f[-1] for f in finds if sev in (None, f[0]))


class ScaleTests(Base):
    def test_numbers_are_gm_py_numbers(self):
        m = S.matchup(self.g, "ringleader", sims=50)
        R = self.g.gm.compute(self.g.sheet(fresh=True), self.g.foes, "hit", "dokkaebi_ringleader")
        self.assertEqual(m["kick"]["p"], R["p"])
        self.assertAlmostEqual(m["kick"]["kr"], R["kr"])

    def test_fight_order_and_unwinnable(self):
        easy = S.matchup(self.g, "dokkaebi", sims=300)
        mid = S.matchup(self.g, "dokkaebi_ringleader", sims=300)
        wall = S.matchup(self.g, "stone_guard", sims=100)
        self.assertGreater(easy["fresh"]["win"], mid["fresh"]["win"])
        self.assertEqual(wall["fresh"]["win"], 0)
        self.assertTrue(wall["cant_hurt"])
        self.assertEqual(wall["class"], "do not fight")

    def test_wounded_mori_does_worse(self):
        self.g.ledger["hp"] = 20
        m = S.matchup(self.g, "dokkaebi_ringleader", sims=300)
        self.assertLess(m["now"]["win"], m["fresh"]["win"])

    def test_levels_help(self):
        lv1 = S.matchup(self.g, "dokkaebi_ringleader", sims=300)["fresh"]["win"]
        lv8 = S.matchup(self.g, "dokkaebi_ringleader", level=8, sims=300)["fresh"]["win"]
        self.assertGreater(lv8, lv1)

    def test_simulation_is_repeatable(self):
        a = S.matchup(self.g, "union_thug", sims=200)["fresh"]
        b = S.matchup(self.g, "union_thug", sims=200)["fresh"]
        self.assertEqual(a, b)

    def test_design_hits_the_role(self):
        for role, lo, hi in (("grunt", 85, 100), ("even", 30, 70), ("elite", 5, 60), ("boss", 0, 25)):
            card, m = S.design(self.g, role)
            self.assertTrue(lo <= m["fresh"]["win"] <= hi, (role, m["fresh"]["win"], card))
            self.assertLess(card["T_weak"], card["T"])
        self.assertNotIn("_probe", self.g.foes)

    def test_design_follows_level(self):
        low, _ = S.design(self.g, "even")
        high, m = S.design(self.g, "even", level=15)
        self.assertGreater(high["T"], low["T"])
        self.assertTrue(30 <= m["fresh"]["win"] <= 70)

    def test_design_rank_scales_into_band(self):
        card, _ = S.design(self.g, "even", rank="B-rank", sims=50)
        self.assertEqual(S.rank_of(S.foe_index(card)), "B-rank")

    def test_audit_flags_bad_cards(self):
        self.g.foes["broken"] = {"name": "Broken", "SPD": 10}
        self.g.foes["soft"] = dict(self.g.foes["dokkaebi"], name="Soft", T_weak=20)
        self.g.foes["mislabelled"] = dict(self.g.foes["stone_guard"], name="Mislabelled", dc="easy", notes="")
        self.g.foes["dokkaebi_chief"] = dict(self.g.foes["dokkaebi"], name="Chief", ATK=5)
        finds, _ = S.audit(self.g, sims=60)
        text = " | ".join(f"{f[1]}: {f[2]}" for f in finds)
        self.assertIn("broken: card is missing", text)
        self.assertIn("soft: weak point", text)
        self.assertIn("mislabelled: card says 'easy'", text)
        self.assertIn("dokkaebi_chief: is a senior form", text)

    def test_ranks(self):
        self.assertEqual(S.rank_of(10), "E-rank")
        self.assertEqual(S.rank_of(11.8), "D-rank")
        self.assertEqual(S.rank_of(5000), "Sovereign")


class SyncTests(Base):
    def test_clean_fixture(self):
        self.assertEqual([f for f in SY.audit(self.g) if f[0] == "FAIL"], [])

    def test_catches_drift(self):
        L = self.g.ledger
        L.update(day=3, hp=40, hp_max=150, xp=500)
        L["flags"]["rent_due"] = "D5"
        L["stats"]["Agi"] = 4
        with open(self.g.path("STATE_NOW.md"), "a") as f:
            f.write("Cracked ribs, broken collarbone.\n")
        self.g.state = self.g.text("STATE_NOW.md")
        text = self.msgs(SY.audit(self.g))
        for want in ("STATE_NOW is stale", "STATE_NOW says HP 100", "HP/MP maximum", "enough to level up",
                     "flags.date is 2047-03-15 but D3 is 2047-03-17", "flags.rent_due says D5", "Agi below 10",
                     "mention injuries"):
            self.assertIn(want, text)

    def test_technique_follows_mastery(self):
        self.g.ledger["skills"]["Renewal Taekwondo"] = "6"
        self.assertIn("technique should be +3", self.msgs(SY.audit(self.g)))


class SceneTests(Base):
    def test_clean_scene(self):
        scene = ("D1 09:00\nYou breathe out.\n[HP 100/100]\n"
                 "🎲 **Dodge:** d20 **5** -1 (edge) +2 (technique) = **6** vs DC 11 → **FAIL**\n\n"
                 "1. Stand up\n2. Stay down\n3. Call for help\n4. Something else\n")
        finds = SC.check(self.g, scene, turn=True)
        self.assertEqual([f for f in finds if f[0] != "NOTE"], [])

    def test_catches_everything(self):
        scene = ("D4 morning\nSystem: You have leveled up.\n"
                 "[STATUS]\nName: Jin Mori   Level: 3\nHP 80/120\nStrength 14\n"
                 "🎲 **Kick:** d20 **17** +0 (edge) = **17** vs DC 14 → **CLEAN**\n"
                 "🎲 **Dodge:** d20 **5** -1 (edge) = **4** vs DC 11 → **CLEAN**\n"
                 "\"Hana,\" you say. You draw your dagger and spin into a True Hoechook, then a Ground Drawer.\n"
                 "A constellation named Kim Dokja watches.\n\n1. Run\n2. Fight\n")
        text = self.msgs(SC.check(self.g, scene))
        for want in ("HP maximum 120", "ends on HP 80", "Level 3", "Strength 14", "d20 17, DC 14) has no matching roll",
                     "result reads CLEAN but 4 vs DC 11 on a 5 is FAIL", "'True Hoechook' opens at mastery 7", "'Hana' appears",
                     "Omniscient Reader", "a blade near Mori", "System messages go in [brackets]", "numbered options; found 2",
                     "set on D4 but the ledger is still on D1"):
            self.assertIn(want, text)
        self.assertNotIn("Ground Drawer", text)   # the ledger records it as used early

    def test_secret_watch(self):
        with open(self.g.path("secrets_watch.json"), "w") as f:
            f.write('[{"pattern": "true name", "rung": 5}, {"pattern": "old bell", "rung": 2}]')
        text = self.msgs(SC.check(self.g, "He hears the old bell and almost learns his true name.\n"))
        self.assertIn("rung-5 truth", text)
        self.assertNotIn("rung-2", text)

    def test_game_folder_stays_clean(self):
        S.matchup(self.g, "dokkaebi", sims=20)
        self.assertNotIn("__pycache__", os.listdir(self.dir))


if __name__ == "__main__":
    unittest.main()
