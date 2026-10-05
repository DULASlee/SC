import io
import importlib.util
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

SKILLS = Path(__file__).resolve().parent.parent / "scripts" / "skills.py"

_VALID = "---\nname: x\n---\n# x\n\nbody\n"


def load_skills():
    spec = importlib.util.spec_from_file_location("harness_skills", SKILLS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_quiet(sk, names, d, cap=100):
    """load_skill_texts + 吞掉 stderr 诊断行（测试关心的是 texts 结果，不是诊断流）。"""
    with redirect_stderr(io.StringIO()):
        return sk.load_skill_texts(names, d, cap)


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
            (d / "s1" / "SKILL.md").write_text(_VALID, encoding="utf-8")
            texts, truncated = _load_quiet(sk, ["s1", "missing"], d, 10)
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

    def test_candidate_order_prefixed_name(self):
        # "superpowers/writing-plans" 前缀写法：必须命中 base/superpowers/writing-plans/
        sk = load_skills()
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "superpowers" / "writing-plans").mkdir(parents=True)
            (d / "superpowers" / "writing-plans" / "SKILL.md").write_text(_VALID)
            cands = sk._candidate_paths(d, "superpowers/writing-plans")
            self.assertEqual(
                cands[0], d / "superpowers" / "writing-plans" / "SKILL.md")
            texts, _ = _load_quiet(sk, ["superpowers/writing-plans"], d)
            self.assertIn("superpowers/writing-plans", texts)

    def test_candidate_order_bare_name_prefers_bare_dir_over_scene(self):
        # 裸名写法且裸目录与场景子目录同名并存：裸目录更具体，必须优先命中裸目录
        sk = load_skills()
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "writing-plans").mkdir()
            (d / "writing-plans" / "SKILL.md").write_text(
                f"---\nname: writing-plans\n---\n# BARE\n")
            (d / "superpowers" / "writing-plans").mkdir(parents=True)
            (d / "superpowers" / "writing-plans" / "SKILL.md").write_text(
                f"---\nname: writing-plans\n---\n# SCENE\n")
            texts, _ = _load_quiet(sk, ["writing-plans"], d)
            self.assertIn("# BARE", texts["writing-plans"])
            self.assertNotIn("# SCENE", texts["writing-plans"])

    def test_candidate_order_bare_name_falls_back_to_scene(self):
        # 裸名写法且裸目录不存在：回退命中场景子目录
        sk = load_skills()
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "superpowers" / "writing-plans").mkdir(parents=True)
            (d / "superpowers" / "writing-plans" / "SKILL.md").write_text(_VALID)
            texts, _ = _load_quiet(sk, ["writing-plans"], d)
            self.assertIn("name: x", texts["writing-plans"])

    def test_scene_dir_absent_no_crash(self):
        sk = load_skills()
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "solo").mkdir()
            (d / "solo" / "SKILL.md").write_text(_VALID)
            texts, _ = _load_quiet(sk, ["solo"], d)
            self.assertIn("solo", texts)

    def test_content_bad_falls_back_to_scene(self):
        # "命中了错的那个"防线：最具体候选内容异常时，降级到场景子目录的正确版本
        sk = load_skills()
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "writing-plans").mkdir()
            (d / "writing-plans" / "SKILL.md").write_text("GARBAGE NO FRONTMATTER", encoding="utf-8")
            (d / "superpowers" / "writing-plans").mkdir(parents=True)
            (d / "superpowers" / "writing-plans" / "SKILL.md").write_text(_VALID)
            texts, _ = _load_quiet(sk, ["writing-plans"], d)
            self.assertIn("name: x", texts["writing-plans"])

    def test_all_candidates_bad_gives_miss(self):
        sk = load_skills()
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "writing-plans").mkdir()
            (d / "writing-plans" / "SKILL.md").write_text("GARBAGE", encoding="utf-8")
            (d / "superpowers" / "writing-plans").mkdir(parents=True)
            (d / "superpowers" / "writing-plans" / "SKILL.md").write_text("", encoding="utf-8")
            texts, _ = _load_quiet(sk, ["writing-plans"], d)
            self.assertNotIn("writing-plans", texts)

    def test_diagnostics_never_on_stdout(self):
        # 契约：诊断行只走 stderr；stdout 永远干净（管道/CI 安全）
        sk = load_skills()
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "writing-plans").mkdir()
            (d / "writing-plans" / "SKILL.md").write_text("GARBAGE", encoding="utf-8")
            outcap, errcap = io.StringIO(), io.StringIO()
            with redirect_stderr(errcap), redirect_stdout(outcap):
                sk.load_skill_texts(["writing-plans"], d, 100)
            self.assertEqual(outcap.getvalue(), "", "diagnostics must not touch stdout")
            self.assertIn("[skills]", errcap.getvalue())


if __name__ == "__main__":
    unittest.main()
