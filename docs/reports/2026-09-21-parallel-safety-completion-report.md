# Parallel Safety Completion Report

- 工程：并行会话隔离与全局协调机制（施工契约 v1.1）
- 日期：2026-09-21
- 判定人：AI 施工会话（架构师临时全权授权）；**done 仍待人类验收**（本报告是 awaiting-review 证据，不是 done 声明）
- 载体分支：chore/reconcile-session-residue-0920（全部提交逐段可审，未合并）

## L0 Physical Isolation
**PASS**
Evidence: start-session 入口（worktree+branch+claim+context 一体，重复占用拒绝、
遗留 in-progress 拒旁路接管）；提交归属门禁实装（未领 worktree 拒、主树放行）；
substrate run V1/V2（docs/testing/red/PARALLEL-SAFETY/substrate-run-01.txt）；
test_start_session 5 例 + test_check_session_registration 6 例。

## L1 Global Ledger
**PASS（substrate）**
Evidence: 账本集中主树已核实并加锁——RunsStore(lock_dir) 写自保护 +
critical_section 复合块；并发 4 线程 append 40 行无丢失无撕裂；V3 并发抢
cap=2 恰 2 成功。

## L1 Concurrency Quota
**PASS（机制）/ PENDING（在线）**
Evidence: capacity_used 跨双账本合计（封堵"PIPELINE 不占额"实存超发口）+
spawning 计入（list_active）+ 逐卡单临界区消除 check-then-act；V3 实证。
在线派发面复测依赖模型行定案（见 PENDING）。

## L1 Cross-process Lock
**PASS**
Evidence: coord.py（mkdir+pid+600s-stale+二次确认+touch 心跳+进程内重入）；
跨进程争用真实子进程实证超时、强杀后 stale 恢复；test_coord 6 原语例 +
集成例。锁覆盖账本全部写路径含 append（B5 关闭）。

## L1 Model Override
**PASS（机制+离线实证）/ PENDING（dsh 消费在线面）**
Evidence: build_session_override（基线只读→per-attempt 副本→--patch 重定向
watch:false）；assemble 注入位序实证旧组装丢令牌（red-03）；V4 机制面三副本
互异 + 基线 SHA256 不变；dsh 端消费行为已由评审报告 §7 真实双探针先行验证
（成功用例 + 404 阴性对照 + 全局零写）。在线全链路（真派发双模型 + canary
真探针）待模型行定案。

## L2 Task Ownership
**PASS**
Evidence: ownership.py 单源（吸收 sessions/）；claim 冲突拒绝且原记录字节不变、
非 owner 写拒、释放仅 owner、读人人可；dispatch/poll(7 释放点)/pipeline
(advance 包装)/手工 CLI 四入口同构；V5/V6/V9 实证 + test_ownership 9 例。

## Crash Recovery
**PASS（substrate）**
Evidence: V7 kill→pid_alive False→GC 回收→slot 释放；stale spawning 600s 回收
（gc_stale_spawned）；清洁 worktree 回收（gc_worktrees，脏/未知/活跃不碰）；
锁 stale 二次确认恢复（测试实证）。

## Three-Worktree Real Run
**PASS（substrate 层）**
Evidence: verify-parallel.py 夹具上三真实 worktree/三 OS 进程并发跑 V1-V10，
11 断言全绿（substrate-run-01.txt, exit=0）。生产仓库真 dsh 会话三并发属
在线面，待模型行（见 PENDING），脚本 --out 参数可直接在生产重跑。

## Existing Regression
**PASS（python 面）/ PENDING（dotnet 派发全链路）**
Evidence: python 185/185 绿（基线 147→185，旧 147 零回归）；每段提交过
pre-commit 全套（含 dotnet build/契约/架构测试真跑，多次 [OK]）。
loop 常驻实跑回归 + canary 需模型行定案后执行。

## Modified Files
- 新增：.harness/scripts/{coord,ownership,start-session,verify-parallel}.py；
  docs/ai-workspace/hooks/check_session_registration.py；测试
  {coord,coord 集成入 test_coord,ownership}_*.py 等；ADR-006~010；
  本仓全部计划/评审/证据文档（逐笔见分支 git log）。
- 修改：runs.py（锁+list_active）、dispatch.py（临界区/容量/归属/会话覆盖）、
  poll.py（回收临界区/GC/释放点）、pipeline.py（锁/覆盖/归属）、
  modelswap.py（build_session_override 追加）、start-task.py 未动、
  .githooks/pre-commit（归属门禁步骤，主树锚点定位）。

## Explicitly Not Changed
MCP 协议、业务代码（src/tests/contracts）、前端、数据库、模型 provider 实现、
配置系统整体、任务系统语义（done 唯一来源仍是人类验收）、Git 策略（直推合并
权仍在人）、日志/持久化/部署/CI/安全体系。旧 modelswap swap 链与
test_gates 断言保留为过渡死代码（物理删除挂清理卡——见挂账）。

## Remaining Known Risks / PENDING（全部阻塞于同一个外部前置：架构师定
dispatch.yaml 模型行，随后按序执行）
1. canary 真探针留证（铁律 15，命令构造已变）→ 过则恢复 dispatch；
2. 在线 V4/V3/V7 + Gate F 全链路实跑（verify-parallel.py --out 生产复跑 +
   loop 数轮实跑）；
3. 退役清理卡：modelswap 死链 + poll.finalize + test_gates 同步改写；
4. 卡片体系遗留：21 张 ready/in-progress 卡使 check-local-scope 走
   "非唯一即跳过"旁路（P0 登记缺陷 C），ownership 门禁已实质接管提交面，
   但本地 scope 检查的"唯一活动卡"前提需独立设计卡；
5. 挂账：docs/ 下 109 个未入库 skills/hooks 文件、.harness/README 模型路由
   章节需按会话覆盖语义重写、ADR 目录双写矛盾（AGENTS.md vs 铁律 10）；
6. 主树当前分支停在 chore/reconcile-session-residue-0920（人回主树工作前
   注意切回；分支合并决策在架构师）。

**结论：PARALLEL-SAFETY = SUBSTRATE-CLOSED；LIVE-CLOSED 待 PENDING-1/2 完成
+ 人类 verify-all 验收。**
