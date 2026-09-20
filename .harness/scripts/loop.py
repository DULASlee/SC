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


def run_pipeline() -> int:
    """跑 pipeline.py，返回退出码（失败不抛错）。

    pipeline.py 本任务内不存在——允许 subprocess 失败（返回码非零
    不抛错，只打印），Task 5 会落地它。
    """
    return _run_script("pipeline.py")


def cycle(max_tasks=None) -> int:
    """一轮调度：顺序固定 dispatch → pipeline → poll。

    max_tasks 非 None 时透传 extra ["--max-tasks", str] 给 dispatch。
    返回首个非零退出码，全零则返回 0（三步恒全部执行，不短路）。
    """
    extra: list[str] = []
    if max_tasks is not None:
        extra = ["--max-tasks", str(max_tasks)]
    rc_d = run_dispatch(extra)
    rc_p = run_pipeline()
    rc_q = run_poll()
    for rc in (rc_d, rc_p, rc_q):
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
            cycle(args.max_tasks)
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
