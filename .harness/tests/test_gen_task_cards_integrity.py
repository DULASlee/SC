"""P4-b 生成器引用完整性 — 验收测试。

生成器在「建卡」这一刻就应拦下引用类错误，而不是等到 --all 校验时才暴露。

覆盖：
  1. depends_on 引用不存在的 TASK-ID  -> 拒绝
  2. id 与 archive 中已归档的 TASK-ID 冲突 -> 拒绝
  3. 同一清单内 id 重复 -> 拒绝，且不得留下任何部分写入
  4. 回归：合法清单仍能正常生成

初始状态：红（1、2 当前照常生成；3 会留下部分写入）
目标状态：绿

契约：本文件不得修改；实现方只能改 gen-task-cards.py。
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent.parent
GEN = REPO / ".harness" / "scripts" / "gen-task-cards.py"
ARCHIVE = REPO / ".harness" / "tasks" / "archive"
EXISTING_TEST = ".harness/tests/test_card_acceptance_integrity.py"


def base_task(tid):
    return {
        "id": tid,
        "title": "integrity fixture card",
        "acceptance_tests": [EXISTING_TEST],
        "allow_write": [".harness/scripts/gen-task-cards.py"],
    }


def run_manifest(tasks):
    """返回 (exit_code, out_dir, combined_output)。"""
    tmp = Path(tempfile.mkdtemp())
    man = tmp / "m.yaml"
    out = tmp / "out"
    man.write_text(yaml.safe_dump({
        "batch": "integrity",
        "created_by": "strong-model",
        "defaults": {"done_when": ["ci: harness_tests"]},
        "tasks": tasks,
    }, allow_unicode=True), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(GEN), "--manifest", str(man), "--out-dir", str(out)],
        capture_output=True, text=True, encoding="utf-8", cwd=str(REPO))
    return r.returncode, out, (r.stdout or "") + (r.stderr or "")


def written(out):
    return sorted(p.name for p in out.glob("*.yaml")) if out.is_dir() else []


class TestDanglingDependency(unittest.TestCase):
    def test_unknown_depends_on_rejected(self):
        t = base_task("TASK-911")
        t["depends_on"] = ["TASK-999"]
        rc, out, log = run_manifest([t])
        self.assertNotEqual(rc, 0, "引用不存在的依赖必须被拒，实际 exit=%d" % rc)
        self.assertEqual(written(out), [], "被拒时不得落盘，实际=%r" % (written(out),))

    def test_existing_depends_on_accepted(self):
        """回归：引用真实存在的 active 卡应通过。"""
        active = REPO / ".harness" / "tasks" / "active"
        ids = sorted(p.stem.split("-")[0] + "-" + p.stem.split("-")[1]
                     for p in active.glob("TASK-*.yaml"))
        if not ids:
            self.skipTest("no active cards to depend on")
        t = base_task("TASK-912")
        t["depends_on"] = [ids[0]]
        rc, out, log = run_manifest([t])
        self.assertEqual(rc, 0, "引用存在的依赖应通过: %s" % log)


class TestArchivedIdCollision(unittest.TestCase):
    def test_archived_id_reuse_rejected(self):
        archived = sorted(p.stem for p in ARCHIVE.glob("TASK-*.yaml"))
        if not archived:
            self.skipTest("archive is empty")
        t = base_task(archived[0])
        rc, out, log = run_manifest([t])
        self.assertNotEqual(rc, 0, "复用已归档的 TASK-ID 必须被拒，实际 exit=%d" % rc)
        self.assertEqual(written(out), [], "被拒时不得落盘")


class TestDuplicateIdInManifest(unittest.TestCase):
    def test_duplicate_id_rejected_without_partial_write(self):
        a = base_task("TASK-913")
        b = base_task("TASK-913")
        b["title"] = "second entry with same id"
        rc, out, log = run_manifest([a, b])
        self.assertNotEqual(rc, 0, "清单内重复 ID 必须被拒，实际 exit=%d" % rc)
        self.assertEqual(written(out), [],
                         "重复 ID 必须整批拒绝、零落盘，实际=%r" % (written(out),))


class TestRegression(unittest.TestCase):
    def test_valid_manifest_still_generates(self):
        rc, out, log = run_manifest([base_task("TASK-914")])
        self.assertEqual(rc, 0, "合法清单必须仍能生成: %s" % log)
        self.assertEqual(written(out), ["TASK-914.yaml"])


def deny_covers(pattern, path):
    """判断 deny 模式是否覆盖给定路径（简化的 glob 语义）。"""
    import fnmatch
    if pattern.endswith("/**"):
        base = pattern[:-3]
        return path == base or path.startswith(base + "/")
    return fnmatch.fnmatch(path, pattern)


class TestAllowDenyOverlap(unittest.TestCase):
    """生成器不得产出 deny 吞掉 allow 的卡（deny 优先会让 allow 形同虚设）。"""

    def test_generated_card_has_no_allow_deny_overlap(self):
        t = base_task("TASK-915")
        t["allow_write"] = [".harness/scripts/gen-task-cards.py"]
        rc, out, log = run_manifest([t])
        if rc != 0:
            return  # 直接拒绝生成也算合规
        card = yaml.safe_load((out / "TASK-915.yaml").read_text(encoding="utf-8"))
        allow = card["scope"]["allow_write"]
        deny = card["scope"]["deny_write"]
        swallowed = [a for a in allow if any(deny_covers(d, a) for d in deny)]
        self.assertEqual(
            swallowed, [],
            "deny 吞掉了 allow 条目，会导致执行者无法写入: %r (deny=%r)" % (swallowed, deny))

    def test_overlap_detected_for_known_pattern(self):
        """自检：辅助函数必须真能识别 .harness/** 覆盖 .harness/scripts/x.py。"""
        self.assertTrue(deny_covers(".harness/**", ".harness/scripts/gen-task-cards.py"))
        self.assertFalse(deny_covers(".harness/tests/**", ".harness/scripts/gen-task-cards.py"))


if __name__ == "__main__":
    unittest.main()
