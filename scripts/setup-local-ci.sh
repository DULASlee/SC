#!/bin/bash
# 一次性配置本地 CI（人类架构师运行）
# 架构师 §一 方案 1
set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# shellcheck disable=SC1091
. .githooks/lib/common.sh

echo "=== 配置本地 CI ==="

# 1. 让 git 使用仓库内 hooks
git config core.hooksPath .githooks
ok "core.hooksPath 设为 .githooks"

# 2. 赋予执行权限（Windows bash 需要这个）
chmod +x .githooks/pre-commit .githooks/pre-push .githooks/commit-msg
chmod +x .githooks/lib/common.sh
chmod +x scripts/setup-local-ci.sh
ok "hooks 执行权限已设置"

# 3. 验证 hooks 可执行
echo ""
info "hooks 状态："
for hook in .githooks/pre-commit .githooks/pre-push .githooks/commit-msg; do
    if [ -x "$hook" ]; then
        ok "$hook 可执行"
    else
        warn "$hook 不可执行（Windows Git Bash 下可能不需要 +x，但建议 chmod 一下）"
    fi
done

# 4. 创建裸仓库作为本地 remote（架构师 §一 方案 3）
BARE_REPO="../JQKJ-verify.git"
if [ ! -d "$BARE_REPO" ]; then
    git init --bare "$BARE_REPO" > /dev/null 2>&1
    ok "创建本地 bare 仓库：$BARE_REPO"
    git remote add local-verify "$BARE_REPO" 2>/dev/null || true
    ok "添加 remote: local-verify"
else
    info "bare 仓库已存在：$BARE_REPO"
    if ! git remote get-url local-verify > /dev/null 2>&1; then
        git remote add local-verify "$BARE_REPO" 2>/dev/null || true
        ok "添加 remote: local-verify"
    fi
fi

echo ""
echo "=== 配置完成 ==="
echo "使用方式："
echo "  1. 正常 git commit —— pre-commit + commit-msg 自动运行"
echo "  2. git push local-verify main —— pre-push 自动运行"
echo "  3. 人工验收：python .harness/scripts/verify-all.py --task-id TASK-XXX"
