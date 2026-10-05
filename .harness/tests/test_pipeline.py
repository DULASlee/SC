import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

PIPE = Path(__file__).resolve().parent.parent / "scripts" / "pipeline.py"
POLL = Path(__file__).resolve().parent.parent / "scripts" / "poll.py"
RUNS = Path(__file__).resolve().parent.parent / "scripts" / "runs.py"


def load_pipeline():
    spec = importlib.util.spec_from_file_location("harness_pipeline", PIPE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_poll():
    spec = importlib.util.spec_from_file_location("harness_poll_fix", POLL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_runs():
    spec = importlib.util.spec_from_file_location("harness_runs_fix", RUNS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestStages(unittest.TestCase):
    def test_stages_order(self):
        mod = load_pipeline()
        self.assertEqual(
            mod.STAGES,
            ["analysis", "spec", "plan", "execute", "check",
             "test", "evidence", "accept", "pr"],
        )

    def test_stages_no_duplicates(self):
        mod = load_pipeline()
        self.assertEqual(len(mod.STAGES), len(set(mod.STAGES)))

    def test_next_stage_boundary(self):
        mod = load_pipeline()
        self.assertEqual(mod.next_stage("analysis"), "spec")
        self.assertEqual(mod.next_stage("accept"), "pr")
        self.assertIsNone(mod.next_stage("pr"))


class TestVerifiers(unittest.TestCase):
    def test_verify_analysis_pos(self):
        mod = load_pipeline()
        with TemporaryDirectory() as tmp:
            rd = Path(tmp)
            (rd / "analysis.md").write_text("# A\n\n## 现状\nxxx\n",
                                            encoding="utf-8")
            self.assertTrue(mod.verify_analysis(rd))

    def test_verify_analysis_neg_missing(self):
        mod = load_pipeline()
        with TemporaryDirectory() as tmp:
            rd = Path(tmp)
            self.assertFalse(mod.verify_analysis(rd))

    def test_verify_analysis_neg_no_header(self):
        mod = load_pipeline()
        with TemporaryDirectory() as tmp:
            rd = Path(tmp)
            (rd / "analysis.md").write_text("no header here\n",
                                            encoding="utf-8")
            self.assertFalse(mod.verify_analysis(rd))

    def test_verify_plan_pos(self):
        mod = load_pipeline()
        with TemporaryDirectory() as tmp:
            rd = Path(tmp)
            (rd / "plan.md").write_text("# 计划\n\n- [ ] step1\n",
                                        encoding="utf-8")
            self.assertTrue(mod.verify_plan(rd))

    def test_verify_plan_neg(self):
        mod = load_pipeline()
        with TemporaryDirectory() as tmp:
            rd = Path(tmp)
            (rd / "plan.md").write_text("no title\nxxx\n", encoding="utf-8")
            self.assertFalse(mod.verify_plan(rd))
            (rd / "plan.md").write_text("# T\nno task\n", encoding="utf-8")
            self.assertFalse(mod.verify_plan(rd))


class TestAcceptProtected(unittest.TestCase):
    def test_protected_without_preapproved_returns_manual(self):
        mod = load_pipeline()
        card = {"id": "TASK-901", "pre_approved": False}
        cfg = {}
        with mock.patch.object(
                mod, "_changed_files",
                return_value=["tests/foo.cs"]) as ch:
            with mock.patch.object(mod, "_run_verify") as rv:
                res = mod.run_accept("TASK-901", card, cfg)
                ch.assert_called_once()
                rv.assert_not_called()
        self.assertEqual(res, (False, "转人工：触碰受保护路径且无预批"))

    def test_protected_with_preapproved_continues_to_verify(self):
        mod = load_pipeline()
        card = {"id": "TASK-901", "pre_approved": True}
        cfg = {}
        with mock.patch.object(
                mod, "_changed_files",
                return_value=["tests/foo.cs"]):
            with mock.patch.object(mod, "_run_verify",
                                   return_value=0) as rv:
                with mock.patch.object(
                        mod, "_mark_done_and_archive",
                        return_value=None) as md:
                    res = mod.run_accept("TASK-901", card, cfg)
                    rv.assert_called_once()
                    md.assert_called_once()
        self.assertTrue(res is True or res == (True, "done"))


if __name__ == "__main__":
    unittest.main()


class TestSpawnAtomicity(unittest.TestCase):
    def _cfg(self, tmp):
        return {"runs_dir": str(Path(tmp)),
                "worktree_root": ".harness/worktrees",
                "executor_argv": ["agent", "{prompt}"],
                "model": "m", "skills_dir": None}

    def test_spawn_writes_spawning_before_popen(self):
        mod = load_pipeline()
        runs = load_runs()
        with TemporaryDirectory() as tmp:
            store = runs.RunsStore(Path(tmp) / "PIPELINE.jsonl")
            cfg = self._cfg(tmp)
            card = {"id": "TASK-901"}
            seen = {}

            def fake_popen(*a, **k):
                recs = store._read_all()
                self.assertTrue(recs)
                seen["status"] = recs[-1].get("status")
                seen["pid"] = recs[-1].get("pid")
                m = mock.Mock()
                m.pid = 9999
                return m

            with mock.patch.object(mod, "ensure_worktree",
                                   return_value=Path(tmp) / "wt"):
                with mock.patch.object(mod.subprocess, "Popen",
                                       side_effect=fake_popen):
                    pid = mod.spawn_stage("TASK-901", card, cfg, store,
                                          "analysis")
            self.assertEqual(pid, 9999)
            self.assertEqual(seen.get("status"), "spawning")
            self.assertIsNone(seen.get("pid"))
            last = store._read_all()[-1]
            self.assertEqual(last["status"], "running")
            self.assertEqual(last["pid"], 9999)

    def test_spawn_popen_error_marks_error(self):
        mod = load_pipeline()
        runs = load_runs()
        with TemporaryDirectory() as tmp:
            store = runs.RunsStore(Path(tmp) / "PIPELINE.jsonl")
            cfg = self._cfg(tmp)
            card = {"id": "TASK-901"}
            with mock.patch.object(mod, "ensure_worktree",
                                   return_value=Path(tmp) / "wt"):
                with mock.patch.object(mod.subprocess, "Popen",
                                       side_effect=OSError("boom")):
                    with self.assertRaises(OSError):
                        mod.spawn_stage("TASK-901", card, cfg, store,
                                        "analysis")
            last = store._read_all()[-1]
            self.assertEqual(last["status"], "error")

    def test_spawning_fresh_waits_stale_reaps(self):
        mod = load_pipeline()
        runs = load_runs()
        with TemporaryDirectory() as tmp:
            store = runs.RunsStore(Path(tmp) / "PIPELINE.jsonl")
            cfg = self._cfg(tmp)
            card = {"id": "TASK-901"}
            store.append({"task_id": "TASK-901", "attempt": 1,
                          "pid": None, "worktree": tmp,
                          "branch": "feat/TASK-901",
                          "run_dir": tmp, "model": "m",
                          "stage": "analysis", "owner": "pipeline",
                          "status": "spawning"})
            res = mod.advance("TASK-901", card, cfg, store)
            self.assertEqual(res, ("spawning", "analysis"))
            # 人工做旧 started_at 超过 10 分钟 → stale 标 error 并重派
            import json
            from datetime import datetime, timedelta, timezone
            p = Path(tmp) / "PIPELINE.jsonl"
            recs = [json.loads(l) for l in
                    p.read_text(encoding="utf-8").splitlines() if l.strip()]
            old = (datetime.now(timezone.utc)
                   - timedelta(seconds=700)).isoformat()
            recs[-1]["started_at"] = old
            p.write_text("\n".join(json.dumps(r, ensure_ascii=False)
                                   for r in recs) + "\n", encoding="utf-8")
            with mock.patch.object(mod, "spawn_stage",
                                   return_value=1234) as sp:
                res2 = mod.advance("TASK-901", card, cfg, store)
                sp.assert_called_once()
            self.assertEqual(res2, ("spawn", "analysis"))


class TestAcceptPrSync(unittest.TestCase):
    def _cfg(self, tmp):
        return {"runs_dir": str(Path(tmp)),
                "worktree_root": ".harness/worktrees",
                "model": "m", "pr_enabled": True}

    def test_accept_sync_writes_done_stage_no_running(self):
        mod = load_pipeline()
        runs = load_runs()
        with TemporaryDirectory() as tmp:
            store = runs.RunsStore(Path(tmp) / "PIPELINE.jsonl")
            cfg = self._cfg(tmp)
            card = {"id": "TASK-901"}
            store.append({"task_id": "TASK-901", "attempt": 1,
                          "pid": 111, "worktree": tmp,
                          "branch": "feat/TASK-901", "run_dir": tmp,
                          "model": "m", "stage": "evidence",
                          "owner": "pipeline", "status": "awaiting-review",
                          "verdict": "pass"})
            with mock.patch.object(mod, "_accept_already_done",
                                   return_value=False):
                with mock.patch.object(mod, "run_accept",
                                       return_value=True) as ra:
                    res = mod.advance("TASK-901", card, cfg, store)
                    ra.assert_called_once()
            self.assertEqual(res, ("pass", "accept"))
            recs = store._read_all()
            self.assertFalse(any(r.get("stage") == "accept"
                                 and r.get("status") == "running"
                                 for r in recs))
            self.assertEqual(recs[-1]["status"], "done-stage")
            self.assertEqual(recs[-1]["verdict"], "pass")

    def test_accept_idempotent_skips_when_archived(self):
        mod = load_pipeline()
        runs = load_runs()
        with TemporaryDirectory() as tmp:
            store = runs.RunsStore(Path(tmp) / "PIPELINE.jsonl")
            cfg = self._cfg(tmp)
            card = {"id": "TASK-901"}
            store.append({"task_id": "TASK-901", "attempt": 1,
                          "pid": 111, "worktree": tmp,
                          "branch": "feat/TASK-901", "run_dir": tmp,
                          "model": "m", "stage": "evidence",
                          "owner": "pipeline", "status": "awaiting-review",
                          "verdict": "pass"})
            with mock.patch.object(mod, "_accept_already_done",
                                   return_value=True):
                with mock.patch.object(mod, "run_accept") as ra:
                    res = mod.advance("TASK-901", card, cfg, store)
                    ra.assert_not_called()
            self.assertEqual(res, ("pass", "accept"))
            self.assertEqual(store._read_all()[-1]["status"], "done-stage")

    def test_pr_idempotent_skips_when_pr_exists(self):
        mod = load_pipeline()
        runs = load_runs()
        with TemporaryDirectory() as tmp:
            store = runs.RunsStore(Path(tmp) / "PIPELINE.jsonl")
            cfg = self._cfg(tmp)
            card = {"id": "TASK-901"}
            store.append({"task_id": "TASK-901", "attempt": 1,
                          "pid": None, "worktree": tmp,
                          "branch": "feat/TASK-901", "run_dir": tmp,
                          "model": "m", "stage": "accept",
                          "owner": "pipeline", "status": "done-stage",
                          "verdict": "pass"})
            with mock.patch.object(mod, "_pr_already_done",
                                   return_value=True):
                with mock.patch.object(mod, "run_pr") as rp:
                    res = mod.advance("TASK-901", card, cfg, store)
                    rp.assert_not_called()
            self.assertEqual(res, ("pass", "pr"))
            self.assertEqual(store._read_all()[-1]["status"], "pr-open")


class TestPollSkipsPipeline(unittest.TestCase):
    def test_poll_skips_pipeline_card(self):
        poll = load_poll()
        runs = load_runs()
        with TemporaryDirectory() as tmp:
            store = runs.RunsStore(Path(tmp) / "RUNS.jsonl")
            store.append({"task_id": "TASK-901", "attempt": 1, "pid": 4242,
                          "worktree": tmp, "branch": "feat/TASK-901",
                          "run_dir": tmp, "model": "m", "stage": "execute",
                          "owner": "dispatch", "status": "running"})
            rec = store._read_all()[-1]
            cfg = {"max_retries": 1}
            with mock.patch.object(poll, "load_card",
                                   return_value={"id": "TASK-901",
                                                 "pipeline": True}):
                with mock.patch.object(poll, "pid_alive") as pa:
                    with mock.patch.object(store, "update") as up:
                        poll._handle_record(rec, cfg, store)
                        pa.assert_not_called()
                        up.assert_not_called()


class TestRunPrMissingBinary(unittest.TestCase):
    def test_run_pr_file_not_found_goes_pr_manual(self):
        mod = load_pipeline()
        cfg = {"pr_enabled": True}
        with mock.patch.object(mod, "_run",
                               side_effect=FileNotFoundError("gh")):
            res = mod.run_pr("TASK-901", cfg)
        self.assertFalse(res[0])
        self.assertIn("pr-manual", res[1])

    def test_advance_pr_manual_verdict(self):
        mod = load_pipeline()
        runs = load_runs()
        with TemporaryDirectory() as tmp:
            store = runs.RunsStore(Path(tmp) / "PIPELINE.jsonl")
            cfg = {"runs_dir": str(Path(tmp)),
                   "worktree_root": ".harness/worktrees",
                   "model": "m", "pr_enabled": True}
            card = {"id": "TASK-901"}
            store.append({"task_id": "TASK-901", "attempt": 1,
                          "pid": None, "worktree": tmp,
                          "branch": "feat/TASK-901", "run_dir": tmp,
                          "model": "m", "stage": "accept",
                          "owner": "pipeline", "status": "done-stage",
                          "verdict": "pass"})
            with mock.patch.object(mod, "_pr_already_done",
                                   return_value=False):
                with mock.patch.object(mod, "_run",
                                       side_effect=FileNotFoundError("gh")):
                    res = mod.advance("TASK-901", card, cfg, store)
            self.assertEqual(res[0], "pr-manual")
            last = store._read_all()[-1]
            self.assertEqual(last["status"], "pr-manual")
            self.assertEqual(last["verdict"], "pr-manual")
