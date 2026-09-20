# agnes-cache-probe — 端点缓存行为取证工具

用于回答两类问题：**① 这个端点的前缀缓存到底生效没有；② 一次 DSH 会话的 TTFT 该拆成哪几项。**
零依赖（仅标准库），Windows 控制台已按铁律 3/4 处理编码。

## 文件

| 文件 | 作用 | 是否联网 |
|---|---|---|
| `cache_probe.py` | 在线探针：4 个 arm（句尾盐/句首盐/跨连接/大 payload）+ 双判据（计量 + 吞吐） | 是（产生真实请求） |
| `miss_triage.py` | 离线判读：DSH transcript 逐请求 → 双判据 miss、游程、链式、事件对齐、成本三项分解 | 否 |

## 用法

```powershell
# 1) 离线（先做这个，零成本）：transcript 由 .dsh/storages/.../session-<id>.json 解压得到
python docs/ai-workspace/tools/agnes-cache-probe/miss_triage.py --transcript <path>.jsonl

# 2) 在线探针：被测端点
python docs/ai-workspace/tools/agnes-cache-probe/cache_probe.py --host api.agnes-ai.cn --model agnes-3.0-flash --interval 20

# 3) 阳性对照（关键！没有对照就无法区分"端点不缓存"与"端点排队"）
python docs/ai-workspace/tools/agnes-cache-probe/cache_probe.py --host api.minimaxi.com --model MiniMax-M3 --anthropic --interval 20
```

API Key 从 `~/.dsh/.credentials.yaml` 按 `--key-env` 名读取，不落盘、不打印。

## 判读规则（本仓库已踩过的坑，按此顺序读）

0. **先读 `Q-queue` arm（排队税基线）**：1.7K token 的极小 payload 同连接复测三次。
   若这条 arm 就要 10–70s，说明端点处于**排队主导**状态，后面所有 hit/miss 判定都不可用——
   本工具初版缺这条 arm，结果把"1.8K 请求用 162s"误读成"缓存完全失效"，实为端点拥塞
   （实测 1.7K payload 的三次复测：70.9s / 10.4s / 57.9s，另有 2 次 `RemoteDisconnected`）。
1. **`cached_tokens` 不可单独作判据。** 实测 agnes 有 110K prompt 请求 30.8s 完成（3,639 tok/s，
   高于其自身冷启动回归速率）却报 `cached=0`；同 payload 的另一次复测用 214s。
   工具因此输出两列判定：`HIT/miss`（计量）与 `FAST/slow`（吞吐），合成
   `HIT / UNREPORTED-HIT? / MISS` 三种结论。
2. **异步写入**：warm 与 probe 间隔 `<5s` 必然双 miss（v1–v3 报告误判"无缓存"的原因）。`--interval` 不得小于 10。
3. **DSH usage 字段语义**：`inputTokens` 是**未缓存增量**，真实 prompt = `inputTokens + cacheReadTokens`。
   拿 `inputTokens` 当 prompt 会把成本算小一个数量级。
4. **游程判别根因方向**：`miss/hit 游程均值 ÷ i.i.d. 期望` > 1.4 为**慢变后端状态**（钉实例类问题）；
   接近 1 且翻转率高为**每请求轮询**。两者处置完全不同，别跳过这步。
5. **链式判别**：命中步 `cached(k)` 与 `prompt(k-1)` 的失配率 ~0.5% ⇒ 端点缓存的是"上一条请求整段 prompt"，
   此时任何前部改写（压缩/prune/就地替换）都会击穿全段；实测 `cacheRead` 恒为 **256 的整数倍**（分块粒度）。
6. **必须有阳性对照**：同协议打一次 MiniMax-M3（实测 warm 2.1s / probe 1.3s / `cache_read=24,470`）。
   没有对照，"全 miss"分不清是被测端点不缓存、还是排队、还是计量不上报。

## 实测结论速查（2026-09-20，详见 `docs/reports/2026-09-20-agnes-cache-hit-round2-and-finetune-scope.md`）

| 观测 | agnes-3.0-flash | MiniMax-M3（对照） |
|---|---|---|
| 同连接句尾盐复测（间隔 20s） | `cached=0`，但墙钟 58.5s→3.5s | `cache_read=24,470`，2.1s→1.3s |
| 110K payload | warm 214s / probe 30.8s，均报 `cached=0`；一次 >300s 超时 | — |
| 真实会话 100 步 | 计量口径 miss 41%；墙钟双判据 35% | — |
| 前置 | `Server: cloudflare`，`CF-RAY *-CZX`，单 A 记录（anycast） | — |
| 每步固定开销 | TTFT 中位 21.9–22.2s，且与新增 token 量无关（r=-0.076） | warm 2.1s |

## 已知局限

- `cache_probe.py` 只测 chat/completions 单消息形态，不含 `tools` 与多轮结构；测"工具块是否是唯一被缓存段"
  需另加带 `tools` 的 arm（v5 报告 §一.1 用离线数据已覆盖该点）。
- 吞吐判据依赖 `--prefill` 常量（默认 2,244 tok/s，取自 agnes miss 步回归），换端点须重估，否则会误报
  `UNREPORTED-HIT?`。
- 探针会真实消耗配额；agnes 现价 ¥0，MiniMax/doubao 请按定价评估。
