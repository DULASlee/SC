#!/usr/bin/env python3
"""常驻单实例循环（loop，只做调度，不做业务判定）。

用法：
  python .harness/scripts/loop.py [--once] [--max-cycles N] [--sleep S]
                                  [--stop-file PATH] [--max-tasks N]

行为：持 <runs_dir>/loop.lock 单实例锁循环，每轮顺序调
dispatch → pipeline → poll（单轮函数复用各脚本 main 语义，
本文件只做 subprocess 调度）。STOP 文件存在 / --once /
达 max_cycles / Ctrl+C 均正常退出（码 0），finally 释放锁。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

# Windows 控制台多为 GBK：dispatch/poll 输出含任意 Unicode 时直接 print
# 会 UnicodeEncodeError 崩掉常驻循环；stdout/stderr 统一切 utf-8/replace。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HARNESS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = HARNESS_DIR.parent
SCRIPTS_DIR = HARNESS_DIR / "scripts"


def _load_interval() -> tuple[int, Path]:
    """读 dispatch.yaml 取 (loop_interval_seconds, runs_dir 绝对路径)。"""
    with open(HARNESS_DIR / "dispatch.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    interval = cfg.get("loop_interval_seconds", 120)
    runs_dir = REPO_ROOT / cfg.get("runs_dir", ".harness/runs")
    return int(interval), Path(runs_dir)


STALE_SECONDS = 600


def acquire_singleton(runs_dir, timeout: float = 5) -> Path:
    """原子 mkdir 抢锁 <runs_dir>/loop.lock（内写 pid 文件），超时抛 TimeoutError。

    锁 mtime 超 600 秒视为 stale 可打破：二次确认仍超期则删锁重建
    （与协调锁 coord.py 同策略；历史上源自 modelswap.acquire_lock，
    该全局 swap 链已随 ADR-008 退役）。
    """
    runs_dir = Path(runs_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)
    lock = runs_dir / "loop.lock"
    deadline = time.monotonic() + timeout
    while True:
        try:
            lock.mkdir(parents=False, exist_ok=False)
            with open(lock / "pid", "w", encoding="utf-8") as f:
                f.write(str(os.getpid()))
            print(f"[LOOP] 已持有单实例锁：{lock}")
            return lock
        except OSError:
            # 锁已存在：先判 stale，再判超时（与 modelswap.py 同序）。
            try:
                age = time.time() - lock.stat().st_mtime
            except OSError:
                continue  # 竞争中被删，重试
            if age > STALE_SECONDS:
                # 打破前二次确认 mtime 仍超期，避免误删刚被新持有者创建的锁
                try:
                    age2 = time.time() - lock.stat().st_mtime
                except OSError:
                    continue
                if age2 <= STALE_SECONDS:
                    pass  # 已被新持有者刷新，转入正常等待
                else:
                    try:
                        shutil.rmtree(lock)
                    except OSError:
                        pass
                    continue
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"抢单实例锁超时（{timeout}s）：{lock} 已被持有")
            time.sleep(0.05)


def release_singleton(runs_dir) -> None:
    """释放单实例锁；仅当锁内 pid 属本进程才删，否则跳过并 WARN。

    锁缺失时忽略；锁内无 pid 文件时宁可跳过也不误删别人的锁。
    """
    lock = Path(runs_dir) / "loop.lock"
    if not lock.exists():
        return
    pid_file = lock / "pid"
    try:
        content = pid_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        print(f"[WARN] 锁无 pid 文件，跳过释放：{lock}")
        return
    except OSError as exc:
        print(f"[WARN] 读锁 pid 失败，跳过释放：{lock}：{exc}")
        return
    if content != str(os.getpid()):
        print(f"[WARN] 锁属 pid={content}，非本进程 {os.getpid()}，跳过释放：{lock}")
        return
    try:
        shutil.rmtree(lock)
    except FileNotFoundError:
        pass
    except OSError as exc:
        print(f"[WARN] 删锁失败：{lock}：{exc}")


def should_stop(stop_file: Path) -> bool:
    """STOP 文件存在即 True（常驻循环退出信号）。"""
    return Path(stop_file).exists()


def _loop_log_path() -> Path:
    """loop 落盘日志路径：<runs_dir>/loop.log（runs_dir 取 dispatch.yaml）。"""
    try:
        _, runs_dir = _load_interval()
    except Exception:
        runs_dir = HARNESS_DIR / "runs"
    return Path(runs_dir) / "loop.log"


def _append_loop_log(name: str, stdout: str, stderr: str, returncode: int) -> None:
    """完整 stdout/stderr append 落盘（每轮 UTC 时间戳头 + 脚本名分隔行）。"""
    try:
        log = _loop_log_path()
        log.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(log, "a", encoding="utf-8", errors="replace") as f:
            f.write(f"===== {ts} {name} exit={returncode} =====\n")
            f.write("--- stdout ---\n")
            f.write(stdout or "")
            if not (stdout or "").endswith("\n"):
                f.write("\n")
            f.write("--- stderr ---\n")
            f.write(stderr or "")
            if not (stderr or "").endswith("\n"):
                f.write("\n")
    except OSError as exc:
        print(f"[LOOP] 写 loop.log 失败：{exc}")


EXIT_NOTE = "[INFO] loop 退出；已派发的 dsh 任务继续运行，由下次 poll.py 回收（fire-and-forget 设计）"


def print_exit_note() -> None:
    """退出语义诚实化：Ctrl+C / STOP 退出前统一打印这一行。"""
    print(EXIT_NOTE)


def _run_script(name: str, args: list[str] | None = None) -> int:
    """subprocess 跑 SCRIPTS_DIR/name（cwd=仓库根，encoding utf-8）。

    完整 stdout/stderr append 到 <runs_dir>/loop.log（UTC 时间戳头 +
    脚本名分隔行）；终端只打印尾 2000 字符。返回退出码。
    注意：pipeline.py 在本任务内尚不存在（Task 5 落地），故此处允许
    subprocess 失败——返回码非零不抛错，只打印。当脚本缺失时
    （OSError / 解释器报文件不存在）同样只打印并返回非零码。
    """
    cmd = [sys.executable, str(SCRIPTS_DIR / name)] + list(args or [])
    try:
        p = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        out = p.stdout or ""
        err = p.stderr or ""
    except OSError as exc:  # 脚本缺失等执行期异常：不抛错，只打印
        print(f"[LOOP] {name} 执行异常：{exc}")
        _append_loop_log(name, "", f"执行异常：{exc}", 1)
        return 1
    _append_loop_log(name, out, err, p.returncode)
    print(f"[LOOP] {name} exit={p.returncode} out_tail={out[-2000:]}")
    if p.stderr:
        print(f"[LOOP] {name} err_tail={(p.stderr or '')[-2000:]}")
    return p.returncode


def run_dispatch(extra: list[str] | None = None) -> int:
    """跑 dispatch.py [+extra]，返回退出码（失败不抛错）。"""
    return _run_script("dispatch.py", extra)


def run_poll() -> int:
    """跑 poll.py，返回退出码（失败不抛错）。"""
    return _run_script("poll.py")


def _load_jsonl(path: Path) -> list[dict]:
    import json as _json
    recs = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    recs.append(_json.loads(line))
                except Exception:
                    continue
    except OSError:
        pass
    return recs


def _awaiting_tasks(runs_dir: Path) -> list[dict]:
    """返回每任务最新 attempt 状态为 awaiting-review 的记录。"""
    latest: dict[str, dict] = {}
    for name in ("RUNS.jsonl", "PIPELINE.jsonl"):
        for r in _load_jsonl(Path(runs_dir) / name):
            tid = r.get("task_id")
            if not tid:
                continue
            cur = latest.get(tid)
            if cur is None or r.get("attempt", 0) >= cur.get("attempt", 0):
                latest[tid] = r
    return [r for r in latest.values()
            if r.get("status") == "awaiting-review"]


def _card_of(task_id: str) -> dict:
    import yaml as _yaml
    for base in (HARNESS_DIR / "tasks" / "active",
                 REPO_ROOT / ".harness" / "tasks" / "active"):
        p = base / f"{task_id}.yaml"
        if p.is_file():
            try:
                return _yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            except Exception:
                return {}
    return {}


def _evidence_dir() -> Path:
    d = HARNESS_DIR / "evidence" / "auto"
    d.mkdir(parents=True, exist_ok=True)
    return d


def run_verify() -> int:
    """验收棒：为每单待审任务跑 verify-agent，产出 verdict 文件。"""
    try:
        _, runs_dir = _load_interval()
    except Exception as exc:
        print(f"[LOOP] verify 跳过（读配置失败）：{exc}")
        return 1
    tasks = _awaiting_tasks(Path(runs_dir))
    if not tasks:
        print("[LOOP] verify 无待审单，跳过")
        return 0
    ev = _evidence_dir()
    rc_all = 0
    for r in tasks:
        tid = r["task_id"]
        wt = r.get("worktree") or ""
        card = _card_of(tid)
        scope = (card.get("scope") or {})
        allow = scope.get("allow_write") or []
        crit = ev / f"criteria-{tid}.md"
        acc = card.get("acceptance_tests") or []
        done_when = card.get("done_when") or []
        crit.write_text("# " + tid + "\n\nacceptance:\n"
                        + "".join(f"- {a}\n" for a in acc)
                        + "\ngates:\n"
                        + "".join(f"- {g}\n" for g in done_when),
                        encoding="utf-8")
        verdict = ev / f"verdict-{tid}.md"
        cmd = [sys.executable, str(SCRIPTS_DIR / "verify-agent.py"),
               "--work", str(wt), "--criteria", str(crit),
               "--out", str(verdict)]
        for p in allow:
            cmd += ["--allow", str(p)]
        try:
            p = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True,
                               text=True, encoding="utf-8", errors="replace")
            print(f"[LOOP] verify {tid} exit={p.returncode} "
                  f"{(p.stdout or '').strip()[-200:]}")
            if p.returncode != 0:
                rc_all = p.returncode
        except OSError as exc:
            print(f"[LOOP] verify {tid} 执行异常：{exc}")
            rc_all = 1
    return rc_all


def _gh_repo() -> str:
    p = subprocess.run(["gh", "repo", "view", "--json", "nameWithOwner",
                        "-q", ".nameWithOwner"],
                       cwd=REPO_ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError("gh repo view 失败")
    return (p.stdout or "").strip()


def run_merge_sweep() -> int:
    """合入棒：枚举 feat/TASK-* 开放合请求，逐单调 merge-agent。"""
    import json as _json
    try:
        repo = _gh_repo()
    except Exception as exc:
        print(f"[LOOP] merge-sweep 跳过（{exc}）")
        return 1
    try:
        p = subprocess.run(
            ["gh", "pr", "list", "--state", "open", "--json",
             "number,headRefName", "--jq",
             ".[] | select(.headRefName | test(\"^feat/TASK-[0-9]+$\")) "
             "| .number"],
            cwd=REPO_ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        numbers = [n.strip() for n in (p.stdout or "").splitlines()
                   if n.strip()]
    except OSError as exc:
        print(f"[LOOP] merge-sweep 列单失败：{exc}")
        return 1
    if not numbers:
        print("[LOOP] merge-sweep 无候选单，跳过")
        return 0
    ev = _evidence_dir()
    rc_all = 0
    for n in numbers:
        vfile = ev / f"verdict-pr{n}.md"
        if not vfile.is_file():
            print(f"[LOOP] merge-sweep PR#{n} 无验收结论，转人工")
            rc_all = 2
            continue
        cmd = [sys.executable, str(SCRIPTS_DIR / "merge-agent.py"),
               "--pr", n, "--repo", repo, "--verdict", str(vfile),
               "--out", str(ev / f"merge-pr{n}.log")]
        try:
            q = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True,
                               text=True, encoding="utf-8", errors="replace")
            print(f"[LOOP] merge-sweep PR#{n} exit={q.returncode}")
            if q.returncode not in (0,):
                rc_all = q.returncode
        except OSError as exc:
            print(f"[LOOP] merge-sweep PR#{n} 执行异常：{exc}")
            rc_all = 1
    return rc_all


def _mark_done(task_id: str) -> bool:
    """把卡 status 改为 done 并单独提交（机器提交沿用占坑提交的
    路径限定与授权标记惯例，证据链在 verdict 文件中）。"""
    import re as _re
    for base in (HARNESS_DIR / "tasks" / "active",
                 REPO_ROOT / ".harness" / "tasks" / "active"):
        p = base / f"{task_id}.yaml"
        if p.is_file():
            card_path = p
            break
    else:
        print(f"[LOOP] closeout {task_id} 找不到活动卡")
        return False
    try:
        text = card_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[LOOP] closeout {task_id} 读卡失败：{exc}")
        return False
    new_text, n = _re.subn(r"^status:\s*\S+.*$", "status: done",
                           text, count=1, flags=_re.M)
    if n != 1:
        print(f"[LOOP] closeout {task_id} 未找到 status 行")
        return False
    try:
        card_path.write_text(new_text, encoding="utf-8")
    except OSError as exc:
        print(f"[LOOP] closeout {task_id} 写卡失败：{exc}")
        return False
    rel = card_path.relative_to(REPO_ROOT).as_posix()
    for args in (["git", "add", "--", rel],
                 ["git", "commit", "-m",
                  f"chore(harness): {task_id} autodrive accept done "
                  f"[APPROVED-BY: architect]", "--", rel]):
        q = subprocess.run(args, cwd=REPO_ROOT, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        if q.returncode != 0:
            print(f"[LOOP] closeout {task_id} 提交失败："
                  f"{(q.stderr or '').strip()[-200:]}")
            return False
    return True


def run_closeout() -> int:
    """归档棒：已合入的单标完成、归档、写汇报行。"""
    import json as _json
    try:
        repo = _gh_repo()
    except Exception as exc:
        print(f"[LOOP] closeout 跳过（{exc}）")
        return 1
    try:
        _, runs_dir = _load_interval()
    except Exception as exc:
        print(f"[LOOP] closeout 跳过（读配置失败）：{exc}")
        return 1
    tasks = _awaiting_tasks(Path(runs_dir))
    if not tasks:
        print("[LOOP] closeout 无待审单，跳过")
        return 0
    rc_all = 0
    for r in tasks:
        tid = r["task_id"]
        branch = r.get("branch") or f"feat/{tid}"
        try:
            p = subprocess.run(
                ["gh", "pr", "list", "--head", branch, "--state", "merged",
                 "--json", "number", "--jq", ".[0].number"],
                cwd=REPO_ROOT, capture_output=True, text=True,
                encoding="utf-8", errors="replace")
            num = (p.stdout or "").strip()
        except OSError as exc:
            print(f"[LOOP] closeout {tid} 查单失败：{exc}")
            rc_all = 1
            continue
        if not num or num == "null":
            continue
        vf = _evidence_dir() / f"verdict-{tid}.md"
        try:
            txt = vf.read_text(encoding="utf-8") if vf.is_file() else ""
        except OSError:
            txt = ""
        if "verdict: PASS" not in txt:
            print(f"[LOOP] closeout {tid} 无通过结论，转人工")
            rc_all = 2
            continue
        print(f"[LOOP] closeout {tid} PR#{num} 已合入，标完成并归档")
        if not _mark_done(tid):
            rc_all = 1
            continue
        q = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "archive-task.py"), tid],
            cwd=REPO_ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        # archive-task 只接受 done 态卡；先改卡状态再归档
        print(f"[LOOP] closeout {tid} archive exit={q.returncode}")
        if q.returncode != 0:
            rc_all = q.returncode
    return rc_all


def run_pipeline() -> int:
    """跑 pipeline.py，返回退出码（失败不抛错）。

    pipeline.py 本任务内不存在——允许 subprocess 失败（返回码非零
    不抛错，只打印），Task 5 会落地它。
    """
    return _run_script("pipeline.py")


def cycle(max_tasks=None, no_merge: bool = False) -> int:
    """一轮调度：顺序固定 dispatch → pipeline → poll → verify →
    merge-sweep → closeout。

    max_tasks 非 None 时透传 extra ["--max-tasks", str] 给 dispatch。
    no_merge 为真时跳过合入与归档（安全演练用）。
    返回首个非零退出码，全零则返回 0（各步恒全部执行，不短路）。
    """
    extra: list[str] = []
    if max_tasks is not None:
        extra = ["--max-tasks", str(max_tasks)]
    rc_d = run_dispatch(extra)
    rc_p = run_pipeline()
    rc_q = run_poll()
    rc_v = run_verify()
    if no_merge:
        print("[LOOP] --no-merge：跳过合入与归档")
        rcs = (rc_d, rc_p, rc_q, rc_v)
    else:
        rc_m = run_merge_sweep()
        rc_c = run_closeout()
        rcs = (rc_d, rc_p, rc_q, rc_v, rc_m, rc_c)
    for rc in rcs:
        if rc:
            return rc
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--max-cycles", type=int, default=None)
    ap.add_argument("--sleep", type=float, default=None)
    ap.add_argument("--stop-file", type=str, default=None)
    ap.add_argument("--max-tasks", type=int, default=None)
    ap.add_argument("--no-merge", action="store_true",
                    help="跳过合入与归档（安全演练用）")
    args = ap.parse_args()

    interval, runs_dir = _load_interval()
    sleep_s = args.sleep if args.sleep is not None else interval
    stop_file = Path(args.stop_file) if args.stop_file else runs_dir / "STOP"

    acquire_singleton(runs_dir)
    try:
        n = 0
        while True:
            if should_stop(stop_file):
                print(f"[LOOP] STOP 文件存在，退出：{stop_file}")
                print_exit_note()
                break
            n += 1
            print(f"[LOOP] cycle {n} 开始")
            cycle(args.max_tasks, args.no_merge)
            print(f"[LOOP] cycle {n} 结束")
            if args.once:
                print_exit_note()
                break
            if args.max_cycles is not None and n >= args.max_cycles:
                print_exit_note()
                break
            if should_stop(stop_file):
                print(f"[LOOP] STOP 文件存在，退出：{stop_file}")
                print_exit_note()
                break
            time.sleep(sleep_s)
    except KeyboardInterrupt:
        print("[LOOP] 收到 Ctrl+C，正常退出")
        print_exit_note()
    finally:
        release_singleton(runs_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
