"""P1 policy tests: default-escalate, explicit allow, explicit forbid."""
import importlib.util
import unittest
from pathlib import Path

SCRIPT = (Path(__file__).resolve().parent.parent / "scripts" / "policy.py")


def load():
    spec = importlib.util.spec_from_file_location("harness_policy", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def card_with(*paths):
    return {"scope": {"allow_write": list(paths), "deny_write": []}}


class TestPolicy(unittest.TestCase):
    def setUp(self):
        self.mod = load()
        self.pol = {"allow": [".harness/evidence/auto/**",
                              "docs/reports/**"],
                    "forbid": ["**/*.pem"]}

    def test_allow_hit(self):
        self.assertEqual(
            self.mod.action_for(".harness/evidence/auto/x.log", self.pol),
            "allow")

    def test_default_escalates(self):
        self.assertEqual(
            self.mod.action_for("src/Collector/X.cs", self.pol), "escalate")

    def test_forbid_wins(self):
        self.assertEqual(
            self.mod.action_for("keys/k.pem", self.pol), "forbid")

    def test_card_all_allowed(self):
        self.assertEqual(
            self.mod.card_action(
                card_with(".harness/evidence/auto/a.log"), self.pol),
            "allow")

    def test_card_mixed_escalates(self):
        self.assertEqual(
            self.mod.card_action(
                card_with(".harness/evidence/auto/a.log", "src/X.cs"),
                self.pol),
            "escalate")

    def test_card_forbidden(self):
        self.assertEqual(
            self.mod.card_action(card_with("keys/k.pem"), self.pol),
            "forbid")

    def test_live_policy_loads(self):
        pol = self.mod.load_policy()
        self.assertIn("allow", pol)
        self.assertIn("forbid", pol)


if __name__ == "__main__":
    unittest.main()
