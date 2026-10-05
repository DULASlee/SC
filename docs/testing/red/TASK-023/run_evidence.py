"""TASK-023 red/green evidence generator: runs the real commit-msg hook
against a scratch git repo (hook + check_approval copied in), captures
R1/R2/G1/G2(lifecycle)/SKIP outcomes. Writes evidence.md next to itself.
Exit code 0 iff all expected outcomes hold.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]  # F:\JQKJ
HOOK = REPO / "docs" / "ai-workspace" / "hooks" / "commit-msg"
APPROVAL = REPO / "docs" / "ai-workspace" / "hooks" / "check_approval.py"

BASH_CANDIDATES = [
    r"C:\Program Files\Git\bin\bash.exe",
    r"C:\Program Files\Git\usr\bin\bash.exe",
]


def find_bash():
    for cand in BASH_CANDIDATES:
        if Path(cand).exists():
            return cand
    import shutil as _s
    p = _s.which("bash")
    if p:
        return p
    raise SystemExit("bash not found (need Git Bash for hook smoke)")


def sh(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", shell=True)


def git(args, cwd):
    r = sh(f'git {" ".join(args)}', cwd)
    assert r.returncode == 0, f"git {' '.join(args)} failed: {r.stderr}"
    return r.stdout.strip()


CARD_READY = """id: TASK-999
title: scratch hook test card
status: ready
created: 2026-09-19T00:00:00Z
created_by: architect
approver: architect
scope:
  allow_write:
    - .harness/tasks/active/TASK-999.yaml
  deny_write:
    - src/**
acceptance_tests: ['tests/t.txt']
done_when: ['ci: build']
"""


def run_hook(repo, msg, env_extra=None):
    import os
    msgfile = Path(repo) / ".msg"
    msgfile.write_text(msg + "\n", encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    if env_extra:
        env.update(env_extra)
    r = subprocess.run([find_bash(), str(HOOK), str(msgfile)],
                       cwd=repo, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    return r.returncode, out


def main():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        git(["init", "-q"], repo)
        git(["config", "user.email", "t@t"], repo)
        git(["config", "user.name", "t"], repo)
        docs = repo / "docs" / "ai-workspace" / "hooks"
        docs.mkdir(parents=True)
        shutil.copy(APPROVAL, docs / "check_approval.py")
        active = repo / ".harness" / "tasks" / "active"
        active.mkdir(parents=True)
        git(["add", "-A"], repo)
        git(["commit", "-q", "-m", "init"], repo)

        results = []

        # R1: conventional prefix no longer penetrates (E1 removed)
        rc, out = run_hook(repo, "chore: bump dependency")
        results.append(("R1", "conventional 前缀 + 无 TASK 引用 → 拒绝",
                       rc == 1 and "FAIL" in out, out))

        # R2: TASK reference present but protected path uncovered
        (active / "TASK-999.yaml").write_text("id: TASK-999\n", encoding="utf-8")
        git(["add", ".harness/tasks/active/TASK-999.yaml"], repo)
        rc, out = run_hook(repo, "TASK-999: add scratch card")
        results.append(("R2", "TASK 引用 + 保护路径无覆盖卡 → 拒绝",
                       rc == 1 and "FAIL" in out, out))

        # G1: covering card (ready + approver + self-allow) passes
        (active / "TASK-999.yaml").write_text(CARD_READY, encoding="utf-8")
        git(["add", ".harness/tasks/active/TASK-999.yaml"], repo)
        rc, out = run_hook(repo, "TASK-999: add scratch card")
        results.append(("G1", "覆盖卡（ready+approver+自覆盖）→ 放行",
                       rc == 0, out))

        # G2: self-lifecycle — done card covers its own file commit
        done_card = CARD_READY.replace("status: ready", "status: done")
        (active / "TASK-999.yaml").write_text(done_card, encoding="utf-8")
        git(["add", ".harness/tasks/active/TASK-999.yaml"], repo)
        rc, out = run_hook(repo, "TASK-999: pipeline accept done")
        results.append(("G2", "自生命周期：done 卡覆盖自身卡文件提交 → 放行",
                       rc == 0, out))

        # G3: SKIP_PROTECTED_CHECK=1 (architect channel) — path gate skipped
        (active / "TASK-999.yaml").write_text(CARD_READY, encoding="utf-8")
        (active / "TASK-888.yaml").write_text("id: TASK-888\n", encoding="utf-8")
        git(["add", ".harness/tasks/active/TASK-888.yaml"], repo)
        rc, out = run_hook(repo, "TASK-888: architect direct",
                           {"SKIP_PROTECTED_CHECK": "1"})
        results.append(("G3", "SKIP_PROTECTED_CHECK=1 跳过路径判定（TASK 引用仍在）",
                       rc == 0, out))
        # and SKIP does NOT skip the TASK-reference gate
        rc2, out2 = run_hook(repo, "chore: no task ref",
                             {"SKIP_PROTECTED_CHECK": "1"})
        results.append(("G3b", "SKIP 不跳 TASK 引用（最小特权）",
                       rc2 == 1, out2))

        all_ok = all(r[2] for r in results)
        lines = ["# TASK-023 红绿证据（commit-msg E1 移除 + 纯 path 判定）",
                 "",
                 "生成：临时 git 仓 + 真实 hook（docs/ai-workspace/hooks/commit-msg）",
                 "+ 真实 check_approval.py；staged 文件为 .harness/tasks/active/ 卡文件。",
                 ""]
        for code, desc, ok, out in results:
            lines.append(f"## {code}：{desc}")
            lines.append(f"期望 {'PASS' if ok else 'FAIL'} → 实际 "
                         f"{'PASS' if ok else 'FAIL'}")
            lines.append("")
            lines.append("```")
            lines.append(out[:600])
            lines.append("```")
            lines.append("")
        lines.append(f"总体：{'ALL PASS' if all_ok else 'REGRESSION'}")
        ev = Path(__file__).with_name("evidence.md")
        ev.write_text("\n".join(lines), encoding="utf-8")
        print(f"[{'OK' if all_ok else 'FAIL'}] {ev}")
        return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
