#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按模型审计「把执行推给人 / 找借口 / 半成品收工」三类行为。

为什么需要它：这三类是**主观印象最容易吵不出结果**的问题，但它们在会话事件日志里全部有字面痕迹，
可以按模型算出频率，从而把"MiniMax 老是甩锅"变成"每 100 步甩锅 N 次"的可比较指标。

数据来源：`~/.dsh/sessions/<cwd>/<session>/session*.jsonl[.zstd]`
  - `assistant/message` → data.message.source.{model,provider} 做逐条模型归因（一次会话可能切过多个模型）
  - content 里 `type=='text'` 是**给人看的正文**（只扫这个，避免把代码/注释/reasoning 当成承诺）
  - `tool/call` → 判定它是否自己执行了命令、是否跑过验证类命令

四类指标（都按模型分别算，per 100 步）：
  OFFLOAD  让人去运行/贴输出（真正的甩锅）
  EXCUSE   声称无法执行/受限于环境（找借口的字面特征）
  DONE     声称完成/通过
  VERIFY   自己跑过验证命令（pytest/test/verify/exit code 等）
  → 关键派生指标 **空头完成率 = DONE 且该步之前没有任何 VERIFY 的次数 / DONE 次数**：
     这是"半成品收工 + 找借口"的可证伪定义，比"感觉它在糊弄"精确得多。
"""
import argparse, glob, json, os, re, sys
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
from compression import zstd

OFFLOAD = [
    r'请(你|您)?(在)?(你的)?(终端|本机|命令行|shell|PowerShell|cmd|控制台)',
    r'请(你|您)?(手动)?(运行|执行|跑)(一下|这个|这些|下列|以下)?',
    r'(运行|执行)(后|完|之后).{0,12}(把|将|发|贴|反馈)',
    r'把(输出|结果|报错|日志|返回|截图)(贴|发|给)(给)?我?',
    r'(帮我|你来|你去|麻烦你).{0,6}(运行|执行|跑|调试)',
    r'需要(你|用户|人工)(手动)?(运行|执行|提供|确认输出)',
    r'(告诉我|反馈)(一下)?(它的|命令的)?(输出|报错|结果)',
    r'(?i)\b(please|can you|could you)\s+(run|execute|paste)\b',
    r'(?i)\brun (this|these|the) (command|script|following)\b',
    r'(?i)\bpaste the (output|result|error)\b',
    r'(?i)share the (output|logs?) with me',
]
EXCUSE = [
    r'(无法|不能|没办法|没法)(在|直接|自己)?(我的)?(环境|沙箱|这里|本地)?(中)?(执行|运行|验证|测试|访问|调用|安装)',
    r'受限于(我的|当前|环境)',
    r'由于(权限|沙箱|环境|网络)(限制|所限|的原因)?，?(我)?(无法|不能|没法)',
    r'(没有|缺少|不具备)(执行|运行|网络|shell|命令行)(能力|权限|条件)',
    r'我(这边|这里|当前)(的)?环境(没有|不支持|无法)',
    r'(?i)\b(I (cannot|can\'?t|am unable to|\'m unable to)|unable to (run|execute|verify|access))',
    r'(?i)\bnot available in my (environment|sandbox)',
]
DONE = [
    r'(已|全部|都)(经)?(完成|通过|修好|实现|解决|交付|搞定|验证通过)',
    r'(任务|测试|用例|门禁).{0,6}(全部|都|已)(通过|绿|pass)',
    r'(?i)\b(done|all tests pass|completed successfully|fixed|implemented)\b',
]
VERIFY_CMD = re.compile(r'(?i)(pytest|python\s+-m\s+unittest|\bnpm (test|run )|\.\\?(tests?|verify|run_)[\w.\\-]*|go test|cargo test|dotnet test|mvn test|gradlew|test-|_test|\.test\.|exit code|验证|自检|跑测试)')
SHELL_TOOLS = re.compile(r'(?i)^(pwsh|powershell|bash|sh|zsh|cmd|shell|terminal|command|run|exec|execute|docker|git|python)$')


def texts(msg):
    c = (msg or {}).get('content')
    out = []
    if isinstance(c, str):
        return [c]
    for b in (c or []):
        if isinstance(b, dict) and b.get('type') == 'text' and b.get('text'):
            out.append(b['text'])
    return out


def compile_all(pats):
    return [re.compile(p) for p in pats]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sessions', default=os.path.expanduser(r'~\.dsh\sessions'))
    ap.add_argument('--cwd', default='--F-JQKJ--', help='目录名片段；传 all 扫全部工作区')
    ap.add_argument('--samples', type=int, default=4, help='每模型每类打印几条原文')
    ap.add_argument('--min-steps', type=int, default=10)
    ap.add_argument('--json', default='')
    a = ap.parse_args()

    pat = {'offload': compile_all(OFFLOAD), 'excuse': compile_all(EXCUSE), 'done': compile_all(DONE)}
    S = defaultdict(lambda: {'steps': 0, 'user_turns': 0, 'calls': 0, 'shell': 0, 'verify': 0,
                             'offload': 0, 'excuse': 0, 'done': 0, 'hollow_done': 0,
                             'ctx_at_offload': [], 'offload_turn_pos': [], 'turn_of': [],
                             'samples': defaultdict(list)})
    files = glob.glob(os.path.join(a.sessions, '*', 'session-*', 'session*.jsonl*'))
    if a.cwd != 'all':
        files = [f for f in files if a.cwd.lower() in f.lower()]
    print('扫描 %d 个会话日志（cwd 过滤=%s）' % (len(files), a.cwd))
    for f in files:
        try:
            raw = open(f, 'rb').read()
            if f.endswith('.zstd'):
                raw = zstd.decompress(raw)
            ev = [json.loads(l) for l in raw.decode('utf-8', 'replace').splitlines() if l.strip()]
        except Exception as e:
            print('  [SKIP] %s: %r' % (os.path.basename(f), e))
            continue
        ev.sort(key=lambda e: e.get('seq') or 0)
        ver_seen = 0            # 本会话累计跑过的验证命令数
        turn_first_seq = {}
        nturn = 0
        for e in ev:
            t = e.get('type'); d = e.get('data') or {}
            if t == 'turn/start':
                nturn += 1
                turn_first_seq[d.get('turn')] = e.get('seq')
            elif t == 'tool/call':
                nm = str(d.get('name') or '')
                args = str(d.get('arguments') or '')[:4000]
                src = 'model'
                mkey = 'model'
                mdl = d.get('model') or 'unknown'
                if SHELL_TOOLS.match(nm) or 'pwsh' in nm or 'bash' in nm or 'command' in nm or nm in ('run_exec', 'job'):
                    S[mdl]['shell'] += 1
                    if VERIFY_CMD.search(args):
                        S[mdl]['verify'] += 1
                        ver_seen += 1
                S[mdl]['calls'] += 1
            elif t == 'assistant/message':
                msg = d.get('message') or {}
                srcobj = msg.get('source') or {}
                mdl = '%s/%s' % (srcobj.get('provider') or '?', srcobj.get('model') or '?')
                u = d.get('usage') or {}
                ctx = (u.get('inputTokens') or 0) + (u.get('cacheReadTokens') or 0)
                S[mdl]['steps'] += 1
                S[mdl]['turn_of'].append(d.get('turn') or 0)
                body = '\n'.join(texts(msg))
                for kind in ('offload', 'excuse', 'done'):
                    hit = next((rx for rx in pat[kind] if rx.search(body)), None)
                    if hit:
                        S[mdl][kind] += 1
                        if kind == 'offload':
                            S[mdl]['ctx_at_offload'].append(ctx)
                            S[mdl]['offload_turn_pos'].append((d.get('turn'), d.get('step')))
                        if len(S[mdl]['samples'][kind]) < a.samples:
                            frag = hit.search(body)
                            lo = max(0, frag.start() - 40); hi = min(len(body), frag.end() + 70)
                            S[mdl]['samples'][kind].append('turn%s/%s: …%s…' % (
                                d.get('turn'), d.get('step'), body[lo:hi].replace('\n', ' ')))
                        if kind == 'done' and ver_seen == 0:
                            S[mdl]['hollow_done'] += 1
    print('\n=== 按模型：每 100 步的行为频率（步数 < %d 的模型不列）===' % a.min_steps)
    hdr = '%-34s %5s %5s %6s %6s %6s %6s %6s %7s %7s %8s' % (
        '模型', '步数', '工具', 'shell', '验证', '甩锅', '借口', '收工', '甩锅/100', '空头%', '甩锅时ctx中位')
    print(hdr)
    rows = []
    for mdl, v in S.items():
        if v['steps'] < a.min_steps:
            continue
        per = lambda x: 100.0 * v[x] / v['steps']
        hollow = 100.0 * v['hollow_done'] / v['done'] if v['done'] else 0.0
        import statistics
        ctxm = statistics.median(v['ctx_at_offload']) if v['ctx_at_offload'] else 0
        rows.append((per('offload'), mdl, v, hollow, ctxm))
    rows.sort(reverse=True)
    for rate, mdl, v, hollow, ctxm in rows:
        print('%-34s %5d %5d %6d %6d %6.1f %6.1f %6.1f %7.1f %7.0f %8.0f' % (
            mdl[:34], v['steps'], v['calls'], v['shell'], v['verify'],
            rate, 100.0 * v['excuse'] / v['steps'], 100.0 * v['done'] / v['steps'],
            100.0 * v['offload'] / v['steps'], hollow, ctxm))
    print('\n=== 原文抽样（可逐条复核，避免正则误判当成结论）===')
    for rate, mdl, v, hollow, ctxm in rows:
        for kind in ('offload', 'excuse', 'done'):
            if v['samples'][kind]:
                print('  [%s] %s' % (mdl, kind.upper()))
                for s in v['samples'][kind]:
                    print('     - %s' % s[:168])
    if a.json:
        json.dump({m: {k: (v[k] if not isinstance(v[k], dict) else
                           {kk: vv for kk, vv in v[k].items()}) for k in v if k != 'turn_of'}
                   for m, v in S.items()}, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('\n明细写 %s' % a.json)


if __name__ == '__main__':
    main()
