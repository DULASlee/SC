#!/usr/bin/env python3
"""协调锁：跨进程 + 进程内可重入的临界区互斥（TASK-043, v1.1 P3）。

复用 modelswap.py / loop.py 已在 Windows 实战两次的 mkdir 锁模式
（原子 mkdir + 内写 pid + mtime stale 600s 二次确认打破），泛化为独立
协调锁，供全局账本的"读→检查→预留→写"复合操作当作单一临界区使用
（v1.1 §5.2 消除 check-then-act 窗口；§5.3 要求真跨进程、不依赖 worktree 文件）。

与旧锁的分工：
- loop.lock  —— 只保证"同一时刻一个常驻 loop"（单实例）。
- coord.lock —— 保证账本/额度/claim 的复合写原子性，dispatch/poll/pipeline
  手工并发时也互斥（本卡新语义；旧版靠"同一时刻只跑其一"的约定）。
- modelswap.lock —— 全局配置切换（P4 退役，本卡不动）。

进程内可重入：同线程按 path 计数嵌套（context manager 复合块内再调用
带锁的 store 写方法不会自锁死）；不同线程各自走跨进程 mkdir 争用。
异常/崩溃恢复：持锁进程死亡后锁目录 mtime 超 600s 视为 stale，由后来者
二次确认打破（与 modelswap 同序，不永久锁死）。
"""
from __future__ import annotations

import os
import shutil
import threading
import time
from pathlib import Path
from contextlib import contextmanager

LOCK_NAME = "coord.lock"
STALE_SECONDS = 600
_ACQUIRE_POLL = 0.05

# 进程内重入：threading.local 记录本线程已持有的 (lock_path -> depth)。
_local = threading.local()


def _held() -> dict:
    h = getattr(_local, "held", None)
    if h is None:
        h = {}
        _local.held = h
    return h


def lock_dir_for(runs_dir) -> Path:
    return Path(runs_dir) / LOCK_NAME


def acquire(runs_dir, timeout: float = 120.0) -> Path:
    """获取协调锁；返回锁目录。超时抛 TimeoutError；stale 可打破。"""
    runs_dir = Path(runs_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)
    lock = lock_dir_for(runs_dir)
    held = _held()
    key = str(lock)
    if key in held:                     # 同线程重入：加计数，不再 mkdir
        held[key] += 1
        return lock
    deadline = time.monotonic() + timeout
    while True:
        try:
            lock.mkdir(exist_ok=False)
        except FileExistsError:
            _break_stale(lock, deadline, timeout)
            continue
        except OSError:
            _break_stale(lock, deadline, timeout)
            continue
        # 抢到：写 pid（诊断用；释放按路径重入计数，不依赖 pid）
        try:
            (lock / "pid").write_text(str(os.getpid()), encoding="utf-8")
        except OSError:
            pass
        held[key] = 1
        return lock


def _break_stale(lock: Path, deadline: float, timeout: float) -> None:
    """锁被占：mtime 超期二次确认后打破；否则判超时或轮询等待。"""
    try:
        age = time.time() - lock.stat().st_mtime
    except OSError:
        return  # 竞争中被删，回到循环重试
    if age > STALE_SECONDS:
        try:
            age2 = time.time() - lock.stat().st_mtime
        except OSError:
            return
        if age2 > STALE_SECONDS:
            try:
                shutil.rmtree(lock)
            except OSError:
                pass
            return
    if time.monotonic() >= deadline:
        raise TimeoutError(
            f"coord 锁超时：{lock}（timeout={timeout}s）")
    time.sleep(_ACQUIRE_POLL)


def release(runs_dir) -> None:
    """释放（重入计数归零才真删锁目录）。非本线程持有则忽略。"""
    lock = lock_dir_for(runs_dir)
    held = _held()
    key = str(lock)
    if key not in held:
        return
    held[key] -= 1
    if held[key] > 0:
        return
    del held[key]
    try:
        shutil.rmtree(lock)
    except FileNotFoundError:
        pass
    except OSError:
        pass


@contextmanager
def critical_section(runs_dir, timeout: float = 120.0):
    """with critical_section(runs_dir): 读→检查→写 的原子复合块。"""
    acquire(runs_dir, timeout)
    try:
        yield lock_dir_for(runs_dir)
    finally:
        release(runs_dir)


def is_held(runs_dir) -> bool:
    """本线程当前是否持有该协调锁（供 RunsStore 判断是否自锁）。"""
    return str(lock_dir_for(runs_dir)) in _held()


def touch(runs_dir) -> None:
    """持锁期间刷新锁目录 mtime，防止临界区耗时接近 STALE_SECONDS 被他人
    误判 stale 打破。仅当本线程持有时生效。"""
    if not is_held(runs_dir):
        return
    lock = lock_dir_for(runs_dir)
    try:
        os.utime(lock, None)
    except OSError:
        pass
