import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SKILLS = Path(__file__).resolve().parent.parent / "scripts" / "skills.py"


def load_skills():
    spec = importlib.util.spec_from_file_location("harness_skills", SKILLS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestSkills(unittest.TestCase):
    def test_cap_text_no_truncate(self):
        sk = load_skills()
        self.assertEqual(sk.cap_text("abc", 10), "abc")

    def test_cap_text_truncate_keeps_tail(self):
        sk = load_skills()
        out = sk.cap_text("x" * 5 + "HELLO", 6)
        self.assertEqual(len(out), 6)
        self.assertTrue(out.startswith("…"))
        self.assertTrue(out.endswith("HELLO"))

    def test_load_missing_skipped_and_overcap_flagged(self):
        sk = load_skills()
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "s1").mkdir()
            (d / "s1" / "SKILL.md").write_text("A" * 100, encoding="utf-8")
            texts, truncated = sk.load_skill_texts(["s1", "missing"], d, 10)
            self.assertIn("s1", texts)
            self.assertNotIn("missing", texts)
            self.assertTrue(truncated.get("s1"))

    def test_tdd_evidence_hit(self):
        sk = load_skills()
        card = {"acceptance_tests": ["tests/t.txt"]}
        ok, _ = sk.check_skill_evidence(
            "test-driven-development", ["src/a.py", "tests/t.txt"], card)
        self.assertTrue(ok)

    def test_tdd_evidence_miss(self):
        sk = load_skills()
        card = {"acceptance_tests": ["tests/t.txt"]}
        ok, _ = sk.check_skill_evidence(
            "test-driven-development", ["src/a.py"], card)
        self.assertFalse(ok)

    def test_unknown_skill_is_instruction_only(self):
        sk = load_skills()
        ok, detail = sk.check_skill_evidence(
            "systematic-debugging", ["src/a.py"], {})
        self.assertTrue(ok)
        self.assertIn("instruction-only", detail)


if __name__ == "__main__":
    unittest.main()
