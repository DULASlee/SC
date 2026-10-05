#!/usr/bin/env python3
"""DSH 模型会话覆盖（TASK-044 机制 / TASK-047 完成旧链退役）。

现行模型（ADR-008）：基线 ~/.dsh/settings.yaml 全程只读；每 attempt 生成
私有设置副本（替换 agent-default-model、保留其余命名空间），spawn 经
`dsh --patch` 把组合树 settings 条目重定向到副本（watch: false）。
无全局写入 ⇒ 无锁、无备份、无恢复。

历史（本卡物理删除，可随时自 git 历史找回）：旧
"acquire_lock→swap_for_run(读+备份+改写全局)→跑→maybe_restore 恢复现场"
链——共享写入跨仓库/跨会话生效且带监视器热发布，经 ADR-008/010 废止。
保留件：split_model / _read_doc / _write_doc / DEFAULT_SETTINGS /
build_session_override。
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

DEFAULT_SETTINGS = Path.home() / ".dsh" / "settings.yaml"


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
    """原子替换写回：先写 <name>.tmp.<pid> + flush + fsync + os.replace。"""
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


def build_session_override(sp: Path, run_dir: Path,
                           provider: str, model: str) -> list[str]:
    """生成会话级模型覆盖的 spawn 附加参数（v1.1 §12 定案机制）。

    1) 基线文件 sp 只读载入（保留全部其他命名空间：provider 配置等）；
    2) agent-default-model 换成本任务 (provider, model)，原子写
       <run_dir>/settings.yaml（随 attempt 生灭，不污染他处）；
    3) 写 <run_dir>/model.patch.yml：把组合树 settings 条目 config.path
       指向副本并 watch: false（文件层值优先组合层——评审报告 §7 探针实证；
       关监视器防热发布）；
    4) 返回 ["--patch", <patch 绝对路径 posix>]，由 assemble_executor_argv
       注入在 {prompt} 之前（dsh 启动器参数须先于位置参数）。

    全程对基线文件零写入；无跨进程状态、无锁、无恢复。
    """
    sp = Path(sp)
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    doc = _read_doc(sp)
    doc["agent-default-model"] = {"provider": provider, "model": model}
    copy = (run_dir / "settings.yaml").resolve()
    _write_doc(copy, doc)
    patch = (run_dir / "model.patch.yml").resolve()
    patch.write_text(
        "- id: settings\n"
        "  config:\n"
        f"    path: {copy.as_posix()}\n"
        "    watch: false\n",
        encoding="utf-8")
    return ["--patch", patch.as_posix()]
