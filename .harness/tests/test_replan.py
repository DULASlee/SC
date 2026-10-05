import importlib.util
import unittest
from pathlib import Path


def load(name):
    path = (Path(__file__).resolve().parent.parent / "scripts" / name)
    spec = importlib.util.spec_from_file_location(name.replace("-", "_").replace(".py", ""), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


replan = load("replan.py")


class TestSigOf(unittest.TestCase):
    def test_digits_normalized_stable(self):
        a = replan.sig_of("fail-exec", 1, "Traceback line 123 col 45\nerror at 99")
        b = replan.sig_of("fail-exec", 1, "Traceback line 456 col 78\nerror at 11")
        self.assertEqual(a, b)

    def test_verdict_differs_sig_differs(self):
        a = replan.sig_of("fail-exec", 1, "same tail")
        b = replan.sig_of("fail-gate", 1, "same tail")
        self.assertNotEqual(a, b)


class TestPlanRetry(unittest.TestCase):
    def test_empty_history_retry_same(self):
        d = replan.plan_retry([], 1, 4, ["m2"])
        self.assertEqual(d["action"], "retry_same")
        self.assertIsNone(d["model_override"])

    def test_two_same_escalated_first_fallback(self):
        d = replan.plan_retry(["aa", "aa"], 2, 4, ["m2", "m3"])
        self.assertEqual(d["action"], "retry_escalated")
        self.assertEqual(d["model_override"], "m2")

    def test_three_same_blocked_early(self):
        d = replan.plan_retry(["aa", "aa", "aa"], 3, 4, ["m2"])
        self.assertEqual(d["action"], "blocked_early")
        self.assertIn("同一失败签名连续3次", d["reason"])

    def test_second_escalation_uses_second_fallback(self):
        d = replan.plan_retry(["aa", "aa", "bb", "bb"], 4, 6, ["m2", "m3"])
        self.assertEqual(d["action"], "retry_escalated")
        self.assertEqual(d["model_override"], "m3")


if __name__ == "__main__":
    unittest.main()
