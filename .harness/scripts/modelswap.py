#!/usr/bin/env python3
"""DSH 模型真路由：settings.yaml 原子切换 + 跨进程互斥锁。

DSH 模型唯一来源是 ~/.dsh/settings.yaml 的 agent-default-model{provider,model}，
dsh --profile headless 本身无模型参数，故派发前必须先 swap，全部 running
结束后 maybe_restore 恢复现场。读写保留除 agent-default-model 外的所有键。
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

DEFAULT_SETTINGS = Path.home() / ".dsh" / "settings.yaml"

LOCK_NAME = "modelswap.lock"
STALE_SECONDS = 600
# 备份治理：备份不再污染 ~/.dsh/，统一落到 runs_dir 下该子目录
BAK_DIR_NAME = "modelswap-bak"
# 同名备份只保留最近 N 个（按 mtime 删旧）
BAK_KEEP = 5


def split_model(mid: str) -> tuple[str | None, str]:
    """"openrouter/a/b:free" -> ("openrouter", "a/b:free")；无斜杠返回 (None, mid)。"""
    if "/" in mid:
        provider, rest = mid.split("/", 1)
        return provider, rest
    return None, mid


def _read_doc(sp: Path) -> dict:
    sp = Path(sp)
    if not sp.exists():
        return {}
    with open(sp, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def _write_doc(sp: Path, doc: dict) -> None:
    """原子替换写回：先写 settings.yaml.tmp.<pid> + flush + fsync +
    os.replace，再删残留 tmp（replace 成功后 tmp 已消失，删是兜底）。"""
    sp = Path(sp)
    sp.parent.mkdir(parents=True, exist_ok=True)
    tmp = sp.with_name(f"{sp.name}.tmp.{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, sp)
    try:
        tmp.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def read_selection(sp: Path) -> tuple[str | None, str | None]:
    """读 DSH 现状：返回 (provider, model)，缺失则为 None。"""
    doc = _read_doc(sp)
    sel = doc.get("agent-default-model") or {}
    if not isinstance(sel, dict):
        return None, None
    return sel.get("provider"), sel.get("model")


def _lock_dir(runs_dir: Path) -> Path:
    return Path(runs_dir) / LOCK_NAME


def acquire_lock(runs_dir: Path, timeout: int = 120) -> Path:
    """原子 mkdir 锁目录 <runs_dir>/modelswap.lock（内写 pid 文件）。

    超时抛 TimeoutError；mtime 超 600 秒视为 stale 锁可打破。
    持锁区间仅毫秒级（读 + 备份 + 写），长运行不持锁，故打破 stale
    锁是安全的；打破前二次确认 mtime 仍超期，收窄 TOCTOU 窗口。
    """
    runs_dir = Path(runs_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)
    lock = _lock_dir(runs_dir)
    deadline = time.monotonic() + timeout
    while True:
        try:
            lock.mkdir(parents=False, exist_ok=False)
            with open(lock / "pid", "w", encoding="utf-8") as f:
                f.write(str(os.getpid()))
            return lock
        except OSError:
            # mkdir 竞争 / 锁已存在一律按“锁被占”处理（含 FileExistsError）。
            try:
                age = time.time() - lock.stat().st_mtime
            except OSError:
                continue  # 竞争中被删，重试
            if age > STALE_SECONDS:
                # 打破前二次确认 mtime 仍超期，避免“刚被新持有者创建”被误删
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
                    f"modelswap 锁超时：{lock}（timeout={timeout}s）")
            time.sleep(0.05)


def release_lock(runs_dir: Path) -> None:
    """仅当锁内 pid 与本进程一致才删，否则跳过并打印 [WARN]。"""
    lock = _lock_dir(runs_dir)
    if not lock.exists():
        return
    pid_file = lock / "pid"
    try:
        content = pid_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        # 无归属可验：宁可跳过也不误删别人的锁
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


def _bak_dir(sp: Path, runs_dir: Path | None) -> Path:
    """备份目录：runs_dir/modelswap-bak（不再污染 ~/.dsh/）。

    runs_dir 为空时回退到 settings 文件同目录（兼容老调用方）。
    """
    base = Path(runs_dir) if runs_dir is not None else Path(sp).parent
    d = base / BAK_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _prune_backups(d: Path, keep: int = BAK_KEEP) -> None:
    """同名备份只保留最近 keep 个（按 mtime 删旧）。"""
    try:
        files = sorted(d.glob("*.bak.*"),
                       key=lambda p: p.stat().st_mtime)
    except OSError:
        return
    for old in files[:-keep] if len(files) > keep else []:
        try:
            old.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            print(f"[WARN] 删旧备份失败：{old}：{exc}")


def swap_for_run(
    sp: Path, provider: str | None, model: str | None,
    runs_dir: Path | None = None,
) -> tuple[str | None, str | None] | None:
    """目标与现状一致则 noop 返回 None；否则备份后原子写回，
    返回 (prev_provider, prev_model)。"""
    sp = Path(sp)
    prev_provider, prev_model = read_selection(sp)
    if prev_provider == provider and prev_model == model:
        return None
    if sp.exists():
        d = _bak_dir(sp, runs_dir)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        bak = d / f"{sp.name}.bak.{ts}"
        bak.write_bytes(sp.read_bytes())
        _prune_backups(d)
    doc = _read_doc(sp)
    doc["agent-default-model"] = {"provider": provider, "model": model}
    _write_doc(sp, doc)
    return prev_provider, prev_model


def restore(sp: Path, provider: str | None, model: str | None) -> None:
    """写回指定值（保留其他键，原子替换；备份机制保留在 swap 侧）。"""
    sp = Path(sp)
    doc = _read_doc(sp)
    doc["agent-default-model"] = {"provider": provider, "model": model}
    _write_doc(sp, doc)


def snapshot(sp: Path, tag: str, dest_dir: Path) -> Path:
    """快照当前 settings 文件 → dest_dir/settings.snapshot.<tag>.<ts>.yaml。"""
    sp = Path(sp)
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = dest / f"settings.snapshot.{tag}.{ts}.yaml"
    if sp.exists():
        out.write_bytes(sp.read_bytes())
    else:
        _write_doc(out, _read_doc(sp))
    return out


def verify_selection(sp: Path, provider: str | None,
                     model: str | None) -> bool:
    """DSH 现状是否等于 (provider, model)。"""
    return read_selection(Path(sp)) == (provider, model)


def _store_label(store) -> str:
    """静默吞错告警用的文件标签：优先 store.path。"""
    return str(getattr(store, "path", store))


def _warn_store(store, exc: Exception) -> None:
    label = _store_label(store)
    msg = f"{type(exc).__name__}: {exc}"[:80]
    print(f"[WARN] {label}: {msg}", file=sys.stderr)


def _all_records(store) -> list[dict]:
    """全量记录查询（含 pipeline），失败只告警不改变返回语义。"""
    if hasattr(store, "_read_all"):
        try:
            return list(store._read_all())
        except Exception as exc:  # noqa: BLE001  历史兼容：读坏只告警，返回空
            _warn_store(store, exc)
    # 首选全量查询（owner=None 含 pipeline）
    try:
        return list(store.list_running(owner=None))
    except TypeError:
        # 老 store 无 owner 参数：无参即全量
        try:
            return list(store.list_running())
        except Exception as exc:  # noqa: BLE001  读坏只告警，返回空
            _warn_store(store, exc)
            return []
    except Exception as exc:  # noqa: BLE001  读坏只告警，回退逐 owner
        _warn_store(store, exc)
    recs: list[dict] = []
    for owner in ("dispatch", "pipeline"):
        try:
            recs.extend(store.list_running(owner=owner))
        except Exception as exc:  # noqa: BLE001  单 owner 坏只告警
            _warn_store(store, exc)
    return recs


def maybe_restore(sp: Path, store,
                  just_finished: list[dict] | None = None,
                  ) -> tuple[str | None, str | None] | None:
    """收尾恢复：只考虑调用方传入的“本轮刚收尾” swapped 记录，不掃全历史。

    若 store 中仍有 model_swapped 为真的 running 记录（全量，含 pipeline）
    则保持现状返回 None；否则取 just_finished 里最后一条含 prev_model 的
    记录恢复。prev_model 唯一合法形状是 [provider, model] 二元 list，
    否则跳过并 WARN。
    """
    try:
        try:
            running = store.list_running(owner=None)
        except TypeError:
            running = store.list_running()
    except Exception as exc:  # noqa: BLE001  读坏只告警，按无 running 处理
        _warn_store(store, exc)
        running = []
    for r in running or []:
        if isinstance(r, dict) and r.get("status") == "running" \
                and r.get("model_swapped"):
            return None
    cands = just_finished if just_finished is not None else []
    swapped = [r for r in cands
               if isinstance(r, dict) and r.get("model_swapped")
               and r.get("prev_model")]
    if not swapped:
        return None
    last = swapped[-1]
    prev = last.get("prev_model")
    if not (isinstance(prev, list) and len(prev) == 2):
        print(f"[WARN] prev_model 形状非法跳过恢复：{str(prev)[:80]}",
              file=sys.stderr)
        return None
    provider, model = prev[0], prev[1]
    restore(Path(sp), provider, model)
    return provider, model
