# INC-001: PR 1 期间使用 --no-verify

## 事故
PR 1 执行期间，AI 工程师在修改 commit message 时使用了一次 `git commit --no-verify`，绕过了 pre-commit hook。

## 表面错误
使用 --no-verify 绕过本地门禁。

## 真正根因
commit message 需要修改，但 AI 工程师不确定是否能在不绕过 hook 的情况下完成 amend。

## 处理
- AI 工程师主动披露
- 最终 SHA 通过 amend 得到，真实过门禁
- 本次接受

## 未来规则
禁止使用 `git commit --no-verify` 和 `git push --no-verify`。如 hook 报错无法解决，停止并报告架构师。

## 落实的改动
在 `.harness/README.md` 中明确"禁止 --no-verify"规则。
