# superpowers — Origin & License（整集落地）

## 来源（已字节比对验证）

| 项 | 值 |
|---|---|
| 名称 | superpowers（整集 14 技能） |
| 唯一可信源（本地实体） | `C:\Users\admin\.claude\plugins\cache\superpowers-marketplace\superpowers\5.1.0\skills\` |
| 上游市场 | `~/.claude/plugins/cache/superpowers-marketplace`（Anthropic / superpowers marketplace） |
| 版本 | 5.1.0 |
| 落地方式 | 一次性从全局插件缓存复制到 `docs/ai-workspace/skills/superpowers/<skill>/`（铁律 14 唯一源） |
| License | **MIT**（完整文本已落地 `docs/ai-workspace/skills/superpowers/LICENSE`，Copyright (c) 2025 Jesse Vincent） |
| 集成日期 | 2026-09-19 |

## SHA256 清单（字节比对）

以下为落地前对全局源文件的 SHA256，供后续 `skills update` 时复验。

| 文件 | SHA256 |
|---|---|
| brainstorming/SKILL.md | `bba47904a7f6bbee3bf8a107ebbe84e65d392be683bbb898ded736b29e415f90` |
| dispatching-parallel-agents/SKILL.md | `76806091c7f923ba2596546b19cccd98a08e57a68745df77c3a7b998fe838e2b` |
| executing-plans/SKILL.md | `e2102f11631433939f162d383d769f8257d859d6639e0e14969cda3ef0a95eca` |
| finishing-a-development-branch/SKILL.md | `5c8d4b59aedb14c94e2f5d787a3265e858e8f53d4ceffe7ff1c15878a52b0e91` |
| receiving-code-review/SKILL.md | `c9382e92b8f32363566068ecfed19d3b2651eaf40d3942b24840f839dedfc406` |
| requesting-code-review/SKILL.md | `5a3a44a3667800e2dc836829c6b92fada51e6dc58ac144ec05fe59f47d6bcd84` |
| subagent-driven-development/SKILL.md | `905a2b9be59b734dbe166525ad31dcaaf712a75926135adee1f554557aba5744` |
| systematic-debugging/SKILL.md | `4999cb851360485eca5074e727bbdd62ef20549c5d5b01216fcbf5831badb473` |
| test-driven-development/SKILL.md | `7dee67b4af6bdccc7a914ca34533184d64592d0f5b23aeae631538168db14994` |
| using-git-worktrees/SKILL.md | `085a45ee3de432bdb2768011591d9a882cb6c759e2317f379226451c5618fe8e` |
| using-superpowers/SKILL.md | `316e29381219adf0cac62190c67aeabf427d6e6e5f2735541d502b3d339be7aa` |
| verification-before-completion/SKILL.md | `ea52d15aabaf72bc6b558efe2c126f161b53961090ddcd712000273bfe8c7b6c` |
| writing-plans/SKILL.md | `4fd4627d2c02367879c0307d7249270bed633317ff9be82e926a6d57bf5d331b` |
| writing-skills/SKILL.md | `38ba648975ae6ba512d6695676f146163db61a496b867f716f4bdfb0ee3aca3e` |

（附属参考文件如 prompt 模板、testing-anti-patterns、root-cause-tracing 等随技能目录一并落地，见各技能 SKILL.md 引用。）

## 设计要点

- **类型**：执行层方法论技能集（harness 执行纪律）
- **触发词**：写计划 / 执行任务 / TDD / 验证完成 / 调试 / 代码评审 / 分支收尾
- **核心原则**：证据先于声明、根因先于修复、子代理双阶段评审
- **与全局铁律关系**：强化 `engineering-iron-laws.md` Law 1–4（Verification is Completion / No Escalation）

## 维护建议

- 上游 superpowers marketplace 升级时，重新拉 `~/.claude/plugins/cache/.../superpowers/<newver>/skills/` 做 SHA256 比对
- 本目录实体一旦修改，须同步更新 SHA256 清单
- 不要在 `~/.claude` 全局缓存与本目录之间双向同步；本目录是项目唯一源
