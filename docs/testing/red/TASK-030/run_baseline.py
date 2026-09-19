"""TASK-030 baseline：改动前非 ASCII 分布扫描 + 三脚本运行输出捕获。

产出 baseline.md：
1. 三份目标文件逐行非 ASCII 定位（行号 + 是否输出语句 + 该行的可打印非 ASCII 字符集）
2. validate-task-card.py --all / 裸运行（print(__doc__)）真实运行输出捕获
3. check-contract-consistency.py 真实运行输出捕获
4. 预改「故意违规」证据：
   - validate-task-card：临时坏卡 → 期望 [FAIL] + exit 1
   - check-contract-consistency：临时注入非法 JSON（schemas/zz-030-evidence.json，
     用完即删，不触碰任何受跟踪文件）→ 期望 [FAIL] + exit 1
   - pre-push：dotnet stub 强制失败（PATH 注入，零仓库改动）→ 期望 [FAIL] + exit 1
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = Path(__file__).with_name("baseline.md")
TARGETS = [
    REPO / "docs" / "ai-workspace" / "hooks" / "pre-push",
    REPO / ".harness" / "scripts" / "validate-task-card.py",
    REPO / "scripts" / "check-contract-consistency.py",
]
OUTPUT_MARKERS = ("echo ", "print(", "info ", "warn ", "fail ", "ok ", "cat <<")


def non_ascii(line: str) -> list[str]:
    return sorted({c for c in line if ord(c) > 0x7F})


def scan_file(path: Path) -> list[str]:
    rel = path.relative_to(REPO).as_posix()
    lines = path.read_text(encoding="utf-8").splitlines()
    out = [f"### {rel}", ""]
    hits = 0
    for i, ln in enumerate(lines, 1):
        na = non_ascii(ln)
        if not na:
            continue
        kind = "输出" if any(m in ln for m in OUTPUT_MARKERS) else "注释/文档"
        out.append(f"- L{i} [{kind}] 非ASCII={na} :: {ln.strip()[:90]}")
        hits += 1
    out.append("")
    out.append(f"（该文件非 ASCII 行共 {hits} 行）")
    return out


def find_bash() -> str:
    for cand in (r"C:\Program Files\Git\bin\bash.exe",
                 r"C:\Program Files\Git\usr\bin\bash.exe"):
        if Path(cand).exists():
            return cand
    raise SystemExit("Git Bash not found")


def run(cmd, cwd=REPO, env_extra=None, shell=False):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"  # 固定捕获编码，避免 GBK/UTF-8 混杂干扰证据
    if env_extra:
        env.update(env_extra)
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", shell=shell, env=env)
    return r.returncode, (r.stdout + r.stderr).strip()


def main() -> int:
    parts = ["# TASK-030 baseline（改动前证据）", ""]

    for t in TARGETS:
        parts += scan_file(t) + [""]

    # 2/3. 真实运行捕获
    code, out = run([sys.executable, ".harness/scripts/validate-task-card.py", "--all"])
    parts += ["## run: validate-task-card.py --all（改前）", f"exit={code}", "```", out, "```", ""]
    code, out = run([sys.executable, ".harness/scripts/validate-task-card.py"])
    parts += ["## run: validate-task-card.py 裸运行（print(__doc__)，改前）", f"exit={code}", "```", out, "```", ""]
    code, out = run([sys.executable, "scripts/check-contract-consistency.py"])
    parts += ["## run: check-contract-consistency.py（改前）", f"exit={code}", "```", out, "```", ""]

    # 4. 故意违规（改前基线）
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)

        # 4a. validate-task-card：缺必填字段的坏卡
        bad = tmpdir / "bad-card.yaml"
        bad.write_text("id: TASK-999\ntitle: bad card\nstatus: ready\ncreated: 2026-09-19T00:00:00Z\ncreated_by: architect\n",
                       encoding="utf-8")
        code, out = run([sys.executable, ".harness/scripts/validate-task-card.py", str(bad)])
        parts += ["## 故意违规 a：validate-task-card 坏卡（改前）", f"exit={code}", "```", out, "```",
                  f"判定：拦截{'生效' if code == 1 else '失效'}", ""]

        # 4b. check-contract-consistency：注入非法 JSON（新文件，finally 删除，零受跟踪文件改动）
        inj = REPO / "contracts" / "schemas" / "zz-030-evidence.json"
        inj.write_text("{ broken json", encoding="utf-8")
        try:
            code, out = run([sys.executable, "scripts/check-contract-consistency.py"])
        finally:
            inj.unlink(missing_ok=True)
        parts += ["## 故意违规 b：check-contract-consistency 注入非法 JSON（改前）",
                  f"exit={code}（注入文件 zz-030-evidence.json 已删，git status 无残留）",
                  "```", out, "```",
                  f"判定：拦截{'生效' if code == 1 else '失效'}", ""]

        # 4c. pre-push：dotnet stub 强制失败（PATH 注入，零仓库改动）
        stubdir = tmpdir / "stub"
        stubdir.mkdir()
        stub = stubdir / "dotnet"
        stub.write_text("#!/bin/sh\necho 'stub: forced fail'\nexit 1\n", encoding="utf-8")
        stub.chmod(0o755)
        env_extra = {"PATH": f"{stubdir}:" + os.environ["PATH"]}
        code, out = run([find_bash(), ".githooks/pre-push", "origin"],
                        env_extra=env_extra)
        parts += ["## 故意违规 c：pre-push dotnet stub 强制失败（改前）",
                  f"exit={code}", "```", out[:800], "```",
                  f"判定：拦截{'生效' if code == 1 else '失效'}", ""]

    OUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"[OK] {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
