"""P4 生成器冒烟 — 验收测试（splan §Phase 4）。

覆盖：
  1. 从最小清单生成卡 -> 通过校验器
  2. 缺 acceptance_tests 的条目 -> 生成失败（非零退出），且不落盘
  3. --dry-run 不写任何文件
  4. 生成卡的 deny_write 必含 ALWAYS_DENY 全部条目

初始状态：未知（生成器已存在，本测试用于判定它是否真的达标）
目标状态：绿

本文件只验证生成器行为，不触碰现有任务卡。
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent.parent
GEN = REPO / ".harness" / "scripts" / "gen-task-cards.py"
# 已存在的验收测试文件（生成器会对 acceptance_tests 做存在性检查）
EXISTING_TEST = ".harness/tests/test_card_acceptance_integrity.py"

ALWAYS_DENY = ["src/**", "tests/**", "contracts/**", ".github/**",
               ".harness/runs/**", ".harness/worktrees/**"]


def write_manifest(path, tasks, batch="smoke"):
    data = {
        "batch": batch,
        "created_by": "strong-model",
        "defaults": {"done_when": ["ci: harness_tests"]},
        "tasks": tasks,
    }
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def good_task(tid="TASK-901"):
    return {
        "id": tid,
        "title": "smoke fixture card",
        "acceptance_tests": [EXISTING_TEST],
        "allow_write": [".harness/scripts/validate-task-card.py"],
    }


def run_gen(manifest, out_dir, extra=None):
    cmd = [sys.executable, str(GEN), "--manifest", str(manifest), "--out-dir", str(out_dir)]
    if extra:
        cmd += list(extra)
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=str(REPO))


class TestGeneratorSmoke(unittest.TestCase):
    def test_minimal_manifest_generates_valid_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            man = tmp / "m.yaml"
            out = tmp / "out"
            write_manifest(man, [good_task()])
            r = run_gen(man, out)
            self.assertEqual(r.returncode, 0, "生成应成功: %s" % (r.stdout + r.stderr))
            card_file = out / "TASK-901.yaml"
            self.assertTrue(card_file.is_file(), "卡文件应落盘")

            # 生成的卡必须能通过校验器（含存在性检查）
            sys.path.insert(0, str(REPO / ".harness" / "scripts"))
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "vgen", REPO / ".harness" / "scripts" / "validate-task-card.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            errs = mod.validate_card(card_file, mod.load_schema(), repo_root=REPO)
            self.assertEqual(errs, [], "生成的卡必须通过校验器: %r" % (errs,))

    def test_missing_acceptance_tests_fails_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            man = tmp / "m.yaml"
            out = tmp / "out"
            bad = good_task()
            del bad["acceptance_tests"]
            write_manifest(man, [bad])
            r = run_gen(man, out)
            self.assertNotEqual(r.returncode, 0, "缺 acceptance_tests 必须非零退出")
            self.assertFalse((out / "TASK-901.yaml").exists(), "失败时不得落盘")

    def test_missing_allow_write_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            man = tmp / "m.yaml"
            out = tmp / "out"
            bad = good_task()
            del bad["allow_write"]
            write_manifest(man, [bad])
            r = run_gen(man, out)
            self.assertNotEqual(r.returncode, 0, "缺 allow_write 必须非零退出")

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            man = tmp / "m.yaml"
            out = tmp / "out"
            write_manifest(man, [good_task()])
            r = run_gen(man, out, extra=["--dry-run"])
            self.assertEqual(r.returncode, 0, "dry-run 应成功: %s" % (r.stdout + r.stderr))
            written = list(out.glob("*.yaml")) if out.is_dir() else []
            self.assertEqual(written, [], "dry-run 不得写任何文件")

    def test_deny_write_includes_always_deny(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            man = tmp / "m.yaml"
            out = tmp / "out"
            write_manifest(man, [good_task()])
            r = run_gen(man, out)
            self.assertEqual(r.returncode, 0, "生成应成功: %s" % (r.stdout + r.stderr))
            card = yaml.safe_load((out / "TASK-901.yaml").read_text(encoding="utf-8"))
            deny = card["scope"]["deny_write"]
            for p in ALWAYS_DENY:
                self.assertIn(p, deny, "deny_write 必须含 %s: %r" % (p, deny))

    def test_unknown_gate_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            man = tmp / "m.yaml"
            out = tmp / "out"
            t = good_task()
            t["done_when"] = ["ci: nonexistent_gate"]
            write_manifest(man, [t])
            r = run_gen(man, out)
            self.assertNotEqual(r.returncode, 0, "非法 gate 必须被拒")


if __name__ == "__main__":
    unittest.main()
