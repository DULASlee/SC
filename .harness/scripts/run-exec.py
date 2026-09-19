#!/usr/bin/env python3
"""执行包装器：跑一条 executor 命令，把 stdout/stderr/exitcode 落盘。

用法：
  python .harness/scripts/run-exec.py --run-dir <dir> -- <command...>

产出（run_dir 下）：
  stdout.log / stderr.log / exitcode.txt
父进程（dispatch.py）用 Popen 拉起本脚本即得 pid；poll.py 凭 pid 判活，
凭 exitcode.txt 判执行成败。自身退出码恒为 0（执行结果只看文件，避免
父进程把"包装器崩了"和"任务失败"混为一谈）。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _resolve_windows_cmd(cmd: list[str]) -> list[str]:
    """Windows 非 exe 命令经 cmd/pwsh 拉起。

    - os.name != "nt" 时原样返回。
    - 用 shutil.which(cmd[0]) 解析；解析到 .cmd/.bat 后缀（或解析不到
      但同名 .cmd/.bat 存在）则改走 [cmd.exe, /d, /c, <list2cmdline>]；
      .ps1 后缀则走 [pwsh.exe, -NoProfile, -NonInteractive, -Command,
      <list2cmdline>]；.exe / 无后缀可直拉的不变。
    - which 返回 None 且无对应垫片时原样返回，让 FileNotFoundError
      自然抛出（由调用方落盘），不吞异常。
    """
    if os.name != "nt":
        return cmd
    target: str | None = shutil.which(cmd[0])
    if target is None:
        # which 解析不到：试同名垫片（bare name 经 PATH，或带目录的显式路径）。
        for ext in (".cmd", ".bat", ".ps1"):
            cand = shutil.which(cmd[0] + ext)
            if cand:
                target = cand
                break
        if target is None:
            p = Path(cmd[0])
            if p.suffix == "" and p.parent != Path("."):
                # 显式路径缺后缀时，直接看文件系统上是否有同名垫片。
                for ext in (".cmd", ".bat", ".ps1"):
                    sibling = p.with_suffix(ext)
                    try:
                        if sibling.is_file():
                            target = str(sibling)
                            break
                    except OSError:
                        continue
        if target is None:
            return cmd
    low = target.lower()
    if low.endswith(".cmd") or low.endswith(".bat"):
        return ["cmd.exe", "/d", "/c", subprocess.list2cmdline(cmd)]
    if low.endswith(".ps1"):
        return ["pwsh.exe", "-NoProfile", "-NonInteractive",
                "-Command", subprocess.list2cmdline(cmd)]
    return cmd


def _write_result(run_dir: Path, out: str, err: str, rc: int) -> None:
    (run_dir / "stdout.log").write_text(out or "", encoding="utf-8")
    (run_dir / "stderr.log").write_text(err or "", encoding="utf-8")
    (run_dir / "exitcode.txt").write_text(str(rc), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("command", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    # 只剥掉分隔用的前导 --，保留命令内部合法的 -- 参数
    cmd = list(args.command)
    if cmd[:1] == ["--"]:
        cmd = cmd[1:]
    if not cmd:
        # 契约：包装器自身退出码恒为 0，任务失败只体现在 exitcode.txt（非 0）
        _write_result(run_dir, "", "run-exec: 缺少被执行的命令\n", -1)
        print("[FAIL] run-exec: 缺少被执行的命令", file=sys.stderr)
        return 0

    try:
        exec_cmd = _resolve_windows_cmd(cmd)
        proc = subprocess.run(
            exec_cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        out, err, rc = proc.stdout, proc.stderr, proc.returncode
    except OSError as exc:
        # 可执行文件缺失 / 无权限等：仍落盘并返回 0，让 poll 判 fail-exec
        out, err, rc = "", f"run-exec: {type(exc).__name__}: {exc}\n", -1

    _write_result(run_dir, out, err, rc)
    print(f"[OK] run-exec: exit={rc} cmd={cmd[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
