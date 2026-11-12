"""Tests for the RSI mechanisms: each one checked on inputs whose answer is known."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from cipherlab.audit import audit  # noqa: E402
from cipherlab.evaluate import Ledger  # noqa: E402
from cipherlab.loop import Step, Trace  # noqa: E402
from cipherlab.methods import rsigym  # noqa: E402
from cipherlab.methods.budget_rsi import HGMTree, LinearReadout, Node  # noqa: E402
from cipherlab.methods.so_rsi import AnomalyDetector, InquiryMemory  # noqa: E402
from cipherlab.methods.swarm_rsi import MODULES, diversity, recombine  # noqa: E402
from cipherlab.probes import diagnose_rows  # noqa: E402
from cipherlab.program import Genome  # noqa: E402


def step(i, op, accepted, d=0.0, expected=0.0):
    return Step(i, op, "search", "parametric", "p", "c", 0.2, 0.2 + d, accepted, expected=expected)


class TestAnomalies(unittest.TestCase):
    def test_recurrence(self):
        t = Trace([step(1, "iters_up", False), step(2, "add_polish", False), step(3, "iters_up", False)])
        self.assertIn("recurrence", [a.kind for a in AnomalyDetector().check(t)])

    def test_opposing(self):
        t = Trace([step(1, "temp_up", True, 0.02), step(2, "temp_down", False)])
        self.assertIn("opposing", [a.kind for a in AnomalyDetector().check(t)])

    def test_mismatch(self):
        t = Trace([step(1, "iters_up", False, 0.0, expected=0.05)])
        self.assertIn("mismatch", [a.kind for a in AnomalyDetector().check(t)])

    def test_quiet_trace(self):
        t = Trace([step(1, "add_words", True, 0.1, expected=0.05)])
        self.assertEqual(AnomalyDetector().check(t), [])


class TestInquiryMemory(unittest.TestCase):
    def test_refuted_edits_are_damped_below_their_boost(self):
        m = InquiryMemory()
        m.observe(step(1, "iters_up", False))
        m.observe(step(2, "iters_up", False))
        w = m.weights({"iters_up": 0.2, "add_words": 0.2})
        self.assertLess(w["iters_up"], w["add_words"])


class TestInquiryMemoryResolution(unittest.TestCase):
    def test_supported_finding_stops_steering(self):
        """Regression: a finding whose remedy was accepted must not keep damping edits."""
        from cipherlab.methods.so_rsi import Finding
        m = InquiryMemory()
        m.findings.append(Finding(1, ["mismatch"], ["objective"], [], ["add_words"], ["restarts_up"]))
        self.assertLess(m.weights({"restarts_up": 0.2})["restarts_up"], 0.2)   # open: restarts_up is futile
        m.observe(step(2, "add_words", True, 0.3))                              # the remedy works
        self.assertEqual(m.findings[0].status, "supported")
        self.assertEqual(m.weights({"restarts_up": 0.2})["restarts_up"], 0.2)  # resolved: no longer steers


class TestAReaLCredit(unittest.TestCase):
    def test_only_rejected_edits_count_against_a_skill(self):
        """Regression: edits accepted inside a losing campaign must not be retired."""
        from cipherlab.methods.areal import Leader
        leader = Leader(np.random.default_rng(0))
        for _ in range(3):
            leader.review("search", 0.0, [("use_anneal", True), ("iters_down", False)])
        self.assertIn("use_anneal", leader.skills["search"])
        self.assertNotIn("iters_down", leader.skills["search"])


class TestProbes(unittest.TestCase):
    def rows(self, found_minus_true, last_frac, hit_cap=False, n=10):
        return [{"uid": f"u-{i:03d}", "bucket": "long", "solved": False, "fitness_found": 0.0 + found_minus_true,
                 "fitness_true": 0.0, "evals": 1000, "last_improvement": int(1000 * last_frac), "hit_cap": hit_cap}
                for i in range(n)]

    def test_objective_gap_is_diagnosed(self):
        d = diagnose_rows(Genome(), self.rows(+5.0, 0.3))
        self.assertIn("objective", d.mechanisms)
        self.assertIn("ngram_up", d.recommended())
        self.assertIn("iters_up", d.futile())

    def test_undersearched_vs_cap_bound(self):
        self.assertIn("undersearched", diagnose_rows(Genome(), self.rows(-5.0, 0.95)).mechanisms)
        self.assertIn("cap_bound", diagnose_rows(Genome(), self.rows(-5.0, 0.95, hit_cap=True)).mechanisms)


class TestReadout(unittest.TestCase):
    def test_recovers_a_linear_rule(self):
        rng = np.random.default_rng(0)
        X = rng.normal(size=(200, 4))
        y = 0.5 + 2 * X[:, 1] - X[:, 3]
        m = LinearReadout(ridge=1e-6).fit(X, y)
        np.testing.assert_allclose(m.predict(X), y, atol=1e-3)

    def test_constant_feature_is_harmless(self):
        X = np.c_[np.ones(20), np.arange(20.0)]
        m = LinearReadout().fit(X, np.arange(20.0))
        self.assertTrue(np.all(np.isfinite(m.predict(X))))


class TestHGM(unittest.TestCase):
    def test_productive_clade_is_preferred(self):
        t = HGMTree()
        t.add(Node(Genome(), None, 5, 48, 0.2))
        t.add(Node(Genome(ngram=3), 0, 40, 48, 0.8))
        t.add(Node(Genome(ngram=1), 0, 1, 48, 0.1))
        picks = [t.select_parent(np.random.default_rng(s)) for s in range(50)]
        self.assertGreater(picks.count(1), 40)


class TestSwarm(unittest.TestCase):
    def test_recombine_takes_one_module(self):
        a = Genome(ngram=4, word_weight=2.0)
        b = Genome(search="anneal", temp0=8.0, iters=4000)
        c = recombine(a, b, "search")
        self.assertEqual((c.ngram, c.word_weight, c.search, c.temp0), (4, 2.0, "anneal", 8.0))
        self.assertEqual(set(MODULES), {"objective", "search", "start"})

    def test_diversity_bounds(self):
        class A:
            def __init__(self, g):
                self.genome = g
        self.assertEqual(diversity([A(Genome()), A(Genome())]), 0.0)
        self.assertGreater(diversity([A(Genome()), A(Genome(ngram=4, search="anneal"))]), 0.0)


class TestRSIIndex(unittest.TestCase):
    def test_course_example(self):
        init, fin = {"a": 0.5, "b": 0.2}, {"a": 0.75, "b": 0.6}
        self.assertAlmostEqual(rsigym.rsi_index(init, fin), 0.5)
        self.assertAlmostEqual(rsigym.rsi_index_as_printed(init, fin), -0.5)


class TestAudit(unittest.TestCase):
    def test_flags_early_heldout_and_budget_mismatch(self):
        led = Ledger()
        led.accesses.append({"split": "heldout", "runs": 1, "caller": "peek", "t": 1.0})
        arms = {"a": [{"runs_spent": 100, "steering": 0.1, "heldout": 0.1}] * 3,
                "b": [{"runs_spent": 200, "steering": 0.1, "heldout": 0.1}] * 3}
        res = {name: ok for name, ok, _ in audit(led, arms, final_report_time=2.0)}
        self.assertFalse(res["sealed held-out"])
        self.assertFalse(res["matched budgets"])
        self.assertTrue(res["enough seeds"])


if __name__ == "__main__":
    unittest.main()
