#!/usr/bin/env python3
"""Phase2 九阶段管线（pipeline，一轮只推进一步）。

STAGES = analysis/spec/plan/execute/check/test/evidence/accept/pr。
账本复用 RunsStore，另开 .harness/runs/PIPELINE.jsonl，owner 固定 pipeline。
每卡每轮 advance() 只做一个动作（spawn 或 reap其一）。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = HARNESS_DIR.parent
sys.path.insert(0, str(HARNESS_DIR / "scripts"))
from runs import RunsStore  # noqa: E402
from skills import DEFAULT_SKILLS_BY_STAGE  # noqa: E402
from dispatch import (  # noqa: E402
    build_prompt,
    card_self_authorized,
    ensure_worktree,
    load_card,
    load_config,
    resolve_model,
    write_skills_file,
)
from dispatch import spawn_attempt as dispatch_spawn_attempt  # noqa: E402
import poll as poll_mod  # noqa: E402

SCRIPTS_DIR = HARNESS_DIR / "scripts"
ACTIVE_DIR = HARNESS_DIR / "tasks" / "active"

STAGES = ["analysis", "spec", "plan", "execute", "check",
          "test", "evidence", "accept", "pr"]

TEST_TIMEOUT_SECONDS = 1200
PROTECTED_PATHS = ["tests/", "contracts/", ".harness/", ".githooks/"]

PIPELINE_LEDGER = "PIPELINE.jsonl"

SPAWNING_STALE_SECONDS = 600

ARCHIVE_DIR = HARNESS_DIR / "tasks" / "archive"

# 同步终态集合：accept/pr 同步执行直接落终态，不经过 running
SYNC_DONE_STATUSES = ("done-stage", "pr-open", "pr-manual")


def next_stage(s: str) -> str | None:
    try:
        i = STAGES.index(s)
    except ValueError:
        return None
    if i + 1 >= len(STAGES):
        return None
    return STAGES[i + 1]


def stage_skills(stage: str, card: dict) -> list[str]:
    names = (card or {}).get("skills") or []
    if names:
        return list(names)
    return list(DEFAULT_SKILLS_BY_STAGE.get(stage, []) or [])


def pipeline_store(cfg: dict) -> RunsStore:
    runs_dir = REPO_ROOT / cfg.get("runs_dir", ".harness/runs")
    return RunsStore(runs_dir / PIPELINE_LEDGER)


def pipe_run_dir(task_id: str, stage: str, n: int, cfg: dict) -> Path:
    runs_dir = REPO_ROOT / cfg.get("runs_dir", ".harness/runs")
    return runs_dir / task_id / f"pipe-{stage}-{n}"


def _all_for(store: RunsStore, task_id: str) -> list[dict]:
    try:
        recs = store._read_all()
    except AttributeError:
        recs = []
    return [r for r in recs if r.get("task_id") == task_id]


def _stage_count(store: RunsStore, task_id: str, stage: str) -> int:
    return sum(1 for r in _all_for(store, task_id)
               if r.get("stage") == stage)


def last_record(store: RunsStore, task_id: str) -> dict | None:
    recs = _all_for(store, task_id)
    if not recs:
        return None
    return recs[-1]


def current_stage(store: RunsStore, task_id: str) -> str:
    last = last_record(store, task_id)
    if last is None:
        return STAGES[0]
    if last.get("status") in ("running", "spawning"):
        return last.get("stage") or STAGES[0]
    nxt = next_stage(last.get("stage") or "")
    return nxt or STAGES[-1]


def _spawning_age_seconds(rec: dict) -> float | None:
    ts = (rec or {}).get("started_at")
    if not ts:
        return None
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(str(ts))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - dt).total_seconds()
    except Exception:
        return None


def _accept_already_done(task_id: str) -> bool:
    try:
        return (ARCHIVE_DIR / f"{task_id}.yaml").exists()
    except OSError:
        return False


def _pr_already_done(task_id: str) -> bool:
    branch = f"feat/{task_id}"
    try:
        code, out, _err = _run(
            ["gh", "pr", "view", "--head", branch], REPO_ROOT)
    except (FileNotFoundError, OSError):
        return False
    return code == 0 and bool((out or "").strip())


# ---------- verifier 纯函数 ----------

def verify_analysis(run_dir: Path) -> bool:
    f = Path(run_dir) / "analysis.md"
    try:
        text = f.read_text(encoding="utf-8")
    except OSError:
        return False
    return "## " in text


def verify_spec(worktree: Path, task_id: str) -> bool:
    f = Path(worktree) / "docs" / "superpowers" / "spec" / f"TASK-{task_id}-spec.md"
    # 兼容 task_id 已带 TASK- 前缀的调用
    if not f.exists():
        alt = Path(worktree) / "docs" / "superpowers" / "spec" / f"{task_id}-spec.md"
        if alt.exists():
            f = alt
    try:
        text = f.read_text(encoding="utf-8")
    except OSError:
        return False
    return ("## 背景" in text) and ("## 方案" in text) and ("## 验收" in text)


def verify_plan(run_dir: Path) -> bool:
    f = Path(run_dir) / "plan.md"
    try:
        text = f.read_text(encoding="utf-8")
    except OSError:
        return False
    stripped = text.lstrip()
    return stripped.startswith("# ") and ("- [ ]" in text)


def verify_test(worktree: Path, card: dict, files: list[str]) -> bool:
    # 全量 dotnet 检查留给人类 verify-all，本函数只做静态存在+触碰检查。
    acceptance = (card or {}).get("acceptance_tests") or []
    if not acceptance:
        return False
    flist = [str(x) for x in (files or [])]
    for a in acceptance:
        a_s = str(a)
        exists = (Path(worktree) / a_s).is_file()
        if not exists:
            continue
        for f in flist:
            if f == a_s or f.endswith("/" + a_s):
                return True
    return False


def verify_evidence(run_dir: Path) -> bool:
    f = Path(run_dir) / "EVIDENCE.md"
    try:
        text = f.read_text(encoding="utf-8")
    except OSError:
        return False
    return "## 门禁" in text


# ---------- spawn / reap ----------

def _run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout or "", p.stderr or ""


def spawn_stage(task_id: str, card: dict, cfg: dict, store: RunsStore,
                stage: str, failure_note: str | None = None) -> int:
    """通用 headless 派发：cwd 为任务 worktree，run_dir 为 pipe 目录。"""
    if stage in ("execute", "check"):
        eff_card = dict(card)
        if not eff_card.get("skills"):
            eff_card["skills"] = list(
                DEFAULT_SKILLS_BY_STAGE.get(stage, [])
                or DEFAULT_SKILLS_BY_STAGE.get("execute", []))
        return dispatch_spawn_attempt(
            task_id, eff_card, cfg, store, failure_note,
            stage="execute", owner="pipeline")
    wt = ensure_worktree(task_id, REPO_ROOT, REPO_ROOT / cfg["worktree_root"])
    n = _stage_count(store, task_id, stage) + 1
    run_dir = pipe_run_dir(task_id, stage, n, cfg)
    run_dir.mkdir(parents=True, exist_ok=True)
    names = stage_skills(stage, card)
    skills_ctx: str | None = None
    if names and cfg.get("skills_dir"):
        spath = write_skills_file(task_id, names, cfg)
        if spath is not None:
            skills_ctx = ("附带的 skill 工作流（必须遵守）："
                          f"{spath.resolve().as_posix()}")
    ctx = HARNESS_DIR / "context" / f"{task_id}-context.md"
    model = resolve_model(card, cfg)
    prompt = build_prompt(ctx.resolve(), model, failure_note, skills_ctx)
    prompt = (f"[{stage}] {prompt}\n产物一律写 worktree 相对路径，"
              f"不要写绝对路径。run_dir={run_dir.as_posix()}")
    argv = [a.replace("{prompt}", prompt) for a in cfg["executor_argv"]]
    # 原子性：先落盘(spawning, pid=None)后拉起，避免 Popen 成功但落盘前崩溃的孤儿进程
    rec = store.append({"task_id": task_id, "attempt": n, "pid": None,
                        "worktree": str(wt), "branch": f"feat/{task_id}",
                        "run_dir": str(run_dir), "model": model,
                        "stage": stage, "owner": "pipeline",
                        "status": "spawning",
                        "executor": " ".join(argv[:3])})
    try:
        proc = subprocess.Popen(
            [sys.executable, str(SCRIPTS_DIR / "run-exec.py"),
             "--run-dir", str(run_dir), "--", *argv],
            cwd=wt)
    except Exception as exc:
        try:
            store.update(task_id, n, status="error", verdict="fail-exec")
        except KeyError:
            pass
        print(f"[FAIL] pipeline 派发起失败 {task_id} {stage}："
              f"{type(exc).__name__}: {exc}", flush=True)
        raise
    store.update(task_id, n, status="running", pid=proc.pid)
    print(f"[OK] pipeline 已派发 {task_id} {stage} pipe-{n} pid={proc.pid}",
          flush=True)
    return proc.pid


def _changed_files(task_id: str, cfg: dict) -> list[str]:
    wt = REPO_ROOT / cfg.get("worktree_root", ".harness/worktrees") / task_id
    if wt.is_dir():
        try:
            files, _scale = poll_mod.worktree_changes(wt)
            return files
        except Exception:
            pass
    code, out, _err = _run(
        ["git", "-c", "core.quotepath=off", "diff", "--name-only", "HEAD"],
        REPO_ROOT)
    if code != 0:
        return []
    return [l.strip() for l in out.splitlines() if l.strip()]


def _run_verify(task_id: str) -> int:
    cmd = [sys.executable, str(SCRIPTS_DIR / "verify-all.py"),
           "--task-id", task_id, "--operator", "dispatcher"]
    p = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace",
                       timeout=TEST_TIMEOUT_SECONDS)
    return p.returncode


def _touches_protected(files: list[str]) -> str | None:
    for f in files:
        fs = str(f).replace("\\", "/")
        for p in PROTECTED_PATHS:
            if fs == p.rstrip("/") or fs.startswith(p):
                return fs
    return None


def _mark_done_and_archive(task_id: str, card: dict, cfg: dict) -> None:
    import re

    import yaml

    # TASK-023：卡文件可带人类可读后缀（check-pr-scope v3.1 同规则），
    # 按 id 前缀在 active/ 唯一解析卡文件；严格文件名假设已废弃。
    cands = sorted(ACTIVE_DIR.glob(f"{task_id}*.yaml"))
    if len(cands) != 1:
        raise RuntimeError(
            f"{task_id} 卡文件数 {len(cands)}（应唯一），拒绝机器验收")
    card_path = cands[0]
    # TASK-023 自覆盖契约：机器验收提交命中 .harness/** 保护，
    # 卡须含非空 approver + allow_write 自覆盖（D2：approver 人工签发，不自动补）。
    pre = card_self_authorized(load_card(card_path),
                              card_path.relative_to(REPO_ROOT).as_posix())
    if pre:
        raise RuntimeError(f"{task_id} 机器验收提交拒绝：{pre}")
    text = card_path.read_text(encoding="utf-8")
    new, n = re.subn(r"(?m)^status:.*$", "status: done", text)
    if n == 0:
        raise RuntimeError(f"{task_id} 无 status 字段，拒绝改写")
    card_path.write_text(new, encoding="utf-8")
    _run(["git", "add", str(card_path)], REPO_ROOT)
    # 机器验收提交：不带人工批标记（D1：机器验证归机器，授权归 approver——
    # 人工批准的职责是授权任务及其写入范围，不是事后给机器验收结果盖章）。
    # TASK-023：受保护路径合规由卡 approver + 自覆盖保证；归档 rename 由
    # check_approval 自生命周期规则放行（done/已归档卡只覆盖自身卡文件，
    # 保护范围不削弱）。原「hook 放行 done 路径」注释在 023 后失效，已废弃。
    _run(["git", "commit", "-m",
          f"chore(harness): {task_id} pipeline accept done",
          "--", str(card_path)], REPO_ROOT)
    code, _out, err = _run(
        [sys.executable, str(SCRIPTS_DIR / "archive-task.py"), task_id],
        REPO_ROOT)
    if code != 0:
        raise RuntimeError(f"{task_id} 归档失败：{err.strip()[:300]}")


def run_accept(task_id: str, card: dict, cfg: dict):
    files = _changed_files(task_id, cfg)
    hit = _touches_protected(files)
    if hit is not None and not (card or {}).get("pre_approved"):
        return (False, "转人工：触碰受保护路径且无预批")
    code = _run_verify(task_id)
    if code != 0:
        return (False, "fail-gate")
    _mark_done_and_archive(task_id, card, cfg)
    return True


def run_pr(task_id: str, cfg: dict):
    if not (cfg or {}).get("pr_enabled"):
        print("pr-manual：开关关闭，按 README 手工开 PR", flush=True)
        return (False, "pr-manual：开关关闭，按 README 手工开 PR")
    branch = f"feat/{task_id}"
    try:
        code, _out, err = _run(["git", "push", "origin", branch], REPO_ROOT)
    except (FileNotFoundError, OSError) as exc:
        print(f"pr-manual：git 不可用，请手工执行 git push origin "
              f"{branch}；{type(exc).__name__}: {exc}", flush=True)
        return (False, f"pr-manual：git 不可用，请手工执行 "
                       f"git push origin {branch}")
    if code != 0:
        return (False, f"pr-manual：push 失败，请手工执行 git push origin "
                       f"{branch}；{err.strip()[:200]}")
    try:
        code2, _o2, err2 = _run(
            ["gh", "pr", "create", "--fill", "--head", branch], REPO_ROOT)
    except (FileNotFoundError, OSError) as exc:
        print(f"pr-manual：gh 不可用，请手工执行 gh pr create "
              f"--fill --head {branch}；{type(exc).__name__}: {exc}",
              flush=True)
        return (False, f"pr-manual：gh 不可用，请手工执行 gh pr create "
                       f"--fill --head {branch}")
    if code2 != 0:
        return (False, f"pr-manual：gh 创建失败，请手工执行 gh pr create "
                       f"--fill --head {branch}；{err2.strip()[:200]}")
    try:
        code3, out3, _e3 = _run(
            ["gh", "pr", "view", "--head", branch], REPO_ROOT)
    except (FileNotFoundError, OSError) as exc:
        print(f"pr-manual：gh 不可用，请手工执行 gh pr view "
              f"--head {branch}；{type(exc).__name__}: {exc}", flush=True)
        return (False, f"pr-manual：gh 不可用，请手工执行 gh pr view "
                       f"--head {branch}")
    if code3 != 0 or not (out3 or "").strip():
        return (False, f"pr-manual：未找到 PR，请手工执行 gh pr view "
                       f"--head {branch}")
    return True


def _reap_running(rec: dict, card: dict, cfg: dict, store: RunsStore):
    tid = rec["task_id"]
    stage = rec.get("stage") or "execute"
    if rec.get("status") == "spawning":
        age = _spawning_age_seconds(rec)
        if age is not None and age < SPAWNING_STALE_SECONDS:
            print(f"[INFO] {tid} {stage} spawning 等待中 "
                  f"({int(age)}s<{SPAWNING_STALE_SECONDS}s)", flush=True)
            return ("spawning", stage)
        try:
            store.update(tid, rec["attempt"], status="error",
                         verdict="fail-exec")
        except KeyError:
            pass
        print(f"[WARN] {tid} {stage} spawning 超时 stale，已标 error 可重派",
              flush=True)
        return ("stale", stage)
    run_dir = Path(rec["run_dir"])
    if poll_mod.pid_alive(rec["pid"]):
        print(f"[INFO] {tid} {stage} 仍在跑 pid={rec['pid']}", flush=True)
        return ("running", stage)
    code = poll_mod.read_exitcode(run_dir)
    if code is None or code != 0:
        store.update(tid, rec["attempt"], status="blocked",
                     verdict="fail-exec", exit_code=code)
        print(f"[WARN] {tid} {stage} exitcode={code} 已标 blocked", flush=True)
        return ("blocked", stage)
    ok = False
    detail = ""
    if stage == "analysis":
        ok = verify_analysis(run_dir)
        detail = "analysis.md 门禁"
    elif stage == "spec":
        wt = Path(rec.get("worktree") or
                  (REPO_ROOT / cfg.get("worktree_root",
                                       ".harness/worktrees") / tid))
        ok = verify_spec(wt, tid)
        detail = "spec 三标题门禁"
    elif stage == "plan":
        ok = verify_plan(run_dir)
        detail = "plan.md 门禁"
    elif stage in ("execute", "check"):
        wt = Path(rec.get("worktree"))
        files, scale = poll_mod.worktree_changes(wt)
        card_live = card
        try:
            card_live = load_card(ACTIVE_DIR / f"{tid}.yaml")
        except OSError:
            pass
        verdict, detail = poll_mod.check_scope_and_scale(files, scale,
                                                         card_live)
        if verdict != "pass":
            store.update(tid, rec["attempt"], status="blocked",
                         verdict=verdict, exit_code=code)
            return ("blocked", stage)
        for sk in (card_live.get("skills") or []):
            sok, d2 = poll_mod.check_skill_evidence(sk, files, card_live)
            if not sok:
                store.update(tid, rec["attempt"], status="blocked",
                             verdict="fail-skill", exit_code=code)
                print(f"[WARN] {tid} {stage} fail-skill：{d2}", flush=True)
                return ("blocked", stage)
        ok = True
    elif stage == "test":
        # TEST 阶段不跑命令，仅静态 verifier；全量 dotnet 留给人类。
        wt = Path(rec.get("worktree"))
        files, _scale = poll_mod.worktree_changes(wt)
        card_live = card
        try:
            card_live = load_card(ACTIVE_DIR / f"{tid}.yaml")
        except OSError:
            pass
        ok = verify_test(wt, card_live, files)
        detail = "acceptance 触碰门禁"
    elif stage == "evidence":
        ok = verify_evidence(run_dir)
        detail = "EVIDENCE 门禁"
    elif stage == "accept":
        res = run_accept(tid, card, cfg)
        if res is True:
            store.update(tid, rec["attempt"], status="awaiting-review",
                         verdict="pass", exit_code=code)
            return ("pass", stage)
        _msg = res[1] if isinstance(res, tuple) else "fail-gate"
        store.update(tid, rec["attempt"], status="blocked",
                     verdict="fail-gate", exit_code=code)
        print(f"[WARN] {tid} accept 未过：{_msg}", flush=True)
        return ("blocked", stage)
    elif stage == "pr":
        res = run_pr(tid, cfg)
        if res is True:
            store.update(tid, rec["attempt"], status="awaiting-review",
                         verdict="pass", exit_code=code)
            return ("pass", stage)
        store.update(tid, rec["attempt"], status="blocked",
                     verdict="fail-gate", exit_code=code)
        return ("blocked", stage)
    else:
        ok = False
    if ok:
        store.update(tid, rec["attempt"], status="awaiting-review",
                     verdict="pass", exit_code=code)
        print(f"[OK] {tid} {stage} 门禁通过", flush=True)
        return ("pass", stage)
    store.update(tid, rec["attempt"], status="blocked",
                 verdict="fail-gate", exit_code=code)
    print(f"[WARN] {tid} {stage} 门禁未过：{detail}，已标 blocked", flush=True)
    return ("blocked", stage)


def advance(task_id: str, card: dict, cfg: dict, store: RunsStore):
    last = last_record(store, task_id)
    if last is None:
        spawn_stage(task_id, card, cfg, store, STAGES[0])
        return ("spawn", STAGES[0])
    if last.get("status") == "spawning":
        stage = last.get("stage") or STAGES[0]
        age = _spawning_age_seconds(last)
        if age is not None and age < SPAWNING_STALE_SECONDS:
            print(f"[INFO] {task_id} {stage} spawning 等待中，跳过等待",
                  flush=True)
            return ("spawning", stage)
        try:
            store.update(task_id, last["attempt"], status="error",
                         verdict="fail-exec")
        except KeyError:
            pass
        print(f"[WARN] {task_id} {stage} spawning 超时 stale，已标 error 重派",
              flush=True)
        spawn_stage(task_id, card, cfg, store, stage)
        return ("spawn", stage)
    if last.get("status") == "running":
        return _reap_running(last, card, cfg, store)
    if last.get("status") in ("blocked", "error"):
        print(f"[INFO] {task_id} 已 {last.get('status')}，等人工", flush=True)
        return ("stalled", last.get("stage"))
    if (last.get("verdict") != "pass"
            and last.get("status") not in ("awaiting-review",
                                           *SYNC_DONE_STATUSES)):
        print(f"[INFO] {task_id} 上一阶段未通过，等人工", flush=True)
        return ("stalled", last.get("stage"))
    nxt = next_stage(last.get("stage") or "")
    if nxt is None:
        print(f"[OK] {task_id} 管线已完成", flush=True)
        return ("done", None)
    # accept/pr 为同步动作：直接执行一次，不走 headless spawn，不经过 running。
    if nxt in ("accept", "pr"):
        n = _stage_count(store, task_id, nxt) + 1
        wt = REPO_ROOT / cfg.get("worktree_root",
                                 ".harness/worktrees") / task_id
        run_dir = pipe_run_dir(task_id, nxt, n, cfg)
        run_dir.mkdir(parents=True, exist_ok=True)
        base = {"task_id": task_id, "attempt": n,
                "pid": None, "worktree": str(wt),
                "branch": f"feat/{task_id}",
                "run_dir": str(run_dir),
                "model": resolve_model(card, cfg),
                "stage": nxt, "owner": "pipeline",
                "executor": "sync"}
        if nxt == "accept":
            # 重入幂等：归档已存在即 accept done，不重复执行
            if _accept_already_done(task_id):
                store.append({**base, "status": "done-stage",
                              "verdict": "pass", "exit_code": 0})
                print(f"[SKIP] {task_id} accept 已归档，直接记 done-stage",
                      flush=True)
                return ("pass", nxt)
            res = run_accept(task_id, card, cfg)
            if res is True:
                store.append({**base, "status": "done-stage",
                              "verdict": "pass", "exit_code": 0})
                return ("pass", nxt)
            store.append({**base, "status": "blocked",
                          "verdict": "fail-gate", "exit_code": 1})
            return ("blocked", nxt)
        # 重入幂等：gh 已有 PR 即 pr done，不重复执行
        if _pr_already_done(task_id):
            store.append({**base, "status": "pr-open",
                          "verdict": "pass", "exit_code": 0})
            print(f"[SKIP] {task_id} pr 已存在，直接记 pr-open", flush=True)
            return ("pass", nxt)
        res = run_pr(task_id, cfg)
        if res is True:
            store.append({**base, "status": "pr-open",
                          "verdict": "pass", "exit_code": 0})
            return ("pass", nxt)
        _msg = res[1] if isinstance(res, tuple) else "pr-manual"
        print(f"[INFO] {task_id} {_msg}", flush=True)
        store.append({**base, "status": "pr-manual",
                      "verdict": "pr-manual", "exit_code": 0})
        return ("pr-manual", nxt)
    spawn_stage(task_id, card, cfg, store, nxt)
    return ("spawn", nxt)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("task_id", nargs="?", default=None,
                    help="限定单卡，如 TASK-001")
    args = ap.parse_args()
    cfg = load_config()
    store = pipeline_store(cfg)
    cards: list[tuple[Path, dict]] = []
    if args.task_id:
        p = ACTIVE_DIR / f"{args.task_id}.yaml"
        if p.exists():
            cards = [(p, load_card(p))]
    else:
        for p in sorted(ACTIVE_DIR.glob("TASK-*.yaml")):
            try:
                c = load_card(p)
            except OSError:
                continue
            if c.get("pipeline"):
                cards.append((p, c))
    if args.dry_run:
        for _p, c in cards:
            st = current_stage(store, c["id"])
            print(f"[DRY] {c['id']} 下一阶段 {st}")
        return 0
    for _p, c in cards:
        try:
            advance(c["id"], c, cfg, store)
        except Exception as exc:  # noqa: BLE001 单卡隔离
            print(f"[FAIL] {c.get('id')} advance 异常："
                  f"{type(exc).__name__}: {exc}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
