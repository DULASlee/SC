"""TASK-045: ownership 单一事实源与 claim/release 语义测试。"""
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / ".harness" / "scripts"


def load_ownership():
    spec = importlib.util.spec_from_file_location(
        "harness_ownership", SCRIPTS / "ownership.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(mod)
    return mod


class TestOwnership(unittest.TestCase):
    def test_claim_then_conflict_rejected_not_warning(self):
        o = load_ownership()
        with TemporaryDirectory() as tmp:
            rec = o.claim(Path(tmp), "T1", "manual:a", f"{tmp}/wtA")
            self.assertEqual(rec["state"], "claimed")
            with self.assertRaises(o.OwnershipConflict):
                o.claim(Path(tmp), "T1", "manual:b", f"{tmp}/wtB")
            # 原主不变
            cur = o.current(Path(tmp), "T1")
            self.assertEqual(cur["owner_session_id"], "manual:a")

    def test_same_session_claim_idempotent(self):
        o = load_ownership()
        with TemporaryDirectory() as tmp:
            r1 = o.claim(Path(tmp), "T1", "manual:a", f"{tmp}/wtA")
            r2 = o.claim(Path(tmp), "T1", "manual:a", f"{tmp}/wtA")
            self.assertEqual(r1["owner_session_id"], r2["owner_session_id"])
            self.assertEqual(r2["state"], "claimed")

    def test_release_only_by_owner(self):
        o = load_ownership()
        with TemporaryDirectory() as tmp:
            o.claim(Path(tmp), "T1", "manual:a", f"{tmp}/wtA")
            with self.assertRaises(o.OwnershipConflict):
                o.release(Path(tmp), "T1", "manual:b")
            rec = o.release(Path(tmp), "T1", "manual:a")
            self.assertEqual(rec["state"], "released")
            # 释放后他人可领（A3-3）
            r2 = o.claim(Path(tmp), "T1", "manual:b", f"{tmp}/wtB")
            self.assertEqual(r2["owner_session_id"], "manual:b")

    def test_assert_writer_matrix(self):
        o = load_ownership()
        with TemporaryDirectory() as tmp:
            ok, _ = o.assert_writer(Path(tmp), "T1", "manual:a")
            self.assertFalse(ok)  # 无主：无人可写
            o.claim(Path(tmp), "T1", "manual:a", f"{tmp}/wt")
            ok, _ = o.assert_writer(Path(tmp), "T1", "manual:a")
            self.assertTrue(ok)
            ok, msg = o.assert_writer(Path(tmp), "T1", "manual:z")
            self.assertFalse(ok)
            self.assertIn("non-owner", msg)

    def test_force_release_terminal_and_read_anyone(self):
        o = load_ownership()
        with TemporaryDirectory() as tmp:
            self.assertIsNone(o.force_release(Path(tmp), "T9", "none"))
            o.claim(Path(tmp), "T1", "dispatch:T1", f"{tmp}/wt")
            rec = o.force_release(Path(tmp), "T1", "awaiting-review")
            self.assertEqual(rec["state"], "released")
            self.assertEqual(rec["release_reason"], "awaiting-review")
            cur = o.current(Path(tmp), "T1")
            self.assertEqual(cur["state"], "released")  # 读人人可

    def test_worktree_owner_reverse_lookup(self):
        o = load_ownership()
        with TemporaryDirectory() as tmp:
            wtA = Path(tmp) / "wtA"
            wtA.mkdir()
            o.claim(Path(tmp), "T1", "manual:a", str(wtA))
            rec = o.worktree_owner(Path(tmp), wtA)
            self.assertIsNotNone(rec)
            self.assertEqual(rec["task_id"], "T1")
            self.assertIsNone(o.worktree_owner(Path(tmp), Path(tmp) / "other"))
            o.release(Path(tmp), "T1", "manual:a")
            self.assertIsNone(o.worktree_owner(Path(tmp), wtA))

    def test_claim_conflict_never_clobbers_record(self):
        o = load_ownership()
        with TemporaryDirectory() as tmp:
            o.claim(Path(tmp), "T1", "manual:a", f"{tmp}/wtA")
            f = Path(tmp) / "ownership" / "T1.json"
            before = f.read_text(encoding="utf-8")
            try:
                o.claim(Path(tmp), "T1", "manual:b", f"{tmp}/wtB")
            except o.OwnershipConflict:
                pass
            self.assertEqual(f.read_text(encoding="utf-8"), before)

    def test_state_file_shape_stable(self):
        o = load_ownership()
        with TemporaryDirectory() as tmp:
            runs = Path(tmp)
            o.claim(runs, "T1", "manual:a", str(runs / "wt"))
            data = json.loads((runs / "ownership" / "T1.json").read_text(
                encoding="utf-8"))
            for k in ("task_id", "owner_session_id", "owner_worktree",
                      "state", "claimed_at"):
                self.assertIn(k, data)


if __name__ == "__main__":
    unittest.main()
