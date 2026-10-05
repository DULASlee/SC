"""loop 常驻单实例循环测试（TDD 先行）。

覆盖：锁互斥+释放；STOP 文件判停；cycle 顺序 dispatch→pipeline→poll；
落盘日志 loop.log；退出语义 print_exit_note；锁归属 + stale 打破。
"""
import contextlib
import importlib.util
import io
import os
import shutil
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

LOOP_PY = (Path(__file__).resolve().parent.parent / "scripts" / "loop.py")


def load_loop():
    spec = importlib.util.spec_from_file_location("harness_loop", LOOP_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestSingletonLock(unittest.TestCase):
    def test_double_acquire_raises_timeout_and_release(self):
        loop = load_loop()
        with TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            loop.acquire_singleton(runs_dir, timeout=1)
            with self.assertRaises(TimeoutError):
                loop.acquire_singleton(runs_dir, timeout=1)
            loop.release_singleton(runs_dir)
            # 释放后可重新获取
            loop.acquire_singleton(runs_dir, timeout=1)
            loop.release_singleton(runs_dir)
            # 释放缺失不抛错
            loop.release_singleton(runs_dir)


class TestShouldStop(unittest.TestCase):
    def test_stop_file_exists_means_stop(self):
        loop = load_loop()
        with TemporaryDirectory() as tmp:
            stop = Path(tmp) / "STOP"
            self.assertFalse(loop.should_stop(stop))
            stop.write_text("stop", encoding="utf-8")
            self.assertTrue(loop.should_stop(stop))


class TestCycleOrder(unittest.TestCase):
    def test_cycle_calls_dispatch_pipeline_poll_in_order(self):
        loop = load_loop()
        calls: list = []
        with mock.patch.object(loop, "run_dispatch",
                               side_effect=lambda extra: calls.append("dispatch") or 0), \
             mock.patch.object(loop, "run_pipeline",
                               side_effect=lambda: calls.append("pipeline") or 0), \
             mock.patch.object(loop, "run_poll",
                               side_effect=lambda: calls.append("poll") or 0):
            loop.cycle(None)
        self.assertEqual(calls, ["dispatch", "pipeline", "poll"])

    def test_cycle_passes_max_tasks_to_dispatch(self):
        loop = load_loop()
        seen: dict = {}
        def fake_dispatch(extra):
            seen["extra"] = extra
            return 0
        with mock.patch.object(loop, "run_dispatch", side_effect=fake_dispatch), \
             mock.patch.object(loop, "run_pipeline", return_value=0), \
             mock.patch.object(loop, "run_poll", return_value=0):
            loop.cycle(3)
        self.assertEqual(seen["extra"], ["--max-tasks", "3"])


class TestLoopLogToDisk(unittest.TestCase):
    def test_run_dispatch_appends_full_output_to_loop_log(self):
        loop = load_loop()
        with TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "loop.log"
            head_marker = "HEAD-MARKER-ABC123"
            big_out = head_marker + "X" * 5000 + "TAIL-END"
            fake = mock.Mock(stdout=big_out,
                             stderr="ERR-FULL-XYZ", returncode=0)
            printed: list = []

            def fake_print(*a, **k):
                printed.append(" ".join(str(x) for x in a))

            with mock.patch.object(loop.subprocess, "run",
                                   return_value=fake), \
                 mock.patch.object(loop, "_loop_log_path",
                                   return_value=log_path), \
                 mock.patch("builtins.print", side_effect=fake_print):
                rc = loop.run_dispatch()
            self.assertEqual(rc, 0)
            self.assertTrue(log_path.exists())
            content = log_path.read_text(encoding="utf-8")
            # 落盘含完整输出（含终端被截掉的头部）+ 脚本名分隔行
            self.assertIn(head_marker, content)
            self.assertIn("TAIL-END", content)
            self.assertIn("ERR-FULL-XYZ", content)
            self.assertIn("dispatch.py", content)
            # 终端只剩尾 2000 字符：头部 marker 不出现在终端
            self.assertNotIn(head_marker, "\n".join(printed))


class TestExitNote(unittest.TestCase):
    def test_print_exit_note_line(self):
        loop = load_loop()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            loop.print_exit_note()
        self.assertIn(
            "[INFO] loop 退出；已派发的 dsh 任务继续运行，"
            "由下次 poll.py 回收（fire-and-forget 设计）",
            buf.getvalue())

    def test_once_path_prints_exit_note(self):
        loop = load_loop()
        with TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            argv = ["loop.py", "--once"]
            with mock.patch.object(loop, "_load_interval",
                                   return_value=(0, runs_dir)), \
                 mock.patch.object(loop, "acquire_singleton",
                                   return_value=runs_dir / "loop.lock"), \
                 mock.patch.object(loop, "release_singleton",
                                   return_value=None), \
                 mock.patch.object(loop, "cycle", return_value=0), \
                 mock.patch.object(loop.sys, "argv", argv):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = loop.main()
                self.assertEqual(rc, 0)
                self.assertIn(loop.EXIT_NOTE, buf.getvalue())


class TestStaleLockOwnership(unittest.TestCase):
    FOREIGN_PID = "999999999"

    def _plant_foreign_lock(self, runs_dir: Path, old: bool) -> Path:
        lock = runs_dir / "loop.lock"
        lock.mkdir(parents=False, exist_ok=False)
        (lock / "pid").write_text(self.FOREIGN_PID, encoding="utf-8")
        if old:
            ancient = time.time() - 700
            os.utime(lock, (ancient, ancient))
        return lock

    def test_stale_foreign_lock_is_broken(self):
        loop = load_loop()
        with TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            self._plant_foreign_lock(runs_dir, old=True)
            lock = loop.acquire_singleton(runs_dir, timeout=5)
            self.assertTrue(lock.exists())
            mine = (lock / "pid").read_text(encoding="utf-8").strip()
            self.assertEqual(mine, str(os.getpid()))
            loop.release_singleton(runs_dir)
            self.assertFalse(lock.exists())

    def test_fresh_foreign_lock_times_out_and_not_deleted(self):
        loop = load_loop()
        with TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            lock = self._plant_foreign_lock(runs_dir, old=False)
            with self.assertRaises(TimeoutError):
                loop.acquire_singleton(runs_dir, timeout=1)
            # 他人新锁不被删：acquire 超时 + release 跳过
            self.assertTrue(lock.exists())
            loop.release_singleton(runs_dir)
            self.assertTrue(lock.exists())
            shutil.rmtree(lock, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
