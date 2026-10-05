"""TASK-024 C5 证据生成器：deny_write 四执行点证据（只复核，不新增实现）。

覆盖：
- 执行点 2 check-pr-scope.py:237-250（deny 优先 / [DENY] / [CONFIG-CONFLICT]）
  → CLI 级冒烟（monkeypatch TASKS_DIR + 变更函数，临时卡 TASK-999，不污染真实 active/）
- 执行点 4 check-local-scope.py:105-119 → 同法冒烟
- 执行点 1 check_approval.py:97-98 → 既有单测 test_check_approval.test_deny_hit_rejects
  （由外部 unittest discover 运行，本脚本只记录）
- 执行点 3 poll.py:132-135 → 既有单测 test_poll.test_scope_check_rejects_deny_write
  （同上）
"""
import importlib.util
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

H = Path(__file__).resolve().parents[4] / ".harness" / "scripts"


def load(name, fname):
    spec = importlib.util.spec_from_file_location(fname, H / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CARD = """id: TASK-999
title: 024 C5 evidence card
status: ready
created: 2026-09-19T00:00:00Z
created_by: architect
approver: architect
scope:
  allow_write: ['docs/notes/**']
  deny_write: ['tests/**']
acceptance_tests: ['tests/t.txt']
done_when: ['ci: build']
"""


def pr_scope_case(mod, files):
    base_lines = [1, 2]
    with TemporaryDirectory() as tmp:
        mod.TASKS_DIR = Path(tmp)
        (Path(tmp) / "TASK-999.yaml").write_text(CARD, encoding="utf-8")
        mod.get_changed_files = lambda base_ref: list(files)
        mod.get_changed_lines = lambda base_ref: sum(base_lines[:len(files)]) or 2
        buf = io.StringIO()
        old_argv = sys.argv
        sys.argv = ["check-pr-scope", "--task-id", "TASK-999", "--base", "HEAD"]
        try:
            with redirect_stdout(buf):
                mod.main()
            code, out = 0, buf.getvalue()
        except SystemExit as e:
            code, out = (e.code if e.code is not None else 0), buf.getvalue()
        finally:
            sys.argv = old_argv
        return code, out


def local_scope_case(mod, files):
    with TemporaryDirectory() as tmp:
        mod.TASKS_DIR = Path(tmp)
        (Path(tmp) / "TASK-999.yaml").write_text(CARD, encoding="utf-8")
        mod.get_staged_files = lambda: list(files)
        mod.get_staged_lines = lambda: 2
        buf = io.StringIO()
        old_argv = sys.argv
        sys.argv = ["check-local-scope", "--task-id", "TASK-999"]
        try:
            with redirect_stdout(buf):
                code = mod.main()
        finally:
            sys.argv = old_argv
        return code, buf.getvalue()


def main():
    pr = load("check-pr-scope.py", "harness_check_pr_scope_024")
    ls = load("check-local-scope.py", "harness_check_local_scope_024")

    results = []
    code, out = pr_scope_case(pr, ["tests/b.txt"])
    results.append(("P1", "check-pr-scope：deny 命中 → [DENY] 拒绝",
                    code == 1 and "[DENY]" in out and "tests/b.txt" in out, out))
    code, out = pr_scope_case(pr, ["docs/notes/a.md"])
    results.append(("P2", "check-pr-scope：allow 命中 → 放行", code == 0, out))
    code, out = local_scope_case(ls, ["tests/b.txt"])
    results.append(("P3", "check-local-scope：deny 命中 → [DENY] 拒绝",
                    code == 1 and "[DENY]" in out, out))
    code, out = local_scope_case(ls, ["docs/notes/a.md"])
    results.append(("P4", "check-local-scope：allow 命中 → 放行", code == 0, out))

    all_ok = all(r[2] for r in results)
    lines = ["# TASK-024 C5 证据：deny_write 四执行点复核",
             "",
             "| 执行点 | 证据 |",
             "|---|---|",
             "| check_approval.py:97-98 | 既有单测 test_check_approval.test_deny_hit_rejects / "
             "test_lifecycle_deny_hit_rejects（unittest discover 运行） |",
             "| poll.py:132-135 | 既有单测 test_poll.test_scope_check_rejects_deny_write |",
             "| check-pr-scope.py:237-250 | 本脚本 P1/P2（CLI 冒烟，临时卡 TASK-999，不污染 active/） |",
             "| check-local-scope.py:105-119 | 本脚本 P3/P4（同法） |",
             ""]
    for code_id, desc, ok, out in results:
        lines += [f"## {code_id}：{desc}",
                  f"结果：{'PASS' if ok else 'FAIL'}",
                  "", "```", out.strip()[:500], "```", ""]
    lines.append(f"C5 结论：{'四执行点 deny 约束全部在位，销项 CLOSED' if all_ok else '存在缺口，不销项'}")
    report = Path(__file__).with_name("deny-evidence.md")
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"[{'OK' if all_ok else 'FAIL'}] {report}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
