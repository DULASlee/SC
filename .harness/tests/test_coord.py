"""TASK-043: coord.py 跨进程可重入协调锁测试。"""
import importlib.util
import os
import subprocess
import sys
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]


def load_coord():
    spec = importlib.util.spec_from_file_location(
        "coord", ROOT / ".harness" / "scripts" / "coord.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestCoord(unittest.TestCase):
    def test_acquire_release_dir_lifecycle(self):
        c = load_coord()
        with TemporaryDirectory() as tmp:
            runs = Path(tmp)
            lock = c.acquire(runs, timeout=1)
            self.assertTrue(lock.is_dir())
            self.assertEqual((lock / "pid").read_text(encoding="utf-8"),
                             str(os.getpid()))
            c.release(runs)
            self.assertFalse(lock.exists())

    def test_same_thread_reentrant(self):
        c = load_coord()
        with TemporaryDirectory() as tmp:
            runs = Path(tmp)
            c.acquire(runs, timeout=1)
            try:
                c.acquire(runs, timeout=0)  # 重入不得超时/死锁
                with c.critical_section(runs, timeout=0):
                    pass
                # 内层 release 两次后仍持有（计数未到 0）
                c.release(runs)
                self.assertTrue(c.lock_dir_for(runs).is_dir())
            finally:
                c.release(runs)
            self.assertFalse(c.lock_dir_for(runs).is_dir())

    def test_cross_thread_contention_times_out(self):
        c = load_coord()
        with TemporaryDirectory() as tmp:
            runs = Path(tmp)
            c.acquire(runs, timeout=1)
            errors = []

            def other():
                try:
                    c.acquire(runs, timeout=0.3)
                    errors.append("acquired while held")
                except TimeoutError:
                    pass

            t = threading.Thread(target=other)
            t.start()
            t.join(5)
            c.release(runs)
            self.assertEqual(errors, [])

    def test_cross_process_contention_times_out(self):
        c = load_coord()
        with TemporaryDirectory() as tmp:
            runs = Path(tmp)
            script = (
                "import sys, time;"
                f"sys.path.insert(0, {str(ROOT / '.harness' / 'scripts')!r});"
                "import coord;"
                f"coord.acquire({str(runs)!r}, timeout=5);"
                "print('HELD', flush=True);"
                "time.sleep(3)")
            proc = subprocess.Popen([sys.executable, "-c", script],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8")
            try:
                # 等子进程真持有锁
                first = proc.stdout.readline()
                self.assertIn("HELD", first)
                with self.assertRaises(TimeoutError):
                    c.acquire(runs, timeout=0.5)
            finally:
                proc.kill()
                proc.wait(timeout=10)
            # 子进程被强杀，锁目录残留且 mtime 新鲜（父线程未持有，release 无效）
            lock = c.lock_dir_for(runs)
            self.assertTrue(lock.is_dir())
            old = (datetime.now() - timedelta(seconds=c.STALE_SECONDS + 60)
                   ).timestamp()
            os.utime(lock, (old, old))
            c.acquire(runs, timeout=2)  # stale 恢复路径（§11 崩溃不留永久锁）
            c.release(runs)
            self.assertFalse(lock.exists())

    def test_stale_lock_broken_after_600s(self):
        c = load_coord()
        with TemporaryDirectory() as tmp:
            runs = Path(tmp)
            lock = c.lock_dir_for(runs)
            lock.mkdir(parents=True)
            (lock / "pid").write_text("99999999", encoding="utf-8")
            old = (datetime.now() - timedelta(seconds=c.STALE_SECONDS + 60)
                   ).timestamp()
            os.utime(lock, (old, old))
            got = c.acquire(runs, timeout=1)  # stale 被打破
            self.assertTrue(got.is_dir())
            self.assertEqual((got / "pid").read_text(encoding="utf-8"),
                             str(os.getpid()))
            c.release(runs)

    def test_is_held_tracks_state(self):
        c = load_coord()
        with TemporaryDirectory() as tmp:
            runs = Path(tmp)
            self.assertFalse(c.is_held(runs))
            c.acquire(runs, timeout=1)
            try:
                self.assertTrue(c.is_held(runs))
            finally:
                c.release(runs)
            self.assertFalse(c.is_held(runs))


# ---------- TASK-043 集成面：双账本统一保护 ----------

SCRIPTS = ROOT / ".harness" / "scripts"


def load_mod(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(mod)
    return mod


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


class TestRunsLockIntegration(unittest.TestCase):
    def test_list_active_counts_spawning(self):
        runs = load_mod("runs")
        with TemporaryDirectory() as tmp:
            st = runs.RunsStore(Path(tmp) / "RUNS.jsonl")
            st.append({"task_id": "T1", "attempt": 1, "status": "spawning"})
            st.append({"task_id": "T2", "attempt": 1, "status": "running"})
            st.append({"task_id": "T3", "attempt": 1,
                       "status": "awaiting-review"})
            self.assertEqual(
                sorted(r["task_id"] for r in st.list_active()),
                ["T1", "T2"])
            self.assertEqual(len(st.list_running()), 1)

    def test_reentrant_writes_under_outer_section(self):
        runs = load_mod("runs")
        with TemporaryDirectory() as tmp:
            p = Path(tmp)
            st = runs.RunsStore(p / "RUNS.jsonl", lock_dir=p)
            with st.critical_section():
                st.append({"task_id": "T1", "attempt": 1})
                st.update("T1", 1, status="done-stage")
            self.assertEqual(st.list_active(owner=None), [])

    def test_concurrent_thread_appends_no_loss(self):
        runs = load_mod("runs")
        with TemporaryDirectory() as tmp:
            p = Path(tmp)
            st = runs.RunsStore(p / "RUNS.jsonl", lock_dir=p)

            def worker(n):
                s2 = runs.RunsStore(p / "RUNS.jsonl", lock_dir=p)
                for i in range(10):
                    s2.append({"task_id": f"T{n}", "attempt": i + 1})

            ts = [threading.Thread(target=worker, args=(n,))
                  for n in range(4)]
            for t in ts:
                t.start()
            for t in ts:
                t.join(60)
            self.assertEqual(len(st._read_all()), 40)


class TestDispatchCapacity(unittest.TestCase):
    def test_capacity_used_sums_both_ledgers(self):
        disp = load_mod("dispatch")
        runs = load_mod("runs")
        with TemporaryDirectory() as tmp:
            p = Path(tmp)
            a = runs.RunsStore(p / "RUNS.jsonl")
            b = runs.RunsStore(p / "PIPELINE.jsonl")
            a.append({"task_id": "T1", "attempt": 1})
            a.append({"task_id": "T2", "attempt": 1, "status": "spawning"})
            b.append({"task_id": "P1", "attempt": 1, "owner": "pipeline"})
            self.assertEqual(disp.capacity_used([a, b]), 3)
            self.assertEqual(disp.running_count(a), 2)

    def test_running_count_includes_spawning(self):
        disp = load_mod("dispatch")
        runs = load_mod("runs")
        with TemporaryDirectory() as tmp:
            st = runs.RunsStore(Path(tmp) / "RUNS.jsonl")
            st.append({"task_id": "T1", "attempt": 1})
            st.append({"task_id": "T2", "attempt": 1, "status": "spawning"})
            self.assertEqual(disp.running_count(st), 2)


class TestPollGc(unittest.TestCase):
    def test_gc_stale_spawned_marks_error(self):
        poll = load_mod("poll")
        runs = load_mod("runs")
        with TemporaryDirectory() as tmp:
            st = runs.RunsStore(Path(tmp) / "RUNS.jsonl")
            st.append({"task_id": "T1", "attempt": 1, "status": "spawning",
                       "started_at": "2020-01-01T00:00:00+00:00"})
            st.append({"task_id": "T2", "attempt": 1, "status": "spawning"})
            n = poll.gc_stale_spawned(st)
            self.assertEqual(n, 1)
            r1 = st.get("T1", 1)
            self.assertEqual(r1["status"], "error")
            self.assertIn("stale spawning", r1.get("note", ""))
            self.assertEqual(st.get("T2", 1)["status"], "spawning")

    def test_gc_worktrees_reclaims_clean_keeps_dirty_unknown(self):
        poll = load_mod("poll")
        runs = load_mod("runs")
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            git("init", cwd=root)
            git("config", "user.email", "t@t", cwd=root)
            git("config", "user.name", "t", cwd=root)
            (root / "a.txt").write_text("a", encoding="utf-8")
            git("add", "-A", cwd=root)
            git("commit", "-m", "init", cwd=root)
            cfg = {"worktree_root": ".harness/worktrees",
                   "runs_dir": ".harness/runs"}
            wt_root = root / cfg["worktree_root"]
            wt_root.mkdir(parents=True)
            for name in ("TDONE", "TDIRTY", "TACTIVE", "TUNKNOWN"):
                wt = wt_root / name
                r = git("worktree", "add", "-B", f"feat/{name}", str(wt),
                        cwd=root)
                self.assertEqual(r.returncode, 0, r.stderr)
            (wt_root / "TDIRTY" / "dirty.txt").write_text(
                "x", encoding="utf-8")
            st = runs.RunsStore(root / ".harness" / "runs" / "RUNS.jsonl")
            st.append({"task_id": "TDONE", "attempt": 1,
                       "status": "awaiting-review"})
            st.append({"task_id": "TDIRTY", "attempt": 1,
                       "status": "awaiting-review"})
            st.append({"task_id": "TACTIVE", "attempt": 1})
            n = poll.gc_worktrees(cfg, st, root)
            self.assertEqual(n, 1)
            self.assertFalse((wt_root / "TDONE").exists())
            self.assertTrue((wt_root / "TDIRTY").exists())
            self.assertTrue((wt_root / "TACTIVE").exists())
            self.assertTrue((wt_root / "TUNKNOWN").exists())
            br = git("branch", "--list", "feat/TDONE", cwd=root)
            self.assertIn("feat/TDONE", br.stdout)


if __name__ == "__main__":
    unittest.main()
