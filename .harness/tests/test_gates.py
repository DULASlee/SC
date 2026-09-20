"""新门禁/账本/fallback 链的 TDD 测试（先 FAIL 后 PASS）。

覆盖：
1. canary.py：缺文件→True、等价→False、argv 变化→True、probe 只做签名存在性检查
2. dispatch worktree 洁净门：脏拒绝 / 复位后放行
3. modelswap 快照 + verify
4. poll 上游账本：is_upstream_fault、budget_attempts、_settle 上游/普通两路
5. fallback 冻结/命中两路（replan + poll _settle 集成）
6. poll 收尾模型校验：恢复一致无 note、不一致 WARN + note
"""
import importlib.util
import inspect
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def load(name, alias=None):
    path = SCRIPTS / name
    mod_name = alias or name.replace("-", "_").replace(".py", "")
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def git(*args, cwd):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    return r.stdout


SETTINGS = """ui-onboarding:
  welcomeNoticeVersion: 2026-08-13.1
agent-default-model:
  provider: openrouter
  model: deepseek/deepseek-v4-flash-0731:free
llm-pi-ai:
  providers: {}
"""


class TestCanary(unittest.TestCase):
    def test_probe_exists_with_signature_no_dsh_call(self):
        canary = load("canary.py", "harness_canary_sig")
        self.assertTrue(callable(getattr(canary, "probe", None)))
        sig = inspect.signature(canary.probe)
        self.assertEqual(list(sig.parameters), ["executor_argv", "run_dir"])
        # 不许真调 dsh：只检查存在性与签名，本测试绝不调用 probe()

    def test_missing_state_requires(self):
        canary = load("canary.py", "harness_canary_missing")
        with TemporaryDirectory() as tmp:
            canary.HARNESS_DIR = Path(tmp)
            cfg = {"executor_argv": ["dsh", "--profile", "headless",
                                    "{prompt}"]}
            self.assertTrue(canary.is_required(cfg))

    def test_equivalent_snapshot_not_required(self):
        canary = load("canary.py", "harness_canary_same")
        with TemporaryDirectory() as tmp:
            canary.HARNESS_DIR = Path(tmp)
            argv = ["dsh", "--profile", "headless", "{prompt}"]
            canary.record_state(argv)
            self.assertTrue(canary.state_path().exists())
            self.assertFalse(canary.is_required({"executor_argv": argv}))

    def test_argv_change_requires(self):
        canary = load("canary.py", "harness_canary_argv")
        with TemporaryDirectory() as tmp:
            canary.HARNESS_DIR = Path(tmp)
            canary.record_state(["dsh", "--profile", "headless", "{prompt}"])
            cfg = {"executor_argv": ["dsh", "--profile", "other",
                                    "{prompt}"]}
            self.assertTrue(canary.is_required(cfg))

    def test_state_record_shape(self):
        canary = load("canary.py", "harness_canary_shape")
        with TemporaryDirectory() as tmp:
            canary.HARNESS_DIR = Path(tmp)
            canary.record_state(["dsh", "x", "{prompt}"])
            import json
            doc = json.loads(canary.state_path().read_text(encoding="utf-8"))
            for k in ("executor_argv", "run_exec_sha1", "node_version",
                      "machine", "ts"):
                self.assertIn(k, doc, k)


class TestWorktreeGate(unittest.TestCase):
    def _repo(self, root):
        git("init", cwd=root)
        git("config", "user.email", "t@t", cwd=root)
        git("config", "user.name", "t", cwd=root)
        (root / "a.txt").write_text("a", encoding="utf-8")
        git("add", "-A", cwd=root)
        git("commit", "-m", "init", cwd=root)

    def test_dirty_first_attempt_rejected(self):
        dispatch = load("dispatch.py", "harness_dispatch_dirty")
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root)
            (root / "dirty.txt").write_text("dirty", encoding="utf-8")
            self.assertTrue(dispatch.is_worktree_dirty(root))
            with self.assertRaises(RuntimeError):
                dispatch.check_worktree_gate(root, "TASK-901", 1)

    def test_retry_resets_then_passes(self):
        dispatch = load("dispatch.py", "harness_dispatch_reset")
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root)
            (root / "dirty.txt").write_text("dirty", encoding="utf-8")
            dispatch.check_worktree_gate(root, "TASK-901", 2)
            self.assertFalse(dispatch.is_worktree_dirty(root))

    def test_clean_passes(self):
        dispatch = load("dispatch.py", "harness_dispatch_clean")
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root)
            dispatch.check_worktree_gate(root, "TASK-901", 1)
            self.assertFalse(dispatch.is_worktree_dirty(root))


class TestSnapshotVerify(unittest.TestCase):
    def test_snapshot_writes_file(self):
        ms = load("modelswap.py", "harness_ms_snap")
        with TemporaryDirectory() as tmp:
            sp = Path(tmp) / "settings.yaml"
            sp.write_text(SETTINGS, encoding="utf-8")
            dest = Path(tmp) / "snaps"
            out = ms.snapshot(sp, "pre-swap", dest)
            self.assertTrue(Path(out).exists())
            self.assertIn("settings.snapshot.pre-swap.", Path(out).name)
            self.assertEqual(Path(out).read_bytes(), sp.read_bytes())

    def test_verify_true_and_false(self):
        ms = load("modelswap.py", "harness_ms_verify")
        with TemporaryDirectory() as tmp:
            sp = Path(tmp) / "settings.yaml"
            sp.write_text(SETTINGS, encoding="utf-8")
            self.assertTrue(ms.verify_selection(
                sp, "openrouter", "deepseek/deepseek-v4-flash-0731:free"))
            self.assertFalse(ms.verify_selection(sp, "openrouter", "other:free"))


class TestUpstreamLedger(unittest.TestCase):
    def test_is_upstream_fault_patterns(self):
        poll = load("poll.py", "harness_poll_up1")
        for text in ("no healthy upstream right now",
                     "NO HEALTHY UPSTREAM",
                     "provider returned error: bad gateway",
                     "provider_overloaded, retry later",
                     "PROVIDER_OVERLOADED",
                     "no healthy provider available",
                     "NO HEALTHY PROVIDER"):
            self.assertTrue(poll.is_upstream_fault(text), text)
        self.assertFalse(poll.is_upstream_fault("Traceback FileNotFoundError"))
        self.assertFalse(poll.is_upstream_fault(""))

    def test_bare_503_not_upstream(self):
        poll = load("poll.py", "harness_poll_up_bare503")
        # 裸 503 数字不再豁免：端口号/状态码数字不得误命中
        for text in ("port 8083", "Error 503 Service Unavailable",
                     "request failed: 503, try later", "listen on port 5030"):
            self.assertFalse(poll.is_upstream_fault(text), text)

    def test_budget_attempts_excludes_upstream(self):
        runs = load("runs.py", "harness_runs_budget")
        with TemporaryDirectory() as tmp:
            store = runs.RunsStore(Path(tmp) / "RUNS.jsonl")
            base = {"pid": 1, "worktree": "w", "branch": "b", "run_dir": "r",
                    "model": "m", "executor": "e", "status": "running"}
            store.append({**base, "task_id": "T1", "attempt": 1})
            store.append({**base, "task_id": "T1", "attempt": 2,
                          "upstream_fault": True, "status": "retrying"})
            store.append({**base, "task_id": "T1", "attempt": 3})
            self.assertEqual(store.attempts("T1"), 3)
            self.assertEqual(store.budget_attempts("T1"), 2)

    def _settle_env(self, tmp, stderr_text):
        poll = load("poll.py", f"harness_poll_settle_{len(stderr_text)}_"
                               f"{abs(hash(stderr_text)) % 100000}")
        runs = load("runs.py", poll.__name__ + "_runs")
        store = runs.RunsStore(Path(tmp) / "RUNS.jsonl")
        run_dir = Path(tmp) / "run1"
        run_dir.mkdir()
        (run_dir / "stderr.log").write_text(stderr_text, encoding="utf-8")
        (run_dir / "exitcode.txt").write_text("1", encoding="utf-8")
        wt = Path(tmp) / "wt"
        wt.mkdir()
        rec = store.append({"task_id": "TASK-901", "attempt": 1, "pid": 999999,
                            "worktree": str(wt), "branch": "feat/TASK-901",
                            "run_dir": str(run_dir), "model": "m",
                            "executor": "e", "status": "running"})
        cfg = {"max_retries": 3, "model_fallbacks": [],
               "prompt_budget": {"failure_note_max_chars": 2000}}
        captured = {}
        poll.reset_worktree = lambda wt_: None
        poll.set_card_status = lambda tid, st: None
        poll.load_card = lambda p: {"id": "TASK-901"}

        def fake_spawn(tid, card, cfg_, store_, note, prompt_override=None,
                       stage="execute", model_override=None, owner="dispatch"):
            captured["model_override"] = model_override
            captured["note"] = note
            store_.append({"task_id": tid, "attempt": 2, "pid": 111,
                           "worktree": "w", "branch": "b", "run_dir": "r",
                           "model": "m", "executor": "e", "status": "running"})
            return 111
        poll.spawn_attempt = fake_spawn
        return poll, store, cfg, rec, captured

    def test_settle_upstream_no_sig_no_budget(self):
        with TemporaryDirectory() as tmp:
            poll, store, cfg, rec, captured = self._settle_env(
                tmp, "provider_overloaded, retry later")
            poll._settle(rec, cfg, store, "fail-exec", "exitcode=1", 1)
            got = store.get("TASK-901", 1)
            self.assertTrue(got.get("upstream_fault"))
            self.assertEqual(got.get("sig_history"), [])
            # 上游轮不耗预算：2 条记录里只有新重试轮计入预算
            self.assertEqual(store.budget_attempts("TASK-901"), 1)
            self.assertEqual(got.get("verdict"), "fail-exec")
            # 照常重试但不升级模型
            self.assertIsNone(captured.get("model_override"))
            self.assertEqual(store.attempts("TASK-901"), 2)

    def test_settle_normal_appends_sig(self):
        with TemporaryDirectory() as tmp:
            poll, store, cfg, rec, captured = self._settle_env(
                tmp, "Traceback: FileNotFoundError mod/a.txt")
            poll._settle(rec, cfg, store, "fail-exec", "exitcode=1", 1)
            got = store.get("TASK-901", 1)
            self.assertFalse(got.get("upstream_fault", False))
            self.assertEqual(len(got.get("sig_history")), 1)
            self.assertEqual(store.budget_attempts("TASK-901"), 2)

    def test_upstream_streak_consecutive_5_blocked(self):
        with TemporaryDirectory() as tmp:
            poll, store, cfg, rec, captured = self._settle_env(
                tmp, "provider_overloaded, retry later")
            # 模拟已连续 4 次上游故障，本轮第 5 次应转 blocked
            store.update("TASK-901", 1, upstream_streak=4)
            rec = store.get("TASK-901", 1)
            blocked = []
            poll.set_card_status = lambda tid, st: blocked.append((tid, st))
            poll._settle(rec, cfg, store, "fail-exec", "exitcode=1", 1)
            got = store.get("TASK-901", 1)
            self.assertEqual(got.get("upstream_streak"), 5)
            self.assertEqual(got.get("status"), "blocked")
            self.assertIn(("TASK-901", "blocked"), blocked)
            # 达上限不再重派新 attempt
            self.assertEqual(store.attempts("TASK-901"), 1)

    def test_upstream_streak_reset_on_non_upstream(self):
        with TemporaryDirectory() as tmp:
            poll, store, cfg, rec, captured = self._settle_env(
                tmp, "Traceback: ordinary failure")
            store.update("TASK-901", 1, upstream_streak=3)
            rec = store.get("TASK-901", 1)
            poll._settle(rec, cfg, store, "fail-exec", "exitcode=1", 1)
            got = store.get("TASK-901", 1)
            self.assertEqual(got.get("upstream_streak"), 0)
            self.assertFalse(got.get("upstream_fault", False))

    def test_upstream_streak_increment_and_propagate(self):
        with TemporaryDirectory() as tmp:
            poll, store, cfg, rec, captured = self._settle_env(
                tmp, "no healthy provider, retry later")
            poll._settle(rec, cfg, store, "fail-exec", "exitcode=1", 1)
            got = store.get("TASK-901", 1)
            self.assertEqual(got.get("upstream_streak"), 1)
            nxt = store.get("TASK-901", 2)
            self.assertIsNotNone(nxt)
            self.assertEqual(nxt.get("upstream_streak"), 1)


class TestFallbackFreeze(unittest.TestCase):
    def test_frozen_escalation(self):
        replan = load("replan.py", "harness_replan_frozen")
        d = replan.plan_retry(["aa", "aa"], 2, 4, ["m2"], auto_fallback=False)
        self.assertEqual(d["action"], "retry_escalated")
        self.assertIsNone(d["model_override"])
        self.assertIn("fallback \u5c31\u7eea\u4f46 pilot \u51bb\u7ed3\uff0c"
                      "\u9700\u4eba\u5de5\u6279\u51c6", d["note_prefix"])
        self.assertFalse(d["model_fallback_hit"])
        # 同模型重跑：note 前缀保留 ESCALATE_PREFIX
        self.assertTrue(d["note_prefix"].startswith(replan.ESCALATE_PREFIX))

    def test_frozen_no_fallback_still_same_model_retry(self):
        replan = load("replan.py", "harness_replan_frozen_empty")
        d = replan.plan_retry(["aa", "aa"], 2, 4, [], auto_fallback=False)
        self.assertEqual(d["action"], "retry_escalated")
        self.assertIsNone(d["model_override"])
        self.assertTrue(d["note_prefix"].startswith(replan.ESCALATE_PREFIX))
        self.assertIn("pilot \u51bb\u7ed3", d["note_prefix"])
        self.assertFalse(d["model_fallback_hit"])

    def test_hit_escalation(self):
        replan = load("replan.py", "harness_replan_hit")
        d = replan.plan_retry(["aa", "aa"], 2, 4, ["m2"], auto_fallback=True)
        self.assertEqual(d["action"], "retry_escalated")
        self.assertEqual(d["model_override"], "m2")
        self.assertTrue(d["model_fallback_hit"])

    def test_settle_records_hit_flag(self):
        poll = load("poll.py", "harness_poll_hitflag")
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run1"
            run_dir.mkdir()
            (run_dir / "stderr.log").write_text("ordinary fail",
                                                encoding="utf-8")
            (run_dir / "exitcode.txt").write_text("1", encoding="utf-8")
            wt = Path(tmp) / "wt"
            wt.mkdir()
            runs = load("runs.py", "harness_poll_hitflag_runs")
            store = runs.RunsStore(Path(tmp) / "RUNS.jsonl")
            rec = store.append({"task_id": "T1", "attempt": 3, "pid": 1,
                                "worktree": str(wt), "branch": "b",
                                "run_dir": str(run_dir), "model": "m",
                                "executor": "e", "status": "running",
                                "sig_history": ["X", "S"]})
            poll.sig_of = lambda *a: "S"  # hist -> [X,S,S] 尾随2次→升级
            poll.reset_worktree = lambda wt_: None
            poll.set_card_status = lambda tid, st: None
            poll.load_card = lambda p: {"id": "T1"}
            captured = {}

            def fake_spawn(tid, card, cfg_, store_, note,
                           prompt_override=None, stage="execute",
                           model_override=None, owner="dispatch"):
                captured["model_override"] = model_override
                captured["note"] = note
                store_.append({"task_id": tid, "attempt": 4, "pid": 2,
                               "worktree": "w", "branch": "b", "run_dir": "r",
                               "model": "m", "executor": "e",
                               "status": "running"})
                return 2
            poll.spawn_attempt = fake_spawn
            cfg = {"max_retries": 5, "model_fallbacks": ["m2"],
                   "auto_fallback": True,
                   "prompt_budget": {"failure_note_max_chars": 2000}}
            poll._settle(rec, cfg, store, "fail-exec", "exitcode=1", 1)
            got = store.get("T1", 3)
            self.assertEqual(captured.get("model_override"), "m2")
            self.assertTrue(got.get("model_fallback_hit"))

    def test_settle_records_frozen_flag(self):
        poll = load("poll.py", "harness_poll_frozenflag")
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run1"
            run_dir.mkdir()
            (run_dir / "stderr.log").write_text("ordinary fail",
                                                encoding="utf-8")
            (run_dir / "exitcode.txt").write_text("1", encoding="utf-8")
            wt = Path(tmp) / "wt"
            wt.mkdir()
            runs = load("runs.py", "harness_poll_frozenflag_runs")
            store = runs.RunsStore(Path(tmp) / "RUNS.jsonl")
            rec = store.append({"task_id": "T1", "attempt": 3, "pid": 1,
                                "worktree": str(wt), "branch": "b",
                                "run_dir": str(run_dir), "model": "m",
                                "executor": "e", "status": "running",
                                "sig_history": ["X", "S"]})
            poll.sig_of = lambda *a: "S"
            poll.reset_worktree = lambda wt_: None
            poll.set_card_status = lambda tid, st: None
            poll.load_card = lambda p: {"id": "T1"}
            captured = {}

            def fake_spawn(tid, card, cfg_, store_, note,
                           prompt_override=None, stage="execute",
                           model_override=None, owner="dispatch"):
                captured["model_override"] = model_override
                captured["note"] = note
                store_.append({"task_id": tid, "attempt": 4, "pid": 2,
                               "worktree": "w", "branch": "b", "run_dir": "r",
                               "model": "m", "executor": "e",
                               "status": "running"})
                return 2
            poll.spawn_attempt = fake_spawn
            cfg = {"max_retries": 5, "model_fallbacks": ["m2"],
                   "auto_fallback": False,
                   "prompt_budget": {"failure_note_max_chars": 2000}}
            poll._settle(rec, cfg, store, "fail-exec", "exitcode=1", 1)
            got = store.get("T1", 3)
            self.assertIsNone(captured.get("model_override"))
            self.assertFalse(got.get("model_fallback_hit"))
            self.assertIn("pilot \u51bb\u7ed3", captured.get("note", ""))


class TestFinalizeVerify(unittest.TestCase):
    def test_restore_consistent_no_note(self):
        poll = load("poll.py", "harness_poll_fin_ok")
        ms = load("modelswap.py", "harness_poll_fin_ok_ms")
        with TemporaryDirectory() as tmp:
            sp = Path(tmp) / "settings.yaml"
            sp.write_text(SETTINGS.replace(
                "deepseek/deepseek-v4-flash-0731:free",
                "cohere/north-mini-code:free"), encoding="utf-8")
            runs = load("runs.py", "harness_poll_fin_ok_runs")
            store = runs.RunsStore(Path(tmp) / "RUNS.jsonl")

            class _S:
                def list_running(self, owner="dispatch"):
                    return []
            just = [{"task_id": "T1", "attempt": 1,
                     "model_swapped": True,
                     "prev_model": ["openrouter",
                                    "deepseek/deepseek-v4-flash-0731:free"]}]
            ret = poll.finalize_model_restore(sp, _S(), just)
            self.assertEqual(
                ret, ("openrouter", "deepseek/deepseek-v4-flash-0731:free"))
            self.assertTrue(ms.verify_selection(
                sp, "openrouter", "deepseek/deepseek-v4-flash-0731:free"))

    def test_mismatch_warns_and_notes(self):
        poll = load("poll.py", "harness_poll_fin_warn")
        with TemporaryDirectory() as tmp:
            sp = Path(tmp) / "settings.yaml"
            sp.write_text(SETTINGS, encoding="utf-8")
            runs = load("runs.py", "harness_poll_fin_warn_runs")
            store = runs.RunsStore(Path(tmp) / "RUNS.jsonl")
            store.append({"task_id": "T1", "attempt": 1, "pid": 1,
                          "worktree": "w", "branch": "b", "run_dir": "r",
                          "model": "m", "executor": "e",
                          "status": "awaiting-review",
                          "model_swapped": True,
                          "prev_model": ["openrouter", "orig:free"]})
            # 恢复后仍不一致：桩掉 verify，模拟外部又改了回来
            poll.verify_selection = lambda sp_, p, m: False
            poll.read_selection = lambda sp_: ("openrouter", "hijacked:free")
            just = store._read_all()
            poll.finalize_model_restore(sp, store, just)
            got = store.get("T1", 1)
            self.assertIn("[WARN]", got.get("note", ""))
            self.assertIn("orig:free", got.get("note", ""))


if __name__ == "__main__":
    unittest.main()
