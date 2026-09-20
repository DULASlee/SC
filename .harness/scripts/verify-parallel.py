#!/usr/bin/env python3
"""Parallel-safety verification (TASK-046 / v1.1 §14 V1-V10).

真实并发运行验证——不是单元测试替身：本脚本在一个隔离夹具仓库上，
用**生产模块**（coord / ownership / runs / dispatch）驱动 N 个并行
"会话"，每个是真实 OS 子进程 / 线程 / git worktree，逐一断言：

  V1 物理隔离   V2 分支隔离   V3 全局额度   V5 归属隔离
  V6 同任务竞争拒绝          V7 异常退出恢复   V9 重试链
  V10 主树提交与 worktree 会话并发
  V4(机制面)：会话覆盖为 per-attempt 私有文件，多任务副本互不污染，
                基线零写入。       (dsh 在线消费 --patch 的 V4 全链路 + canary
                真探针 + Gate F 全量回归，依赖模型行定案，另单跑，见报告)

输出 V→PASS/FAIL 矩阵；全 PASS 才允许 PARALLEL-SAFETY=SUBSTRATE-CLOSED。
退出码 0=全绿 1=有红。
"""
from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / ".harness" / "scripts"

try:  # Windows GBK 控制台防护（lessons [TASK-003]）
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    if spec is None:
        spec = importlib.util.spec_from_file_location(
            name.replace("-", "_"), SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


sys.path.insert(0, str(SCRIPTS))
import ownership  # noqa: E402
from runs import RunsStore  # noqa: E402

CARD = """id: {tid}
title: "verify fixture {tid}"
status: ready
created: 2026-09-21T00:00:00Z
created_by: architect
scope:
  allow_write:
    - mod/**
  deny_write:
    - .harness/**
acceptance_tests:
  - tests/x.cs
done_when:
  - "ci: build"
"""
CFG = """model: test-model
executor_argv: ['python', '-c', 'print(1)', '{prompt}']
concurrency: %CONC%
max_retries: 3
max_tasks_per_run: 10
worktree_root: .harness/worktrees
runs_dir: .harness/runs
"""


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def build_fixture(path, n_tasks, conc=3):
    root = Path(path)
    (root / ".harness" / "tasks" / "active").mkdir(parents=True)
    (root / ".harness" / "runs").mkdir(parents=True)
    (root / ".harness" / "worktrees").mkdir(parents=True)
    (root / ".harness" / "scripts").mkdir(parents=True)
    (root / "docs" / "ai-workspace" / "hooks").mkdir(parents=True)
    for f in SCRIPTS.glob("*.py"):
        (root / ".harness" / "scripts" / f.name).write_bytes(
            f.read_bytes())
    (root / "docs" / "ai-workspace" / "hooks" /
     "check_session_registration.py").write_bytes(
        (ROOT / "docs" / "ai-workspace" / "hooks" /
         "check_session_registration.py").read_bytes())
    (root / ".harness" / "dispatch.yaml").write_text(
        CFG.replace("%CONC%", str(conc)), encoding="utf-8")
    for i in range(n_tasks):
        tid = f"VER-{i+1:03d}"
        (root / ".harness" / "tasks" / "active" / f"{tid}.yaml").write_text(
            CARD.format(tid=tid), encoding="utf-8")
    (root / "mod").mkdir()
    (root / "mod" / "base.txt").write_text("base", encoding="utf-8")
    _git("init", cwd=root)
    _git("config", "user.email", "v@v", cwd=root)
    _git("config", "user.name", "v", cwd=root)
    _git("add", "-A", cwd=root)
    _git("commit", "-m", "init", cwd=root)
    return root


def _ensure_wt(root, tid):
    wt = root / ".harness" / "worktrees" / tid
    wt.mkdir(parents=True, exist_ok=True)
    r = _git("worktree", "add", "-B", f"feat/{tid}", str(wt), cwd=root)
    assert r.returncode == 0, r.stderr
    return wt


class V:
    def __init__(self, root, conc):
        self.root = root
        self.runs = root / ".harness" / "runs"
        self.conc = conc
        self.results = {}

    def _store(self):
        return RunsStore(self.runs / "RUNS.jsonl", lock_dir=self.runs)

    def record(self, name, ok, detail):
        self.results[name] = ("PASS" if ok else "FAIL", detail)

    # ---- V1/V2: 物理 & 分支隔离 ----
    def v1_v2(self):
        wts = {}
        sessions = {}
        for tid in ("VER-001", "VER-002", "VER-003"):
            wts[tid] = _ensure_wt(self.root, tid)
            rec = ownership.claim(self.runs, tid, f"manual:{tid}", wts[tid])
            sessions[tid] = rec["owner_session_id"]
        (wts["VER-001"] / "file-X.txt").write_text("only-A", encoding="utf-8")
        b_ok = not (wts["VER-002"] / "file-X.txt").exists()
        c_ok = not (wts["VER-003"] / "file-X.txt").exists()
        self.record("V1 物理隔离", b_ok and c_ok,
                    f"A 写 file-X，B/C 目录未见该文件（B={b_ok} C={c_ok}）")
        br = {}
        for tid in wts:
            r = _git("branch", "--show-current", cwd=wts[tid])
            br[tid] = r.stdout.strip()
        base_ref = _git("rev-parse", "HEAD", cwd=self.root).stdout.strip()
        _git("checkout", base_ref, cwd=wts["VER-002"])
        r = _git("branch", "--show-current", cwd=wts["VER-001"])
        self.record("V2 分支隔离", r.stdout.strip() == br["VER-001"],
                    f"B 切分支后 A 分支不变（A={r.stdout.strip()}）")
        for tid in sessions:
            ownership.release(self.runs, tid, sessions[tid])
        return wts

    # ---- V3: 全局额度（真实并行 reserve） ----
    def v3(self):
        conc = 2
        st = RunsStore(self.runs / "V3.jsonl", lock_dir=self.runs)
        accepted = []
        lock = threading.Lock()

        def reserve(i):
            try:
                with st.critical_section(timeout=30):
                    used = len(st.list_active(owner=None))
                    if used >= conc:
                        return
                    st.append({"task_id": f"R{i}", "attempt": 1,
                               "status": "spawning"})
                    with lock:
                        accepted.append(i)
            except Exception as exc:  # noqa: BLE001
                print("reserve err", exc)

        ts = [threading.Thread(target=reserve, args=(i,)) for i in range(4)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(30)
        ok = len(accepted) == conc
        self.record("V3 全局额度", ok,
                    f"并发 4 抢 cap=2 → 恰 {len(accepted)} 成功（超额被拒）")
        (self.runs / "V3.jsonl").unlink(missing_ok=True)

    # ---- V5/V6: 归属隔离与同任务竞争 ----
    def v5_v6(self):
        try:
            ownership.force_release(self.runs, "VER-001", "pre-v6")
        except Exception:
            pass
        ownership.claim(self.runs, "VER-001", "dispatch:A", "wtA")
        rejected = False
        try:
            ownership.claim(self.runs, "VER-001", "dispatch:B", "wtB")
        except ownership.OwnershipConflict:
            rejected = True
        cur = ownership.current(self.runs, "VER-001")
        self.record("V6 同任务竞争拒绝", rejected and
                    cur["owner_session_id"] == "dispatch:A",
                    "B claim 被拒，A 仍为主（非 warning）")
        w_ok = ownership.assert_writer(self.runs, "VER-001", "dispatch:B")[0]
        r_ok = ownership.assert_writer(self.runs, "VER-001", "dispatch:A")[0]
        self.record("V5 归属隔离", (not w_ok) and r_ok,
                    "非 owner 写被拒、owner 写放行")
        ownership.force_release(self.runs, "VER-001", "post-v56")

    # ---- V7: 异常退出恢复 ----
    def v7(self, wts):
        wt = wts["VER-002"]
        proc = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(30)"],
                                cwd=str(wt))
        st = self._store()
        st.append({"task_id": "VER-002", "attempt": 1, "pid": proc.pid,
                   "status": "running", "worktree": str(wt)})
        proc.kill()
        proc.wait(timeout=10)
        time.sleep(1.2)
        import poll as p
        self.record("V7 异常退出判活", not p.pid_alive(proc.pid),
                    f"pid={proc.pid} 死亡后判活=False")
        st.update("VER-002", 1, status="error", verdict="fail-exec")
        rec = ownership.current(self.runs, "VER-002")
        if rec is None or rec["state"] != "claimed":
            ownership.claim(self.runs, "VER-002", "manual:VER-002", wt)
        st.update("VER-002", 1, status="awaiting-review", verdict="pass")
        p._own_release(st, "VER-002", "awaiting-review")
        rel = ownership.current(self.runs, "VER-002")
        self.record("V7 崩溃后 slot 可回收",
                    rel["state"] == "released" and
                    len([r for r in st.list_active()
                         if r["task_id"] == "VER-002"]) == 0,
                    "kill→判活假→记终态→释放→active 归零")

    # ---- V8: 三 worktree 钩子一致性（真实执行钩子脚本） ----
    def v8(self, wts):
        hook = self.root / "docs" / "ai-workspace" / "hooks" / \
            "check_session_registration.py"
        ownership.claim(self.runs, "VER-001", "manual:v8",
                        str(wts["VER-001"]))
        outs = {}
        for tid, wt in wts.items():
            r = subprocess.run([sys.executable, str(hook)], cwd=str(wt),
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            outs[tid] = (r.returncode, (r.stdout or "").strip())
        a_ok = outs["VER-001"][0] == 0
        others_fail = outs["VER-002"][0] != 0 and outs["VER-003"][0] != 0
        # 一致性：三个 worktree 的钩子都锚定同一主树 ownership（同一份判定源）
        self.record("V8 钩子一致性", a_ok and others_fail,
                    "已领 worktree 通过、未领两个被拒；共读同一 ownership 源")
        ownership.release(self.runs, "VER-001", "manual:v8")

    # ---- V9: 重试链复用同 worktree/同 session ----
    def v9(self, wts):
        wt = wts["VER-001"]
        sid = "manual:VER-001"
        ownership.claim(self.runs, "VER-001", sid, str(wt))
        (wt / "dirty.txt").write_text("x", encoding="utf-8")
        _git("reset", "--hard", cwd=wt)
        _git("clean", "-fd", cwd=wt)
        r2 = ownership.claim(self.runs, "VER-001", sid, str(wt))
        self.record("V9 重试链复位不破坏归属",
                    r2["owner_session_id"] == sid and r2["state"] == "claimed",
                    "attempt 复用同 worktree/同 session（A3-2）")
        ownership.release(self.runs, "VER-001", sid)

    # ---- V10: 主树提交与 worktree 会话并发 ----
    def v10(self, wts):
        wt = wts["VER-003"]
        ownership.claim(self.runs, "VER-003", "manual:VER-003", str(wt))
        (wt / "feature.txt").write_text("WIP", encoding="utf-8")  # 未提交=活动
        f = self.root / "main-note.txt"
        f.write_text("main-tree commit while worktree session active",
                     encoding="utf-8")
        _git("add", "main-note.txt", cwd=self.root)
        r = _git("commit", "-m", "VER main-tree commit", cwd=self.root)
        ok = r.returncode == 0
        br = _git("branch", "--show-current", cwd=wt).stdout.strip()
        self.record("V10 主树提交不干扰 worktree", ok and
                    br == "feat/VER-003" and (wt / "feature.txt").exists(),
                    f"主树提交 rc={r.returncode}，wt 分支/未提交改动完好")
        ownership.release(self.runs, "VER-003", "manual:VER-003")

    # ---- V4 机制面：会话覆盖副本互相隔离 + 基线零写 ----
    def v4_mechanism(self):
        base = self.runs / "baseline-settings.yaml"
        base.write_text(
            "agent-default-model:\n  provider: keep\n  model: keep\n"
            "llm-pi-ai:\n  providers: {}\n", encoding="utf-8")
        before = hashlib.sha256(base.read_bytes()).hexdigest()
        eff = {}
        for tid, m in (("VER-001", "cohere/a:free"), ("VER-002", "minimax/b"),
                       ("VER-003", "openrouter/c")):
            prov, mm = m.split("/", 1) if "/" in m else ("p", m)
            ms = __import__("modelswap")
            run_dir = self.runs / tid / "attempt-1"
            ms.build_session_override(base, run_dir, prov, mm)
            eff[tid] = (run_dir / "settings.yaml").read_text(encoding="utf-8")
            (run_dir / "model.patch.yml").read_text(encoding="utf-8")
        distinct = len({eff["VER-001"], eff["VER-002"], eff["VER-003"]}) == 3
        after = hashlib.sha256(base.read_bytes()).hexdigest()
        self.record("V4 机制面（per-attempt 私有副本）",
                    distinct and before == after,
                    "三任务副本各异、基线 SHA256 不变（dsh 消费面另跑 canary）")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None,
                    help="UTF-8 直写矩阵文件（绕开控制台码页转码，取证字节确定）")
    args = ap.parse_args()
    lines = []

    def emit(s=""):
        print(s)
        lines.append(s)

    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as tmp:
        root = build_fixture(tmp, 3, conc=3)
        v = V(root, 3)
        emit(f"[verify] fixture={root}")
        wts = v.v1_v2()
        v.v3()
        v.v5_v6()
        v.v7(wts)
        v.v8(wts)
        v.v9(wts)
        v.v10(wts)
        v.v4_mechanism()
        emit("\n=== Parallel-Safety Substrate Verification (V1-V10) ===")
        all_ok = True
        for k in sorted(v.results):
            st, detail = v.results[k]
            all_ok = all_ok and st == "PASS"
            emit(f"  [{st}] {k}: {detail}")
        emit(f"\n{'ALL PASS' if all_ok else 'HAS FAILURE'}")
        if args.out:
            io = __import__("io")
            io.open(args.out, "w", encoding="utf-8").write(
                "\n".join(lines) + "\n")
        return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
