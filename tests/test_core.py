"""Tests for the task, the program representation, the harness and the evaluator."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from cipherlab import corpus, runtime  # noqa: E402
from cipherlab.edits import BY_NAME, OPS, random_genome  # noqa: E402
from cipherlab.evaluate import Evaluator, SealedSplitError  # noqa: E402
from cipherlab.program import BASELINE, FEATURE_NAMES, Genome, diff_features, render, signed_features  # noqa: E402
from cipherlab.tasks import load_split, make_instance  # noqa: E402


class TestCorpus(unittest.TestCase):
    def test_clean_keeps_letters_and_single_spaces(self):
        self.assertEqual(corpus.clean("Don't  STOP—now, 42!"), "dont stop now")

    def test_ngram_tables_are_distributions(self):
        for n in (1, 2, 3):
            self.assertAlmostEqual(float((10 ** corpus.ngram_logp(n)).sum()), 1.0, places=6)

    def test_word_hash_distinguishes_a_from_aa(self):
        self.assertNotEqual(corpus.word_hash("a"), corpus.word_hash("aa"))

    def test_training_book_is_not_a_test_book(self):
        self.assertNotIn(corpus.TRAIN_BOOK, (corpus.STEER_BOOK, corpus.HELDOUT_BOOK))


class TestTasks(unittest.TestCase):
    def test_split_sizes(self):
        self.assertEqual([len(load_split(s)) for s in ("fit", "steering", "probe", "heldout")], [16, 48, 24, 96])

    def test_true_key_decrypts(self):
        for inst in load_split("steering")[:5]:
            np.testing.assert_array_equal(inst.true_key[inst.cipher], inst.plain)

    def test_splits_share_no_plaintext(self):
        texts = {s: {i.plaintext for i in load_split(s)} for s in ("fit", "steering", "probe", "heldout")}
        names = list(texts)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                self.assertFalse(texts[a] & texts[b], f"{a} and {b} overlap")

    def test_instances_are_deterministic(self):
        a = make_instance("x-000", "t", "attack at dawn", np.random.default_rng(3))
        b = make_instance("x-000", "t", "attack at dawn", np.random.default_rng(3))
        self.assertEqual(a.ciphertext, b.ciphertext)

    def test_patristocrat_has_no_spaces_or_words(self):
        inst = load_split("steering", "patristocrat")[0]
        self.assertNotIn(" ", inst.ciphertext)
        self.assertEqual(len(inst.word_starts), 0)


class TestProgram(unittest.TestCase):
    def test_random_programs_compile(self):
        rng = np.random.default_rng(0)
        for _ in range(60):
            compile(render(random_genome(rng, 6)), "<t>", "exec")

    def test_word_bonus_diff_shape(self):
        f = dict(zip(FEATURE_NAMES, diff_features(render(BASELINE), render(BASELINE.with_(word_weight=2.0)))))
        self.assertEqual(f["defs_added"], 1)
        self.assertEqual(f["imports_changed"], 1)
        self.assertGreater(f["lines_added"], f["lines_deleted"])

    def test_direction_is_invisible_to_shape_but_not_to_signed_features(self):
        g = Genome(iters=2000)
        up, down = BY_NAME["iters_up"].apply(g), BY_NAME["iters_down"].apply(g)
        self.assertEqual(diff_features(render(g), render(up)), diff_features(render(g), render(down)))
        self.assertGreater(signed_features(render(g), render(up))[1], 0)
        self.assertLess(signed_features(render(g), render(down))[1], 0)


class TestRuntime(unittest.TestCase):
    def setUp(self):
        self.inst = load_split("probe")[6]

    def test_budget_cap_is_enforced(self):
        src = render(Genome(iters=40000, restarts=4))
        row = runtime.run_instance(src, self.inst, 0, cap=500)
        self.assertEqual(row["evals"], 500)
        self.assertTrue(row["hit_cap"])

    def test_broken_program_is_a_failed_instance(self):
        row = runtime.run_instance("def fitness(p, ctx): return 0\ndef solve(ctx, rng): 1/0\n", self.inst, 0)
        self.assertFalse(row["solved"])
        self.assertIn("ZeroDivisionError", row["error"])  # recorded as data, not raised into the improver
        row = runtime.run_instance("def solve(:", self.inst, 0)  # "this is not python" would parse!
        self.assertIn("SyntaxError", row["error"])

    def test_truth_fitness_is_recorded(self):
        row = runtime.run_instance(render(BASELINE), self.inst, 0)
        self.assertTrue(np.isfinite(row["fitness_true"]))


class TestEvaluator(unittest.TestCase):
    def test_heldout_is_sealed_until_unsealed(self):
        with Evaluator(workers=1) as ev:
            with self.assertRaises(SealedSplitError):
                ev.run(render(BASELINE), "heldout", (0,), subset=[0])
            ev.unseal()
            r = ev.run(render(BASELINE), "heldout", (0,), subset=[0, 1], caller="test")
            self.assertEqual(len(r.rows), 2)
            self.assertEqual(ev.ledger.runs["heldout"], 2)
            self.assertEqual(ev.ledger.accesses[-1]["caller"], "test")


class TestEdits(unittest.TestCase):
    def test_every_inverse_exists(self):
        for op in OPS:
            self.assertIn(op.inverse, BY_NAME, op.name)
            self.assertEqual(BY_NAME[op.inverse].inverse, op.name)

    def test_inverse_round_trips(self):
        g = Genome(ngram=3, word_weight=2.0, search="anneal", iters=2000, restarts=4, temp0=4.0)
        for name in ("iters_up", "restarts_up", "ngram_up", "temp_up", "words_down", "smoothing_up", "use_hill", "add_polish"):
            op = BY_NAME[name]
            child = op.apply(g)
            self.assertIsNotNone(child, name)
            self.assertEqual(BY_NAME[op.inverse].apply(child), g, name)

    def test_noop_edits_are_not_applicable(self):
        self.assertIsNone(BY_NAME["ngram_up"].apply(Genome(ngram=4)))
        self.assertIsNone(BY_NAME["temp_up"].apply(Genome(search="hill")))


if __name__ == "__main__":
    unittest.main()
