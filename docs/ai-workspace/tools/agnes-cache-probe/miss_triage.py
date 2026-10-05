#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""DSH 会话 transcript 的逐请求缓存判读（离线，零成本）。

用法：
  python miss_triage.py --transcript <path>.jsonl [--block 256 --miss-floor 20000 --prefill 2244 --hit-ttft 21.9]

判据顺序（顺序错了就会得错误结论，v1-v3 与本轮各栽过一次）：
  0) 先确认 usage 字段语义：DSH 的 inputTokens 是**未缓存增量**，prompt = inputTokens + cacheReadTokens。
  1) 双判据：cacheRead 低 且 墙钟 TTFT 不低于 prompt/prefill 的下界 => 才是真 miss（防止把
     "缓存生效但 cached_tokens 未上报" 误判成 miss）。
  2) 游程检验：miss/hit 游程均值 ÷ i.i.d. 期望（(1-p)/p 与 p/(1-p)）> 1.4 才说明后端分配是慢变的；
     接近 1 且交替率高 => 轮询路由（另一类根因，处置完全不同）。
  3) 链式检验：命中步 cached(k) 与 prompt(k-1) 的失配率。~0.5% 说明端点缓存的是"上一条请求整段 prompt"，
     此时任何前部改写（压缩/prune/就地替换）都会击穿全段。
  4) 事件对齐：miss 段起点前 180s 内是否有 request/header / compaction/prune / agent/inbox/spliced /
     assistant/attempt；并与命中步同条件基线比较——只看命中率会得出因果幻觉。
  5) 成本三项分解：每步固定税（与规模无关，实测 r=-0.076）/ miss 重算 / 命中增量。
     没有这一步就无法说清"修好命中率的收益上界"，会许出做不到的承诺。
"""
import argparse, json, sys, statistics
from collections import Counter

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ap = argparse.ArgumentParser()
ap.add_argument('--transcript', required=True)
ap.add_argument('--block', type=int, default=256)
ap.add_argument('--miss-floor', type=int, default=20000)
ap.add_argument('--prefill', type=float, default=2244.0)
ap.add_argument('--hit-ttft', type=float, default=21.9)
A = ap.parse_args()

ev = []
for line in open(A.transcript, encoding='utf-8'):
    line = line.strip()
    if line:
        try:
            ev.append(json.loads(line))
        except Exception:
            pass
ev.sort(key=lambda e: e.get('seq') or 0)
t0 = min((e.get('time') or 0) for e in ev if e.get('time'))
types = Counter(e.get('type') for e in ev)
print('事件 %d；类型 %s' % (len(ev), dict(types.most_common(12))))

ss, R, HDR, EV = {}, [], [], []
for e in ev:
    d = e.get('data') or {}
    t = e.get('type')
    if t == 'step/start':
        ss[(d.get('turn'), d.get('step'))] = e.get('time')
    elif t == 'assistant/message':
        u = d.get('usage') or {}
        st = d.get('stream') or []
        first = next((c.get('time') for c in st if c.get('time')), None)
        s0 = ss.get((d.get('turn'), d.get('step')))
        R.append({'turn': d.get('turn'), 'step': d.get('step'), 'seq': e.get('seq'), 't': e.get('time'),
                  'in': u.get('inputTokens') or 0, 'cache': u.get('cacheReadTokens') or 0,
                  'out': u.get('outputTokens') or 0,
                  'ttft': (first - s0) / 1000.0 if first and s0 else None,
                  'dur': ((e.get('time') - s0) / 1000.0) if s0 else None})
    elif t in ('request/header', 'request/context'):
        HDR.append((t, e.get('time'), json.dumps(d, ensure_ascii=False, sort_keys=True)))
    elif t in ('assistant/attempt', 'llm/retry', 'llm/retry-started', 'compaction/prune',
               'todo/write', 'agent/inbox/spliced', 'turn/start', 'user/message'):
        EV.append((t, e.get('time')))
R.sort(key=lambda r: r['seq'])
for r in R:
    r['prompt'] = r['in'] + r['cache']
    r['lowmetric'] = r['cache'] < A.miss_floor
    r['cold'] = r['prompt'] / A.prefill
    r['miss'] = bool(r['lowmetric'] and (r['ttft'] is None or r['ttft'] >= max(30.0, 0.5 * r['cold'])))
print('请求 %d；按 cacheRead 判 miss %d；按双判据判 miss %d；差 %d 步=命中但 cached_tokens 未上报' % (
    len(R), sum(1 for r in R if r['lowmetric']), sum(1 for r in R if r['miss']),
    sum(1 for r in R if r['lowmetric']) - sum(1 for r in R if r['miss'])))
print('  block 粒度校验：cacheRead 为 %d 整数倍的步数 %d/%d' % (
    A.block, sum(1 for r in R if r['cache'] % A.block == 0), len(R)))

# ---- 游程 ----
seq = [('M' if r['miss'] else 'h') for r in R]
runs, cur, n = [], seq[0], 1
for a, b in zip(seq, seq[1:]):
    if a == b:
        n += 1
    else:
        runs.append((cur, n)); cur, n = b, 1
runs.append((cur, n))
p = sum(1 for r in R if r['miss']) / max(1, len(R))
mr = [k for s, k in runs if s == 'M']; hr = [k for s, k in runs if s == 'h']
print('\n=== 游程（慢变 vs 轮询）===')
print('  miss 游程 %s 均值 %.2f / i.i.d.期望 %.2f = %.2f×' % (
    sorted(mr), statistics.mean(mr) if mr else 0, (1 - p) / p if p < 1 else 0,
    (statistics.mean(mr) / ((1 - p) / p)) if mr and p < 1 else 0))
print('  hit  游程 %s 均值 %.2f / i.i.d.期望 %.2f = %.2f×' % (
    sorted(hr), statistics.mean(hr) if hr else 0, p / (1 - p) if p < 1 else 0,
    (statistics.mean(hr) / (p / (1 - p))) if hr and p < 1 else 0))
flip = sum(1 for a, b in zip(seq, seq[1:]) if a != b) / max(1, len(seq) - 1)
print('  翻转率 %.0f%% vs i.i.d. 期望 %.0f%% => %s' % (
    100 * flip, 100 * 2 * p * (1 - p),
    '慢变（存在后端状态，但需另找把手）' if flip < 0.8 * 2 * p * (1 - p) else '接近轮询路由'))

# ---- 链式 ----
d = [(b['cache'] - a['prompt']) / a['prompt'] for a, b in zip(R, R[1:])
     if not b['lowmetric'] and a['prompt'] > 50000]
print('\n=== 链式检验 (cached(k)-prompt(k-1))/prompt(k-1) ===')
if d:
    print('  n=%d 中位 %+.4f 均值 %+.4f => %s' % (
        len(d), statistics.median(d), statistics.mean(d),
        '命中=上一条请求整段 prompt（严格链式）' if abs(statistics.median(d)) < 0.02 else '非链式（缓存粒度或改写另有原因）'))

# ---- 事件对齐 ----
starts = [i for i in range(len(R)) if R[i]['miss'] and (i == 0 or not R[i - 1]['miss'])]
print('\n=== miss 段起点 %d 个 的事件对齐（前 180s）===' % len(starts))
def has(i, kinds, win=180.0):
    return any(t in kinds and 0 <= R[i]['t'] - ts <= win * 1000 for t, ts in EV)
for kinds, label in [({'assistant/attempt', 'llm/retry', 'llm/retry-started'}, 'retry/attempt'),
                     ({'request/header'}, 'header 世代切换'),
                     ({'compaction/prune'}, 'prune'),
                     ({'agent/inbox/spliced', 'turn/start'}, 'turn 起始/splice'),
                     ({'todo/write'}, 'todo/write')]:
    a = sum(1 for i in starts if has(i, kinds))
    base = [i for i in range(len(R)) if not R[i]['miss']]
    b = sum(1 for i in base if has(i, kinds))
    print('  %-16s miss 段起点 %2d/%-2d = %3.0f%%   命中步基线 %3.0f%%  => %s' % (
        label, a, len(starts), 100 * a / max(1, len(starts)), 100 * b / max(1, len(base)),
        '可疑（高于基线 1.5×以上）' if a / max(1, len(starts)) > 1.5 * (b / max(1, len(base))) else '无差别'))

# ---- header 世代 ----
if HDR:
    print('\n=== request header / context 世代 ===')
    import hashlib
    for t, ts, payload in HDR:
        print('  +%6ds %-16s sha1=%s len=%d  %s' % (
            int((ts - t0) / 1000), t, hashlib.sha1(payload.encode()).hexdigest()[:10], len(payload),
            payload[:90].replace('\n', '\\n')))
    hts = [ts for t, ts, _ in HDR if t == 'request/header']
    for gi in range(len(hts)):
        lo = hts[gi]; hi = hts[gi + 1] if gi + 1 < len(hts) else 1 << 62
        ch = [r for r in R if lo <= r['t'] < hi]
        if ch:
            print('  gen%d 步数 %2d miss率 %3.0f%% prompt 中位 %7d' % (
                gi, len(ch), 100 * sum(1 for r in ch if r['miss']) / len(ch),
                statistics.median([r['prompt'] for r in ch])))

# ---- 成本三项分解 ----
H = [r for r in R if r['ttft'] and not r['lowmetric']]
M = [r for r in R if r['ttft'] and r['miss']]
print('\n=== 成本三项分解（TTFT 合计 %.0fs）===' % sum(r['ttft'] for r in R if r['ttft']))
F = statistics.median([r['ttft'] for r in H]) if H else A.hit_ttft
fixed = len(R) * F
misscost = sum(min(r['ttft'] or 0, r['cold']) for r in M)
inc = sum((r['in'] or 0) / A.prefill for r in H)
tot = fixed + misscost + inc
print('  每步固定税 %d × %.1fs = %6.0fs (%4.1f%%)  <- 只有减步数/换端点能动' % (len(R), F, fixed, 100 * fixed / tot))
print('  miss 重算   %d 步         = %6.0fs (%4.1f%%)  <- 只能靠缩小 prompt（命中率不可控）' % (len(M), misscost, 100 * misscost / tot))
print('  命中增量    %d 步         = %6.0fs (%4.1f%%)' % (len(H), inc, 100 * inc / tot))
print('  => 修好命中率的收益上界 %.0fs；剩余 %.0fs 为端点固定税（微调模型权重也动不了）' % (
    tot - fixed, fixed))
if H:
    print('  固定税与规模无关的检验：r(uncached, TTFT)=%+.3f；'
          'uncached<1K 桶 TTFT 中位 %.1fs vs uncached>30K 桶 %.1fs' % (
        (lambda xs, ys: (sum((a - statistics.mean(xs)) * (b - statistics.mean(ys)) for a, b in zip(xs, ys)) /
         ((sum((a - statistics.mean(xs)) ** 2 for a in xs) * sum((b - statistics.mean(ys)) ** 2 for b in ys)) ** .5)))(
            [r['in'] for r in H], [r['ttft'] for r in H]),
        statistics.median([r['ttft'] for r in H if r['in'] < 1000] or [0]),
        statistics.median([r['ttft'] for r in H if r['in'] > 30000] or [0])))
dec = [(r['dur'] - r['ttft']) / r['out'] * 1000 for r in R if r['dur'] and r['ttft'] and (r['out'] or 0) > 30]
if dec:
    print('  解码速率中位 %.0f tok/s（官方榜单口径需另行核对）' % (1000 / statistics.median(dec)))
