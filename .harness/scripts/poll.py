#!/usr/bin/env python3
"""L3 回收器（poll，只做一轮，不常驻）。

用法：
  python .harness/scripts/poll.py

行为：查 running 记录 → pid 存活则跳过 → 已死则读 exitcode →
worktree 里跑机器门禁（卡校验 + scope + 规模三层轻检查）→ pass 进
awaiting-review；fail 且未超重试上限则复位 worktree 并重派，超限则卡标
blocked。dispatcher 永不写 done（判定权留在人类 verify-all.py + 归档）。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = HARNESS_DIR.parent
sys.path.insert(0, str(HARNESS_DIR / "scripts"))
from runs import RunsStore  # noqa: E402
from skills import cap_text, check_skill_evidence  # noqa: E402
from check_local_scope_compat import glob_to_regex  # noqa: E402
from dispatch import (  # noqa: E402  复用派发逻辑与卡状态提交，避免重复实现
    load_config, load_card, spawn_attempt, commit_card_status)
import ownership  # noqa: E402  (TASK-045)
from replan import plan_retry, sig_of  # noqa: E402  Phase2 重规划与 loop 病理

SCRIPTS_DIR = HARNESS_DIR / "scripts"
ACTIVE_DIR = HARNESS_DIR / "tasks" / "active"

# sig_history 只保留最近 N 条，防无限增长导致 RUNS.jsonl 膨胀。
SIG_HISTORY_KEEP = 20


def _own_release(store, tid: str, reason: str) -> None:
    """任务离开活动链（pass/blocked/超限）→ 释放 ownership（A3-3：
    释放后 session 方可更替）。释放失败只 WARN，不干扰回收判定。
    无锁配置的 store（测试桩/老件）跳过。"""
    ld = getattr(store, "lock_dir", None)
    if ld is None:
        return
    try:
        ownership.force_release(ld, tid, reason)
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] {tid} ownership 释放异常（{reason}）："
              f"{type(exc).__name__}: {exc}")

# 上游故障指纹（不分大小写）：命中即上游账本，不记病理、不耗预算。
# 注意：不用裸 "503" 子串（"port 8083" 等端口数字会误命中），只认短语。
UPSTREAM_PATTERNS = (
    "no healthy upstream",
    "provider returned error",
    "provider_overloaded",
    "no healthy provider",
)

# 上游连续故障上限：连续达此次数则标 blocked 交人工，防无限重试。
UPSTREAM_MAX_CONSECUTIVE = 5


def is_upstream_fault(stderr: str) -> bool:
    """stderr 是否为上游故障（匹配即 True，不分大小写）。"""
    s = (stderr or "").lower()
    return any(p in s for p in UPSTREAM_PATTERNS)


def run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout or "", p.stderr or ""


def pid_alive(pid: int) -> bool:
    """Windows 无新依赖判活：tasklist 按 PID 过滤，命中数据行即存活。"""
    p = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    for line in (p.stdout or "").splitlines():
        cols = line.split('","')
        # CSV 无表头行形如："name.exe","1234","Console","1","1,234 K"
        if len(cols) >= 2 and cols[1].strip('"') == str(pid):
            return True
    return False


def read_exitcode(run_dir: Path) -> int | None:
    f = run_dir / "exitcode.txt"
    if not f.exists():
        return None
    try:
        return int(f.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def worktree_changes(worktree: Path) -> tuple[list[str], dict[str, int]]:
    """收集 worktree 里**未提交**的变更：(变更文件列表, {文件: 行数})。

    说明（对计划的一处修正）：计划用 `git diff --numstat main...HEAD` 量规模，
    但文件清单来自 `git status --porcelain`（未提交）。两者不一致，且当分支基点
    领先 main 时 main...HEAD 会把无关历史提交算进来 → 误判 fail-scale。headless
    编辑会话的产物本就是 worktree 里的未提交改动，故此处统一按未提交口径统计：
    已跟踪改动用 `git diff HEAD --numstat`，未跟踪新文件按行数补。
    TODO(Phase 2)：若约定 executor 会在 worktree 内提交，则需在派发时记录 base
    commit 并改用 `git diff <base>...HEAD` 统一 files+scale 口径。
    """
    # -uall：未跟踪目录逐个列文件（默认会把整棵目录折叠成一行 → deny/规模双失效）
    # core.quotepath=off：中文/非 ASCII 路径不八进制转义，否则 glob 必然不匹配
    _, out, _ = run(["git", "-c", "core.quotepath=off",
                     "status", "--porcelain", "-uall"], cwd=worktree)
    files: list[str] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        p = line[3:]
        if " -> " in p:  # 重命名取目标路径
            p = p.split(" -> ")[-1]
        files.append(p.strip().strip('"'))
    scale: dict[str, int] = {}
    _, out, _ = run(["git", "-c", "core.quotepath=off",
                     "diff", "HEAD", "--numstat"], cwd=worktree)
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            scale[parts[2]] = int(parts[0]) + int(parts[1])
    for f in files:
        if f not in scale and (worktree / f).is_file():
            try:
                scale[f] = len((worktree / f).read_text(
                    encoding="utf-8", errors="replace").splitlines())
            except OSError:
                scale[f] = 0
    return files, scale


def check_scope_and_scale(files: list[str], scale: dict[str, int],
                          card: dict) -> tuple[str, str]:
    if not files:
        # 零未提交变更：要么执行器什么都没改，要么在 worktree 内自行提交了 →
        # 轻门禁无法判定，交回重试/人工，绝不让"空 diff"混进 awaiting-review。
        return "fail-gate", "worktree 无任何未提交变更（可能已在 worktree 内提交，门禁无法判定）"
    allow = card["scope"]["allow_write"]
    deny = card["scope"]["deny_write"]
    for f in files:
        if any(glob_to_regex(d).match(f) for d in deny):
            return "fail-scope", f"触碰 deny_write：{f}"
        if not any(glob_to_regex(a).match(f) for a in allow):
            return "fail-scope", f"超出 allow_write：{f}"
    cons = card.get("constraints") or {}
    max_f = cons.get("max_files_changed", 300)
    max_l = cons.get("max_lines_changed", 300)
    if len(files) > max_f:
        return "fail-scale", f"文件数 {len(files)} > {max_f}"
    if sum(scale.values()) > max_l:
        return "fail-scale", f"变更行数 {sum(scale.values())} > {max_l}"
    return "pass", "scope+规模通过"


def reset_worktree(worktree: Path) -> None:
    """复位 worktree（只动 worktree，不碰主仓）：丢弃未提交改动。

    对「不存在 / 非目录」的目标是幂等 no-op，绝不抛异常：worktree 可能
    已被外部清理（人工删 / 上轮 GC 已回收），subprocess.run(cwd=缺失路径)
    抛 NotADirectoryError 会穿透回收链、阻塞 ownership 释放（TASK-054）。
    """
    if not worktree or not worktree.is_dir():
        return
    run(["git", "reset", "--hard"], cwd=worktree)
    run(["git", "clean", "-fd"], cwd=worktree)


def set_card_status(task_id: str, status: str) -> None:
    commit_card_status(ACTIVE_DIR / f"{task_id}.yaml", task_id, status, "poll 标")


def tail_stderr(run_dir: Path, n: int = 30) -> str:
    errf = run_dir / "stderr.log"
    if not errf.exists():
        return ""
    return "\n".join(errf.read_text(
        encoding="utf-8", errors="replace").splitlines()[-n:])


def _validate_card(card_path: Path) -> tuple[int, bool, str]:
    """跑 validate-task-card.py，返回 (退出码, 是否产出判定标记, 合并输出)。

    未产出 [OK]/[FAIL] 标记 = 校验器自身崩溃（缺 jsonschema / schema 缺失）
    = 环境故障，绝不能与"任务卡真非法"（fail-gate）混为一谈。
    """
    code, out, err = run(
        [sys.executable, str(SCRIPTS_DIR / "validate-task-card.py"),
         str(card_path)], cwd=REPO_ROOT)
    combined = f"{out}\n{err}"
    produced = ("[OK]" in combined) or ("[FAIL]" in combined)
    return code, produced, combined


def _preflight_env_ok(running) -> bool:
    """环境预检：校验器跑不起来就本轮中止，且在任何写操作之前退出（I2）。"""
    for rec in running:
        probe = ACTIVE_DIR / f"{rec['task_id']}.yaml"
        if probe.exists():
            _, produced, combined = _validate_card(probe)
            if not produced:
                print("[FAIL] 任务卡校验器环境异常（未产出判定标记），"
                      f"poll 本轮中止、不做任何写操作：{combined.strip()[:300]}")
                return False
            return True
    return True  # 无卡可探活，交给逐条处理


def _settle_upstream(rec: dict, cfg: dict, store: RunsStore,
                     detail: str, tail: str, code) -> None:
    """上游账本：不 append sig_history、不耗预算，打 upstream_fault。

    verdict 置 fail-exec 照常重试，不升级模型、不记病理。
    upstream_streak 连续计数：命中递增、达 UPSTREAM_MAX_CONSECUTIVE
    则标 blocked（reason 含“上游连续故障达上限”），防无限重试。
    """
    tid, attempt = rec["task_id"], rec["attempt"]
    verdict = "fail-exec"
    hist = list(rec.get("sig_history") or [])
    streak = int(rec.get("upstream_streak") or 0) + 1
    if streak >= UPSTREAM_MAX_CONSECUTIVE:
        set_card_status(tid, "blocked")
        store.update(tid, attempt, sig_history=hist, upstream_fault=True,
                     upstream_streak=streak, status="blocked",
                     verdict=verdict, exit_code=code)
        print(f"[WARN] {tid} 上游连续故障达上限（连续 {streak} 次），"
              "已标 blocked，等架构师处理")
        _own_release(store, tid, "upstream-exhausted")
        return
    store.update(tid, attempt, sig_history=hist, upstream_fault=True,
                 upstream_streak=streak)
    print(f"[INFO] {tid} 上游故障（不记病理、不耗预算），"
          f"verdict=fail-exec 照常重试")
    if store.budget_attempts(tid) < 1 + cfg["max_retries"]:
        card_path = ACTIVE_DIR / f"{tid}.yaml"
        reset_worktree(Path(rec["worktree"]))
        limit = cfg.get("prompt_budget", {}).get(
            "failure_note_max_chars", 2000)
        note = cap_text(f"{detail}\n{tail}".strip(), limit)
        try:
            spawn_attempt(tid, load_card(card_path), cfg, store, note,
                          model_override=None)
        except Exception as exc:  # noqa: BLE001  重派失败转人工
            set_card_status(tid, "blocked")
            store.update(tid, attempt, status="error", verdict=verdict,
                         exit_code=code, sig_history=hist,
                         upstream_fault=True, upstream_streak=streak)
            print(f"[WARN] {tid} 上游故障重派失败，已标 blocked 交人工：{exc}")
            _own_release(store, tid, "upstream-respawn-failed")
            return
        store.update(tid, attempt, status="retrying", verdict=verdict,
                     exit_code=code, sig_history=hist, upstream_fault=True,
                     upstream_streak=streak)
        try:
            new_attempt = store.attempts(tid)
            store.update(tid, new_attempt, upstream_streak=streak)
        except KeyError:
            pass
        print(f"[INFO] {tid} 上游故障已复位 worktree 并重派新 attempt"
              f"（不升级模型）")
    else:
        set_card_status(tid, "blocked")
        store.update(tid, attempt, status="blocked", verdict=verdict,
                     exit_code=code, sig_history=hist, upstream_fault=True,
                     upstream_streak=streak)
        print(f"[WARN] {tid} 上游故障但预算耗尽，已标 blocked，等架构师处理")
        _own_release(store, tid, "upstream-budget-exhausted")


def _settle(rec: dict, cfg: dict, store: RunsStore,
            verdict: str, detail: str, code) -> None:
    tid, attempt = rec["task_id"], rec["attempt"]
    if verdict == "pass":
        store.update(tid, attempt, status="awaiting-review",
                     verdict="pass", exit_code=code, upstream_streak=0)
        print(f"[OK] {tid} 通过机器门禁 → awaiting-review，"
              "等人类 verify-all.py 验收（poll 不写 done）")
        _own_release(store, tid, "awaiting-review")
        return
    card_path = ACTIVE_DIR / f"{tid}.yaml"
    tail = tail_stderr(Path(rec["run_dir"]))
    if is_upstream_fault(tail):
        _settle_upstream(rec, cfg, store, detail, tail, code)
        return
    sig = sig_of(verdict, code, tail)
    hist = ((rec.get("sig_history") or []) + [sig])[-SIG_HISTORY_KEEP:]
    store.update(tid, attempt, sig_history=hist, upstream_streak=0)
    if store.budget_attempts(tid) < 1 + cfg["max_retries"]:
        decision = plan_retry(hist, store.budget_attempts(tid),
                              1 + cfg["max_retries"],
                              cfg.get("model_fallbacks") or [],
                              cfg.get("auto_fallback", True))
        hit = bool(decision.get("model_fallback_hit"))
        if decision.get("action") == "blocked_early":
            set_card_status(tid, "blocked")
            store.update(tid, attempt, status="blocked", verdict=verdict,
                         exit_code=code, sig_history=hist,
                         model_fallback_hit=hit, upstream_streak=0)
            print(f"[WARN] {tid} {decision.get('reason')}，已标 blocked，等架构师处理")
            _own_release(store, tid, "blocked-early")
            return
        reset_worktree(Path(rec["worktree"]))
        prefix = decision.get("note_prefix") or ""
        if prefix:
            raw_note = f"{prefix}\n{detail}\n{tail}".strip()
        else:
            raw_note = f"{detail}\n{tail}".strip()
        limit = cfg.get("prompt_budget", {}).get(
            "failure_note_max_chars", 2000)
        note = cap_text(raw_note, limit)
        # 先 spawn 成功、再落 retrying：避免 "retrying 却无后继 running" 的孤儿态
        try:
            spawn_attempt(tid, load_card(card_path), cfg, store, note,
                          model_override=decision.get("model_override"))
        except Exception as exc:  # noqa: BLE001  重派失败不能把卡留成 in-progress 孤儿
            # poll 只看 running、dispatch 只重派 ready → 必须标 blocked 进人工可见队列
            set_card_status(tid, "blocked")
            store.update(tid, attempt, status="error", verdict=verdict,
                         exit_code=code, sig_history=hist,
                         model_fallback_hit=hit, upstream_streak=0)
            print(f"[WARN] {tid} 重派失败，已标 blocked 交人工：{exc}")
            _own_release(store, tid, "respawn-failed")
            return
        store.update(tid, attempt, status="retrying", verdict=verdict,
                     exit_code=code, sig_history=hist,
                     model_fallback_hit=hit, upstream_streak=0)
        # TASK-054：spawn_attempt 用 store.append 默认 sig_history=[] 创建新
        # attempt；若不把累计 hist 种回去，下一轮 plan_retry 仍只见 tail=1，
        # retry_escalated（换模型）与 tail>=3 blocked_early 永不触发。
        try:
            new_attempt = store.attempts(tid)
            store.update(tid, new_attempt, sig_history=hist)
        except KeyError:
            pass
        print(f"[INFO] {tid} 判定 {verdict}，已复位 worktree 并重派新 attempt")
    else:
        set_card_status(tid, "blocked")
        store.update(tid, attempt, status="blocked", verdict=verdict,
                     exit_code=code, sig_history=hist, upstream_streak=0)
        print(f"[WARN] {tid} 超重试上限，已标 blocked，等架构师处理")
        _own_release(store, tid, "retries-exhausted")


def _handle_record(rec: dict, cfg: dict, store: RunsStore) -> None:
    tid, attempt = rec["task_id"], rec["attempt"]
    card_path = ACTIVE_DIR / f"{tid}.yaml"
    try:
        _card = load_card(card_path)
    except OSError:
        _card = {}
    if (_card or {}).get("pipeline"):
        print(f"[SKIP] {tid} 已转管线，poll 跳过（由 pipeline 回收）",
              flush=True)
        return
    run_dir = Path(rec["run_dir"])
    if pid_alive(rec["pid"]):
        print(f"[INFO] {tid} attempt-{attempt} 仍在跑 pid={rec['pid']}")
        return
    code = read_exitcode(run_dir)
    if code is None or code != 0:
        verdict, detail = "fail-exec", f"exitcode={code}"
    else:
        gate_code, produced, combined = _validate_card(card_path)
        if not produced:
            raise RuntimeError(
                f"校验器环境故障（预检后仍异常）：{combined.strip()[:200]}")
        if gate_code != 0:
            verdict, detail = "fail-gate", "任务卡校验失败"
        else:
            # M4：仅在卡校验通过后才跑两次 git 算规模，fail-gate 不白做
            files, scale = worktree_changes(Path(rec["worktree"]))
            card = load_card(card_path)
            verdict, detail = check_scope_and_scale(files, scale, card)
            if verdict == "pass":
                for sk in card.get("skills") or []:
                    ok, detail2 = check_skill_evidence(sk, files, card)
                    if not ok:
                        verdict, detail = "fail-skill", detail2
                        break
    print(f"[INFO] {tid} attempt-{attempt} 判定 {verdict}：{detail}")
    with store.critical_section(timeout=300):
        _settle(rec, cfg, store, verdict, detail, code)


SPAWNING_STALE_SECONDS = 600  # 与协调锁 stale 同语义（v1.1 §11 复用）


def gc_stale_spawned(store, limit: int = SPAWNING_STALE_SECONDS) -> int:
    """spawning 滞留超 limit（落盘与拉起之间崩溃）→ 记 error 释放额度。

    v1.1 §11：不留永久占用；执行器进程若已拉起成功，其改动在 worktree
    未提交，复位重派会丢弃——由下一次派发复查（保守：不猜杀未知 pid）。
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    reaped = 0
    for r in store.list_active(owner=None):
        if r.get("status") != "spawning":
            continue
        try:
            age = (now - datetime.fromisoformat(
                r.get("started_at") or "")).total_seconds()
        except (ValueError, TypeError):
            age = limit + 1
        if age <= limit:
            continue
        try:
            store.update(r["task_id"], r["attempt"], status="error",
                         verdict="fail-exec",
                         note="stale spawning reclaimed (TASK-043)")
        except KeyError:
            continue
        print(f"[WARN] {r['task_id']} attempt-{r['attempt']} spawning "
              f"滞留超 {limit}s，已记 error 释放额度")
        reaped += 1
    return reaped


def _worktree_clean(wt: Path) -> bool:
    p = subprocess.run(["git", "-c", "core.quotepath=off", "status",
                        "--porcelain", "-uall"], cwd=str(wt),
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode != 0:
        return False
    return not (p.stdout or "").strip()


def gc_worktrees(cfg, store, root) -> int:
    """B1：任务终态（无 running/spawning）+ worktree 全清洁 → 回收。

    保守面：有账本记录才可回收（start-session 手工登记但无派发记录的
    目录不在本集合）；分支与提交不删（git worktree remove 只删目录）。
    """
    wt_root = Path(root) / cfg["worktree_root"]
    if not wt_root.is_dir():
        return 0
    recs = store._read_all()
    active = {r["task_id"] for r in recs
              if r.get("status") in ("running", "spawning")}
    known = {r.get("task_id") for r in recs}
    removed = 0
    for d in sorted(wt_root.iterdir()):
        if not d.is_dir():
            continue
        tid = d.name
        if tid in active or tid not in known:
            continue
        if not _worktree_clean(d):
            continue
        r = subprocess.run(["git", "worktree", "remove", str(d)],
                           cwd=str(root), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode == 0:
            print(f"[INFO] 回收 worktree（B1）：{tid}")
            removed += 1
        else:
            print(f"[WARN] worktree 回收失败 {tid}："
                  f"{(r.stderr or '').strip()[:120]}")
    return removed


def main() -> int:
    cfg = load_config()
    runs_dir = REPO_ROOT / cfg["runs_dir"]
    store = RunsStore(runs_dir / "RUNS.jsonl", lock_dir=runs_dir)
    # 崩溃恢复（先于回收/派发，无 running 时也要跑）
    try:
        with store.critical_section(timeout=300):
            gc_stale_spawned(store)
            gc_worktrees(cfg, store, REPO_ROOT)
    except TimeoutError as exc:
        print(f"[WARN] GC 本轮跳过（协调锁争用）：{exc}")
    running = store.list_running(owner="dispatch")
    print(f"[INFO] running 记录 {len(running)} 条")
    if not running:
        return 0
    if not _preflight_env_ok(running):
        return 2
    for rec in running:
        try:
            _handle_record(rec, cfg, store)
        except Exception as exc:  # noqa: BLE001  单条隔离，坏记录不崩整轮
            print(f"[FAIL] {rec['task_id']} 回收异常，记 error 并跳过："
                  f"{type(exc).__name__}: {exc}")
            try:
                store.update(rec["task_id"], rec["attempt"],
                             status="error", verdict="fail-gate")
            except KeyError:
                pass
    # TASK-044/047：全局 swap 的收尾恢复链已退役（ADR-008）——
    # 会话覆盖下全局文件从未被写入，无现场可恢复。
    return 0


if __name__ == "__main__":
    sys.exit(main())
