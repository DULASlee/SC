"""TASK-033 红灯证据 + 判据 5 故意违规测试（schema 失实 + 检测面缺口 分开修）。

判据 5（架构师钉死）：改完拦截逻辑必须证明拦截真会触发。
- 场景 A（幽灵字段：schema 未声明字段进 yaml）→ validate 必 FAIL
- 场景 B（approver 拼写幽灵值：枚举外字符串）→ validate 必 FAIL
- 场景 C（合法 approver=architect + 全字段合规）→ validate PASS
全部用临时文件（不进任何卡/暂存区）。
"""
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[4] / ".harness" / "scripts" / "validate-task-card.py"


def run_validate(card_text: str) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "ghost-card.yaml"
        p.write_text(card_text, encoding="utf-8")
        r = subprocess.run([sys.executable, str(SCRIPT), str(p)],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout + r.stderr).strip()


BASE_VALID = """id: TASK-999
title: 033 evidence card
status: ready
created: 2026-09-19T00:00:00Z
created_by: architect
scope:
  allow_write:
    - mod/a.txt
  deny_write:
    - src/**
acceptance_tests:
  - tests/GenCollector.Tests/LessonsIndexTests.cs
done_when:
  - "ci: build"
"""


def main() -> int:
    results = []

    # C：合法基线（无 approver，schema 未声明字段）→ 当前 schema 下应 PASS
    code, out = run_validate(BASE_VALID)
    results.append(("C", "合法基线（无 approver，全字段已声明）",
                    code == 0, f"exit={code}\n{out}"))

    # A：幽灵字段（schema 未声明）→ 必 FAIL
    code, out = run_validate(BASE_VALID + "ghost_field: should_be_rejected\n")
    results.append(("A", "幽灵字段（未声明）被拒",
                    code == 1 and "Additional properties" in out,
                    f"exit={code}\n{out}"))

    # B：approver 拼写幽灵值 → schema 声明 approver 为枚举[architect]后必 FAIL
    code, out = run_validate(BASE_VALID + "approver: Architec\n")
    results.append(("B", "approver 枚举外值被拒（需 033 修复 schema 后才可断言）",
                    code == 1 and ("Additional properties" in out or "not of type" in out or "architect" in out),
                    f"exit={code}\n{out}"))

    # A2：合法 approver=architect（033 修复 schema 后应 PASS；修复前为幽灵字段 FAIL）
    code, out = run_validate(BASE_VALID + "approver: architect\n")
    results.append(("A2", "approver=architect（033 修复 schema 后应 PASS）",
                    code == 0, f"exit={code}\n{out}"))

    all_ok = all(r[2] for r in results)
    lines = ["# TASK-033 判据 5 故意违规证据", ""]
    for cid, desc, ok, out in results:
        lines += [f"## {cid}：{desc}", f"结果：{'PASS' if ok else 'FAIL'}", "",
                  "```", out[:400], "```", ""]
    lines.append("说明：A=检测面闭环证明（幽灵字段被拒）；B/A2=approver 字段 schema 定义前后行为对照。")
    report = Path(__file__).with_name("criterion5.md")
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"[{'OK' if all_ok else 'FAIL'}] {report}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
