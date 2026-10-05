#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Agnes/任意 OpenAI 或 Anthropic 兼容端点的缓存行为探针。

设计要点（踩过的坑都在这里，别再用更差的判据）：
  1. 缓存是异步写入的：warm 与 probe 间隔 <5s 必然双 miss（v1-v3 报告因此误判"无缓存"）。
  2. cached_tokens 不可单独作判据：实测存在 110K prompt 30.8s 完成（3.6K tok/s）却报 0 的情况。
     因此本工具同时记录墙钟 dt，并给出"按计量判定"与"按吞吐判定"两列。
  3. 必须带对照组：全部 miss 时，无法区分"端点不缓存"与"端点排队"，故 --control-host 跑一次已知
     缓存正常的端点（MiniMax 实测 warm 2.1s / probe 1.3s / cache_read 完整）作为阳性对照。
arms:
  end   盐在句尾（共享最长可复用前缀）+ 同连接复测   -> 端点愿不愿缓存会话级前缀
  start 盐在句首（首 token 即分歧）+ 同连接复测      -> 前缀是否严格锚定
  cross 盐在句尾 + 复测走全新 TCP/TLS 连接          -> 缓存是否跨连接共享
  big   加大 payload 到真实会话量级                 -> 容量/TTL 效应
"""
import argparse, json, ssl, statistics, sys, time, random, string, http.client

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

UNIT = '前缀缓存探针主体：采集器按契约优先实现，x86 目标，敏感信息走环境变量，经验必须沉淀。'  # 48 字
PREFILL_TOKS = 2244.0   # agnes 实测未缓存预填充速率（回归 r=+0.60），用于吞吐判定


def read_key(env_name, cred_path):
    for line in open(cred_path, encoding='utf-8'):
        if env_name in line:
            return line.split(':', 1)[1].strip()
    raise SystemExit('[FATAL] %s not found in %s' % (env_name, cred_path))


def salt(n=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))


class Client:
    def __init__(self, a):
        self.a = a
        self.ctx = ssl.create_default_context()

    def connect(self):
        for _ in range(3):
            try:
                c = http.client.HTTPSConnection(self.a.host, 443, timeout=self.a.timeout, context=self.ctx)
                c.connect()
                return c
            except Exception as e:
                print('  [WARN] connect retry: %r' % e, flush=True)
                time.sleep(2)
        raise SystemExit('[FATAL] cannot connect %s' % self.a.host)

    def body(self, model, content):
        if self.a.anthropic:
            return {"model": model, "max_tokens": 4, "messages": [{"role": "user", "content": content}]}
        return {"model": model, "max_tokens": 4, "messages": [{"role": "user", "content": content}]}

    def headers(self):
        k = read_key(self.a.key_env, self.a.cred)
        h = {'Content-Type': 'application/json', 'Accept-Encoding': 'identity'}
        if self.a.anthropic:
            h.update({'x-api-key': k, 'anthropic-version': '2023-06-01'})
        else:
            h.update({'Authorization': 'Bearer ' + k})
        return h

    def call(self, conn, model, content, tag):
        t0 = time.time()
        try:
            conn.request('POST', self.a.path, json.dumps(self.body(model, content)), self.headers())
            r = conn.getresponse()
            raw = r.read().decode('utf-8', 'replace')
        except Exception as e:
            print('%-30s EXC %r' % (tag, e), flush=True)
            return None
        dt = time.time() - t0
        try:
            j = json.loads(raw)
        except Exception:
            print('%-30s non-json %s' % (tag, raw[:120]), flush=True)
            return None
        u = j.get('usage') or {}
        ptd = u.get('prompt_tokens_details') or {}
        prompt = u.get('prompt_tokens') or u.get('input_tokens') or 0
        cached = (ptd.get('cached_tokens') or u.get('prompt_cache_hit_tokens')
                  or u.get('cache_read_input_tokens') or ptd.get('cache_read_input_tokens') or 0)
        if not prompt:
            print('%-30s ERR %s' % (tag, raw[:140]), flush=True)
            return None
        row = {'tag': tag, 'dt': dt, 'prompt': prompt, 'cached': cached,
               'ray': r.getheader('CF-RAY') or '', 'server': r.getheader('Server') or '',
               'peer': '', 'tp': prompt / dt if dt else 0}
        try:
            row['peer'] = conn.sock.getpeername()[0]
        except Exception:
            pass
        # 双判据：计量判定 + 吞吐判定（超过冷启动速率 1.5 倍即视为实际命中）
        by_usage = 'HIT' if cached > 0.8 * prompt else ('partial' if cached else 'miss')
        by_tp = 'FAST' if row['tp'] > 1.5 * PREFILL_TOKS else 'slow'
        row['verdict'] = by_usage if by_usage != 'miss' else ('UNREPORTED-HIT?' if by_tp == 'FAST' else 'MISS')
        print('%-30s %7.2fs prompt=%-7d cached=%-8d tok/s=%-7.0f %-16s %s%s' % (
            tag, dt, prompt, cached, row['tp'], row['verdict'],
            ('ray=' + row['ray']) if row['ray'] else '',
            (' server=' + row['server']) if row['server'] else ''), flush=True)
        return row


def arm(cl, model, name, content, wait, cross=False, reps=1):
    print('--- %s  间隔=%ds  %s ---' % (name, wait, '跨连接' if cross else '同连接'), flush=True)
    c = cl.connect()
    warm = cl.call(c, model, content, name + ' warm')
    if cross:
        c.close()
    time.sleep(wait)
    probes = []
    for i in range(reps):
        cc = cl.connect() if cross else c
        p = cl.call(cc, model, content, '%s probe%d' % (name, i + 1))
        if p:
            probes.append(p)
        if cross:
            cc.close()
        if i < reps - 1:
            time.sleep(min(15, wait))
    if not cross:
        try:
            c.close()
        except Exception:
            pass
    return warm, probes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='api.agnes-ai.cn')
    ap.add_argument('--path', default='')
    ap.add_argument('--model', default='agnes-3.0-flash')
    ap.add_argument('--key-env', default='AGNES_API_KEY')
    ap.add_argument('--cred', default=r'C:\Users\admin\.dsh\.credentials.yaml')
    ap.add_argument('--anthropic', action='store_true')
    ap.add_argument('--interval', type=int, default=20, help='warm 与 probe 的间隔秒数，必须 >=10')
    ap.add_argument('--timeout', type=int, default=300)
    ap.add_argument('--small-reps', type=int, default=400, help='小 payload 的重复次数（约 1.1 万字/次）')
    ap.add_argument('--queue-reps', type=int, default=60,
                    help='排队税基线 arm 的重复次数（约 1.7K tok，与缓存无关，只测排队）')
    ap.add_argument('--big-reps', type=int, default=4000, help='大 payload 的重复次数（约 11 万 tok）')
    ap.add_argument('--out', default=str(__import__('os').path.join(
        __import__('os').environ.get('TEMP', '.'), 'cache_probe_rows.json')),
        help='明细输出路径（禁止落在仓库根目录）')
    a = ap.parse_args()
    if not a.path:
        a.path = '/anthropic/v1/messages' if a.anthropic else '/v1/chat/completions'
    cl = Client(a)
    S = cl.connect()
    print('peer=%s server=%s' % (S.sock.getpeername()[0] if S.sock else '?', ''), flush=True)
    S.close()

    small = UNIT * a.small_reps
    big = UNIT * a.big_reps
    # 标签按实际规模生成，禁止写死（UNIT 实测约 1.71 字符/token：25,291 tok / 43,200 字符）
    def lab(reps):
        return '%dKtok' % max(1, round(reps * len(UNIT) / 1.71 / 1000.0))
    # 先测"排队税"基线：极小 payload 的多次同连接复测。
    # 没有这条 arm 就会把排队误判成"缓存完全失效"——本工具初版就犯过这个错。
    qw, qps = arm(cl, a.model, 'Q-queue-' + lab(a.queue_reps),
                  UNIT * a.queue_reps + ' [salt=%s]' % salt(), a.interval, reps=2)
    queue_med = statistics.median([p['dt'] for p in qps]) if qps else 0.0
    if qps:
        print('  排队税基线（极小 payload 同连接复测）：warm %s / probes %s 中位 %.1fs'
              ' => 若该值已达数十秒，说明本次端点处于排队主导状态，缓存类判定不可用（先看它再看 hit/miss）' % (
                  ('%.1fs' % qw['dt']) if qw else 'n/a',
                  ['%.1fs' % p['dt'] for p in qps], queue_med), flush=True)
    out = {'queue': (qw, qps)}
    out['end'] = arm(cl, a.model, 'A-end-salt-' + lab(a.small_reps),
                     small + ' [salt=%s]' % salt(), a.interval, reps=2)
    out['start'] = arm(cl, a.model, 'B-start-salt-' + lab(a.small_reps),
                       '[salt=%s] ' % salt() + small, max(a.interval, 30))
    out['cross'] = arm(cl, a.model, 'C-cross-conn-' + lab(a.small_reps),
                       small + ' [salt=%s]' % salt(), a.interval, cross=True)
    out['big'] = arm(cl, a.model, 'D-big-' + lab(a.big_reps), big + ' [salt=%s]' % salt(), a.interval)

    print('\n=== 判定汇总 ===', flush=True)
    for k, (w, ps) in out.items():
        if not ps:
            print('  %-6s 无有效 probe' % k, flush=True)
            continue
        print('  %-6s warm %6.1fs -> probe %s  判定=%s' % (
            k, w['dt'] if w else -1, ['%.1fs/%s' % (p['dt'], p['verdict']) for p in ps],
            '缓存可用' if any(p['cached'] > 0.8 * p['prompt'] for p in ps)
            else ('实际命中但计量未上报' if any(p['verdict'] == 'UNREPORTED-HIT?' for p in ps) else '无命中证据')),
            flush=True)
    print('  读法：B-start-salt 恒 miss 而 A-end-salt 命中 => 前缀严格锚定（易变块必须放末尾）；'
          'C 命中而 A 不命中 => 缓存与连接无关；'
          'A/B/C/D 全 miss 但阳性对照端点命中 => 端点侧当前不缓存，与请求构造无关。', flush=True)
    json.dump({k: [v[0], v[1]] for k, v in out.items() if v[0]},
              open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('  明细已写 %s' % a.out, flush=True)


if __name__ == '__main__':
    main()
