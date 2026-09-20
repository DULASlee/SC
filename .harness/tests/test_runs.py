import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load_runs():
    path = Path(__file__).resolve().parent.parent / "scripts" / "runs.py"
    spec = importlib.util.spec_from_file_location("harness_runs", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestRunsStore(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.mod = load_runs()
        self.store = self.mod.RunsStore(Path(self.tmp.name) / "RUNS.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def test_append_and_get(self):
        rec = self.store.append({
            "task_id": "TASK-901", "attempt": 1, "pid": 1234,
            "worktree": "wt", "branch": "feat/TASK-901",
            "run_dir": "rd", "model": "m", "executor": "dsh",
            "status": "running",
        })
        self.assertIn("started_at", rec)
        got = self.store.get("TASK-901", 1)
        self.assertEqual(got["pid"], 1234)
        self.assertEqual(got["verdict"], "none")

    def test_update_and_list_running(self):
        self.store.append({"task_id": "TASK-901", "attempt": 1, "pid": 1,
                           "worktree": "w", "branch": "b", "run_dir": "r",
                           "model": "m", "executor": "e", "status": "running"})
        self.store.append({"task_id": "TASK-902", "attempt": 1, "pid": 2,
                           "worktree": "w", "branch": "b", "run_dir": "r",
                           "model": "m", "executor": "e", "status": "running"})
        self.store.update("TASK-901", 1, status="awaiting-review", verdict="pass")
        running = self.store.list_running()
        self.assertEqual([r["task_id"] for r in running], ["TASK-902"])
        self.assertEqual(self.store.get("TASK-901", 1)["status"], "awaiting-review")

    def test_attempts_counts_retries(self):
        for i in (1, 2):
            self.store.append({"task_id": "TASK-903", "attempt": i, "pid": i,
                               "worktree": "w", "branch": "b", "run_dir": "r",
                               "model": "m", "executor": "e", "status": "running"})
        self.assertEqual(self.store.attempts("TASK-903"), 2)


if __name__ == "__main__":
    unittest.main()
