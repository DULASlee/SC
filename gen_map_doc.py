#!/usr/bin/env python3
# 由 brand_address_raw.csv 生成可读的「全品牌地址映射表」文档。
import csv, re

NOISE_SUBSTR = ('http', 'sha', 'md5', 'basic', 'fips', 'ripemd', '#', 'opcfoundation',
                '/ua/', 'self-test', 'verified', 'aes', 'fips140', 'code+data', 'none',
                'basic128', 'basic256', ':', 'm100', 'd100', 'ptr:')
NOISE_EXACT = {'m', 'r', 'w', 'x', 'y', 'z', 'a', 'mach', 'rel', 'res', 'abs'}

def is_noise(k):
    kl = k.lower()
    if kl in NOISE_EXACT:
        return True
    if kl.startswith('ptr:'):
        return True
    return any(n in kl for n in NOISE_SUBSTR)

rows = list(csv.DictReader(open(r'F:\JQKJ\brand_address_raw.csv', encoding='utf-8')))
# 仅保留有 f0（即真实 KeyData 条目）的；过滤库字符串噪声
def keep(r):
    if not r.get('f0_raw8'):
        return False
    if is_noise(r['semanticVar']):
        return False
    return True

clean = [r for r in rows if keep(r)]
bybrand = {}
for r in clean:
    bybrand.setdefault(r['brand'], []).append(r)

out = []
out.append('# 全品牌地址映射表（从 Go 二进制 iot_CNC_PLC_IMM.exe 反编译提取）\n')
out.append('> 来源：Ghidra 反编译 `decompile.txt` 中各品牌 `map[string]cnc.<Brand>KeyData` 映射。')
out.append('> 每个语义变量对应一个 KeyData 结构，其中 `addrCode` 为该变量在对应 CNC 协议栈中的命令/地址码。\n')

out.append('## 结构说明\n')
out.append('- 每个 `KeyData` 条目：`f0` 指向一个 64 字节结构，内含该变量的协议地址码（addrCode 列）。')
out.append('- `f3/f4` 为结构内的类型/长度标记。')
out.append('- 三菱（MitsubishiCNC）地址码落在 `74803~74806` 区间，按变量组分；可直接用于 `RemoteComm` 宏/PLC 读取（见 GenCollector 已知地址速查）。')
out.append('- 发那科（Fanuc）地址码为 `40` / `68` 两组（对应 FOCAS 函数族）。\n')

for br in ['fanuc', 'mitsubishi', 'simens']:
    items = bybrand.get(br, [])
    if not items:
        continue
    out.append(f'## {br}  （{len(items)} 个语义变量）\n')
    out.append('| 语义变量 (MeasEncoding) | addrCode | f3 | f4 |')
    out.append('|---|---|---|---|')
    for r in items:
        out.append(f"| {r['semanticVar']} | {r['addrCode'] or ''} | {r['f3'] or ''} | {r['f4'] or ''} |")
    out.append('')

out.append('## 已知真实地址（已验证可直连）\n')
out.append('- **Mitsubishi CNC（RemoteComm.dll）**：宏 33868=加工时间、2097=运行时间、33565=切削时间、33869=零件数；PLC 42.0=运行、42.1=暂停、50.14=告警。')
out.append('- 其余品牌（fanuc/simens/haidehan/gsk/syntec/brother/knd/mazak）的寄存器级地址需结合设备手册或 Go 源码（`E:/workspace/.../cnc/<brand>_commands.go`，二进制内仅保留路径）做二次解码；本表给出的 `addrCode` 即 Go 协议栈内部寻址码，可作为驱动实现的索引。\n')

out.append('## 原始数据\n')
out.append('完整逐字段（含 f0/f1/f2 原始字节）见 `brand_address_raw.csv`。\n')

open(r'F:\JQKJ\brand_address_map.md', 'w', encoding='utf-8').write('\n'.join(out))
print('wrote brand_address_map.md, clean entries:', len(clean), {k: len(v) for k, v in bybrand.items()})
