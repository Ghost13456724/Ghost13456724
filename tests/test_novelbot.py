import copy
import os
import unittest

from novelbot import canon as C, lint as L, review as R, scale as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def codes(findings, severity=None):
    return {c for s, c, _ in findings if severity in (None, s)}


class Base(unittest.TestCase):
    def setUp(self):
        self.scale = C.load("scale.json", DATA)
        self.canon = C.load("canon.json", DATA)
        self.rules = C.load("rules.json", DATA)


class ScaleTests(Base):
    def test_tier_names(self):
        self.assertEqual(S.tier_of(self.scale, 0), "low E-rank")
        self.assertEqual(S.tier_of(self.scale, 35), "mid B-rank")
        self.assertEqual(S.tier_of(self.scale, 119), "high Universal")
        self.assertEqual(S.tier_of(self.scale, 300), "high Beyond")
        self.assertEqual(S.tier_of(self.scale, -5), "below E-rank")

    def test_resolve_alias_and_partial(self):
        self.assertEqual(C.resolve(self.canon, "seorin"), "Han Seorin")
        self.assertEqual(C.resolve(self.canon, "Ogre"), "Gate Ogre")
        self.assertIsNone(C.resolve(self.canon, "a"))

    def test_mirror_match_is_even(self):
        m = S.matchup(self.scale, self.canon, "Dojin", "Dojin")
        self.assertEqual((m["gap"], m["band"], m["dc"]), (0, "even", 11))
        self.assertEqual(m["chance"], 0.5)

    def test_full_tier_gap_is_ten(self):
        strong = copy.deepcopy(self.canon["characters"]["Baek Dojin"])
        strong["stats"] = {k: v + 10 for k, v in strong["stats"].items()}
        self.canon["characters"]["Big Dojin"] = strong
        m = S.matchup(self.scale, self.canon, "Big Dojin", "Baek Dojin")
        self.assertEqual(m["gap"], 10)
        self.assertEqual(m["band"], "auto")  # trivial, then one step easier for the blitz

    def test_matchup_is_symmetric(self):
        ab = S.matchup(self.scale, self.canon, "Dojin", "Seorin")
        ba = S.matchup(self.scale, self.canon, "Seorin", "Dojin")
        self.assertAlmostEqual(ab["gap"], -ba["gap"])

    def test_durability_gate(self):
        m = S.matchup(self.scale, self.canon, "Seorin", "Ogre")
        self.assertTrue(m["a_blocked"])
        self.assertEqual(m["band"], "beyond")
        self.assertEqual(m["chance"], 0.05)  # technique cannot buy a win through the gate

    def test_form_and_conditions_apply(self):
        base, _ = S.effective(self.canon["characters"]["Han Seorin"])
        form, applied = S.effective(self.canon["characters"]["Han Seorin"], "second breath")
        self.assertEqual(base["dur"], 19)  # cracked rib
        self.assertEqual(form["ap"], base["ap"] + 6)
        self.assertEqual(len(applied), 2)

    def test_hax_is_a_win_condition_only_past_resistance(self):
        self.canon["characters"]["Han Seorin"]["abilities"].append("Binding Sutra")
        m = S.matchup(self.scale, self.canon, "Seorin", "Ogre")
        self.assertTrue(m["a_blocked"])  # Ogre resists seals at 50, sutra is 48
        del self.canon["characters"]["Gate Ogre"]["resist"]
        m = S.matchup(self.scale, self.canon, "Seorin", "Ogre")
        self.assertFalse(m["a_blocked"])
        self.assertEqual(m["band"], "hard")  # desperate on raw numbers, one step easier with the seal

    def test_win_chance(self):
        self.assertEqual(S.win_chance(11, 0), 0.5)
        self.assertEqual(S.win_chance(3, 10), 0.95)  # natural 1 always fails
        self.assertEqual(S.win_chance(20, -5), 0.05)  # natural 20 always succeeds

    def test_outlier_and_statement_handling(self):
        char = {"feats": [
            {"stat": "ap", "rating": 60, "desc": "one freak hit"},
            {"stat": "ap", "rating": 30}, {"stat": "ap", "rating": 28},
            {"stat": "ap", "rating": 50, "kind": "stated"}]}
        e = S.evidence(self.scale, char)["ap"]
        self.assertEqual(e["supported"], 33)  # best shown 30, statement adds at most 3
        self.assertEqual(len(e["outliers"]), 1)

    def test_audit_flags_inflation_and_bad_results(self):
        self.canon["characters"]["Han Seorin"]["stats"]["ap"] = 45
        self.canon["results"].append({"winner": "Han Seorin", "loser": "Gate Ogre", "conditions": [], "scene": "x"})
        found = codes(S.audit(self.scale, self.canon), "error")
        self.assertIn("inflated", found)
        self.assertEqual(codes(S.audit(self.scale, C.load("canon.json", DATA)), "error"), set())


class ReviewTests(Base):
    def claims(self, name):
        import json
        with open(os.path.join(ROOT, "examples", name)) as f:
            return json.load(f)

    def test_bad_scene_is_rejected(self):
        found = codes(R.check(self.scale, self.canon, self.claims("claims.json")), "error")
        self.assertEqual(found, {"knowledge-leak", "feat-above-stats", "impossible-win", "missing-item"})

    def test_fixed_scene_has_no_errors(self):
        self.assertEqual(codes(R.check(self.scale, self.canon, self.claims("claims_fixed.json")), "error"), set())

    def test_dead_teleport_time_and_secrets(self):
        self.canon["characters"]["Baek Dojin"]["status"] = "dead"
        claims = {"scene": "t", "day": 3, "location": "Seoul Guild Hall", "present": ["Dojin", "Seorin", "Stranger"],
                  "events": [{"type": "reveal", "fact": "master-is-alive"},
                             {"type": "power_up", "who": "Seorin", "stat": "ap", "delta": 12},
                             {"type": "uses_ability", "who": "Seorin", "ability": "Binding Sutra"}]}
        found = codes(R.check(self.scale, self.canon, claims))
        for code in ("time-reversal", "dead-character", "teleport", "new-character", "early-reveal",
                     "unearned-power", "free-power", "big-jump", "unknown-ability"):
            self.assertIn(code, found)

    def test_power_up_in_scene_covers_the_feat(self):
        claims = {"scene": "t", "day": 12, "location": "Cheongsong Gate", "present": ["Seorin"], "events": [
            {"type": "power_up", "who": "Seorin", "stat": "ap", "delta": 8, "earned_by": "gate core", "cost": "debt"},
            {"type": "feat", "who": "Seorin", "stat": "ap", "rating": 32}]}
        self.assertEqual(codes(R.check(self.scale, self.canon, claims), "error"), set())

    def test_commit_updates_canon(self):
        log = R.commit(self.canon, self.claims("claims_fixed.json"))
        seorin, ogre = self.canon["characters"]["Han Seorin"], self.canon["characters"]["Gate Ogre"]
        self.assertEqual(ogre["status"], "dead")
        self.assertIn("gate-keeper-weakness", seorin["knows"])
        self.assertNotIn("low-grade healing draught", seorin["items"])
        self.assertEqual(len(seorin["conditions"]), 2)
        self.assertEqual(self.canon["results"][-1]["winner"], "Han Seorin")
        self.assertEqual(self.canon["scenes"][-1], "s08")
        self.assertTrue(log)
        # The next scene cannot bring the Ogre back.
        again = R.check(self.scale, self.canon, {"scene": "s09", "present": ["Ogre"], "events": []})
        self.assertIn("dead-character", codes(again))


REALMS = [{"name": "Outer Gate", "abbr": "OG", "floor": 40, "stages": 9},
          {"name": "Inner Gate", "abbr": "IG", "floor": 50, "stages": 9},
          {"name": "Elder", "abbr": "EL", "floor": 60, "stages": 3},
          {"name": "Patriarch", "abbr": "PA", "floor": 70}]


class RealmTests(Base):
    """A ladder made of realms with stages instead of ranks."""

    def setUp(self):
        super().setUp()
        self.scale["tiers"] = REALMS
        flat = lambda v: {s: v for s in S.STATS}
        self.canon["characters"] = {
            "Junior": {"realm": "OG 7", "stats": flat(46.7)},
            "Senior": {"realm": "IG 5", "stats": flat(54.4)}}
        self.canon["results"] = []

    def test_realm_round_trip(self):
        for text, want in (("OG 7", "Outer Gate 7"), ("Inner Gate 5th", "Inner Gate 5"),
                           ("ig 1", "Inner Gate 1"), ("Patriarch", "low Patriarch"), ("Elder 3", "Elder 3")):
            self.assertEqual(S.tier_of(self.scale, S.parse_rating(self.scale, text)), want)
        self.assertEqual(S.parse_rating(self.scale, "46.7"), 46.7)
        with self.assertRaises(KeyError):
            S.parse_rating(self.scale, "Elder 9")
        with self.assertRaises(KeyError):
            S.parse_rating(self.scale, "Nonsense 2")

    def test_realm_feats_parse(self):
        claims = {"scene": "t", "present": ["Junior"],
                  "events": [{"type": "feat", "who": "Junior", "stat": "ap", "rating": "EL 1"}]}
        self.assertIn("feat-above-stats", codes(R.check(self.scale, self.canon, claims)))

    def test_unbacked_stat_above_realm_is_flagged(self):
        self.assertEqual(S.audit(self.scale, self.canon), [])
        self.canon["characters"]["Junior"]["stats"]["ap"] = 58
        self.assertIn("above-realm", codes(S.audit(self.scale, self.canon)))

    def test_ending_rule(self):
        rules = {"ending": "What do you do\\?"}
        self.assertIn("ending", codes(L.lint("He waited.\n\nThe end.", rules)))
        self.assertNotIn("ending", codes(L.lint("He waited.\n\nWhat do you do?", rules)))


class LintTests(Base):
    def test_example_scene(self):
        with open(os.path.join(ROOT, "examples", "scene.md")) as f:
            found = codes(L.lint(f.read(), self.rules))
        self.assertEqual(found, {"system-format", "free-choice"})

    def test_banned_and_options(self):
        text = "A constellation watched.\n\n" + "word " * 200 + "\n\n1. Go\n2. Stay"
        found = codes(L.lint(text, self.rules))
        self.assertTrue({"banned", "options", "repetition"} <= found)


if __name__ == "__main__":
    unittest.main()
