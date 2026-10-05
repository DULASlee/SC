"""TASK-054 验收测试：poll 回收韧性（架构师预先写好，初始为红）。

覆盖两处已取证的缺陷（2026-09-21 TASK-011 回收现场）：
  (a) worktree 已被删除时，poll 收尾调用 reset_worktree 抛
      NotADirectoryError，整条回收链中断：记录只被兜底标 error，
      ownership 不释放（残留 claimed）。
  (b) 重派出的新 attempt 记录不携带累计 sig_history，使 plan_retry
      永远只看到 tail=1 -> retry_same（同模型重试），
      retry_escalated（换模型）与 loop 病理守卫（tail>=3）不可达。

执行者不得修改本文件（验收测试已冻结，改测试视为作弊）。
"""
import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


def load(name):
    path = (Path(__file__).resolve().parent.parent / "scripts" / name)
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestReclaimResilience(unittest.TestCase):
    # ---- (a) 已删除 / 非目录的 worktree 不得让回收链崩溃 ----

    def test_reset_worktree_tolerates_missing_dir(self):
        poll = load("poll.py")
        with TemporaryDirectory() as tmp:
            missing = Path(tmp) / "gone" / "TASK-XXX"
            poll.reset_worktree(missing)  # 不得抛异常（现状：NotADirectoryError）

    def test_reset_worktree_tolerates_non_dir_path(self):
        poll = load("poll.py")
        with TemporaryDirectory() as tmp:
            f = Path(tmp) / "not-a-dir"
            f.write_text("x", encoding="utf-8")
            poll.reset_worktree(f)  # 不得抛异常

    # ---- (b) 重派必须把累计 sig_history 种进新 attempt 记录 ----

    def test_respawn_carries_accumulated_sig_history(self):
        poll = load("poll.py")
        with TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            runs.mkdir()
            store = poll.RunsStore(runs / "RUNS.jsonl", lock_dir=runs)
            wt = Path(tmp) / "wt"
            rd = Path(tmp) / "rd"
            store.append({"task_id": "TASK-900", "attempt": 1, "pid": 1,
                          "worktree": str(wt), "branch": "b",
                          "run_dir": str(rd), "model": "m"})
            prev = "deadbeef0001"
            store.update("TASK-900", 1, sig_history=[prev], status="running")
            rec = store.get("TASK-900", 1)

            def fake_spawn(task_id, card, cfg, st, note, *a, **k):
                n = st.attempts(task_id) + 1
                st.append({"task_id": task_id, "attempt": n, "pid": 2,
                           "worktree": str(wt), "branch": "b",
                           "run_dir": str(rd), "model": "m"})
                return 2

            cfg = {"max_retries": 3, "model_fallbacks": [],
                   "auto_fallback": True,
                   "prompt_budget": {"failure_note_max_chars": 100}}
            with mock.patch.object(poll, "spawn_attempt", fake_spawn), \
                 mock.patch.object(poll, "reset_worktree", lambda *a, **k: None), \
                 mock.patch.object(poll, "load_card", lambda *a, **k: {"id": "TASK-900"}), \
                 mock.patch.object(poll, "set_card_status", lambda *a, **k: None):
                poll._settle(rec, cfg, store, "fail-exec", "boom", 1)

            new = store.get("TASK-900", 2)
            self.assertIsNotNone(new, "重派未落盘新 attempt 记录")
            sig = poll.sig_of("fail-exec", 1, "")
            self.assertEqual(
                new.get("sig_history"), [prev, sig],
                "新 attempt 记录必须携带累计 sig_history，否则换模型与病理守卫不可达")


if __name__ == "__main__":
    unittest.main()