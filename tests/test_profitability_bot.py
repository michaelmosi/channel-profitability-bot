import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import profitability_bot as bot  # noqa: E402

AS_OF = date(2026, 11, 30)


def results():
    s = ROOT / "samples"
    return {r["channel"]: r for r in bot.analyse(bot.read_csv(s / "spend.sample.csv"), bot.read_csv(s / "users.sample.csv"),
                                                  bot.read_csv(s / "revenue.sample.csv"), AS_OF)}


class FormulaTests(unittest.TestCase):
    def test_value_growth_matches_the_posted_formula(self):
        # (current - avg(last two months)) / avg(last two months) x 100
        self.assertAlmostEqual(bot.value_growth(150, [100, 100]), 50.0)
        self.assertAlmostEqual(bot.value_growth(60, [100, 100]), -40.0)
        self.assertAlmostEqual(bot.value_growth(120, [80, 120]), 20.0)
        self.assertIsNone(bot.value_growth(10, [0, 0]))

    def test_cac_ltv_and_payback(self):
        self.assertEqual(bot.cac(1000, 20), 50)
        self.assertIsNone(bot.cac(1000, 0))
        self.assertEqual(bot.ltv(10, 0.5, 12), 60)
        self.assertEqual(bot.payback_months(60, 10, 0.5), 12)
        self.assertIsNone(bot.payback_months(60, 0, 1))

    def test_verdict_thresholds(self):
        self.assertTrue(bot.verdict(100, 3.0).startswith("Scale"))
        self.assertTrue(bot.verdict(100, 2.99).startswith("Optimise"))
        self.assertTrue(bot.verdict(100, 1.0).startswith("Optimise"))
        self.assertTrue(bot.verdict(100, 0.99).startswith("Unprofitable"))
        self.assertTrue(bot.verdict(0, None).startswith("Free"))
        self.assertTrue(bot.verdict(100, None).startswith("No users"))


class PipelineTests(unittest.TestCase):
    def test_planted_channels_get_the_expected_verdicts(self):
        r = results()
        self.assertTrue(r["podcast"]["verdict"].startswith("Scale"))
        self.assertTrue(r["finance_influencers"]["verdict"].startswith("Optimise"))
        self.assertTrue(r["instagram_ads"]["verdict"].startswith("Unprofitable"))
        self.assertTrue(r["referral"]["verdict"].startswith("Free"))

    def test_cac_is_spend_over_new_users(self):
        r = results()["podcast"]
        self.assertAlmostEqual(r["cac"], r["spend"] / r["new_users"], places=1)

    def test_paid_channels_are_ranked_by_ltv_to_cac(self):
        s = ROOT / "samples"
        out = bot.analyse(bot.read_csv(s / "spend.sample.csv"), bot.read_csv(s / "users.sample.csv"),
                          bot.read_csv(s / "revenue.sample.csv"), AS_OF)
        self.assertEqual([r["channel"] for r in out], ["podcast", "finance_influencers", "instagram_ads", "referral"])

    def test_margin_and_lifetime_change_ltv(self):
        s = ROOT / "samples"
        args = (bot.read_csv(s / "spend.sample.csv"), bot.read_csv(s / "users.sample.csv"), bot.read_csv(s / "revenue.sample.csv"), AS_OF)
        base = {r["channel"]: r for r in bot.analyse(*args)}
        half = {r["channel"]: r for r in bot.analyse(*args, margin=0.5)}
        self.assertAlmostEqual(half["podcast"]["ltv"], base["podcast"]["ltv"] / 2, delta=0.02)

    def test_report_and_csv_are_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, md = Path(tmp) / "c.csv", Path(tmp) / "r.md"
            s = ROOT / "samples"
            bot.main([str(s / "spend.sample.csv"), str(s / "users.sample.csv"), str(s / "revenue.sample.csv"),
                      "--as-of", "2026-11-30", "--out", str(out), "--md", str(md)])
            text = md.read_text()
            self.assertIn("# Channel profitability report", text)
            self.assertIn("Fix or pause **instagram_ads**", text)
            self.assertIn("Best paid channel: **podcast**", text)


if __name__ == "__main__":
    unittest.main()
