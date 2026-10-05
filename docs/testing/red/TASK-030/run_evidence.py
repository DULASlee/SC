"""TASK-030 改后证据：三脚本输出 ASCII 归零 + 拦截仍触发（故意违规 3 项）。

判据（架构师钉死）：三份文件运行输出的可打印非 ASCII 字符集合为空；
故意违规必须证明拦截仍触发（改输出未改判定路径）。
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = Path(__file__).with_name("outcome.md")
TARGETS = [
    REPO / "docs" / "ai-workspace" / "hooks" / "pre-push",
    REPO / ".harness" / "scripts" / "validate-task-card.py",
    REPO / "scripts" / "check-contract-consistency.py",
]
OUTPUT_MARKERS = ("echo ", "print(", "info ", "warn ", "fail ", "ok ")


def find_bash() -> str:
    for cand in (r"C:\Program Files\Git\bin\bash.exe",
                 r"C:\Program Files\Git\usr\bin\bash.exe"):
        if Path(cand).exists():
            return cand
    raise SystemExit("Git Bash not found")


def run(cmd, env_extra=None):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    if env_extra:
        env.update(env_extra)
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    return r.returncode, (r.stdout + r.stderr).strip()


def literal_scan(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    for i, ln in enumerate(lines, 1):
        if any(m in ln for m in OUTPUT_MARKERS) and any(ord(c) > 0x7F for c in ln):
            out.append(f"L{i}: {ln.strip()[:100]}")
    return out


def main() -> int:
    results = []

    # P1 validate-task-card --all：绿路径 + ASCII
    code, out = run([sys.executable, ".harness/scripts/validate-task-card.py", "--all"])
    results.append(("P1", "validate-task-card --all 绿路径",
                    code == 0 and out.isascii(),
                    f"exit={code} ascii={out.isascii()}\n{out[-200:]}"))

    # P2 contract-consistency 绿路径 + ASCII
    code, out = run([sys.executable, "scripts/check-contract-consistency.py"])
    results.append(("P2", "check-contract-consistency 绿路径",
                    code == 0 and out.isascii(),
                    f"exit={code} ascii={out.isascii()}\n{out}"))

    # P3 pre-push：静态零非ASCII输出字面量 + 故意违规（stub dotnet）
    res3 = []
    for t in TARGETS:
        res3 += [f"{t.relative_to(REPO).as_posix()} {x}" for x in literal_scan(t)]
    with tempfile.TemporaryDirectory() as tmp:
        stubdir = Path(tmp) / "stub"
        stubdir.mkdir()
        s = stubdir / "dotnet"
        s.write_text("#!/bin/sh\necho 'stub: forced fail'\nexit 1\n", encoding="utf-8")
        s.chmod(0o755)
        code, out = run([find_bash(), ".githooks/pre-push", "origin"],
                        env_extra={"PATH": f"{stubdir}:" + os.environ["PATH"]})
        ok3 = (not res3) and code == 1 and "[FAIL]" in out and out.isascii()
        results.append(("P3", "pre-push 输出字面量零非ASCII + 故意违规仍拦截",
                        ok3,
                        f"residual_literals={res3 or 'none'} exit={code} ascii={out.isascii()}\n{out[:400]}"))

    # P4 故意违规：validate-task-card 坏卡
    with tempfile.TemporaryDirectory() as tmp:
        bad = Path(tmp) / "bad-card.yaml"
        bad.write_text("id: TASK-999\ntitle: bad card\nstatus: ready\n"
                       "created: 2026-09-19T00:00:00Z\ncreated_by: architect\n",
                       encoding="utf-8")
        code, out = run([sys.executable, ".harness/scripts/validate-task-card.py", str(bad)])
        results.append(("P4", "validate-task-card 坏卡仍拦截",
                        code == 1 and "[FAIL]" in out and out.isascii(),
                        f"exit={code}\n{out[:400]}"))

    # P5 故意违规：contract-consistency 注入非法 JSON（finally 删除，零受跟踪改动）
    inj = REPO / "contracts" / "schemas" / "zz-030-evidence.json"
    inj.write_text("{ broken json", encoding="utf-8")
    try:
        code, out = run([sys.executable, "scripts/check-contract-consistency.py"])
    finally:
        inj.unlink(missing_ok=True)
    results.append(("P5", "contract-consistency 注入非法 JSON 仍拦截",
                    code == 1 and "[FAIL]" in out and out.isascii(),
                    f"exit={code} (注入文件已删)\n{out[:400]}"))

    all_ok = all(r[2] for r in results)
    lines = ["# TASK-030 改后证据（ASCII 归零 + 拦截仍触发）", ""]
    for cid, desc, ok, out in results:
        lines += [f"## {cid}：{desc}", f"结果：{'PASS' if ok else 'FAIL'}", "",
                  "```", out, "```", ""]
    lines.append(f"总体：{'ALL PASS' if all_ok else 'REGRESSION'}")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"[{'OK' if all_ok else 'FAIL'}] {OUT}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
