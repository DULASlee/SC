#!/usr/bin/env python3
# 从 Ghidra 反编译导出中，按品牌提取每条 KeyData 映射的 (语义变量 -> 3个字段原始8字节 + f3/f4)。
# 不猜测字符串，只可靠地读取符号 VA 处的原始字节，供后续按各品牌结构解码。
import re, struct, sys

BIN = r'F:\JQKJ\CNC\iot_CNC_PLC_IMM.exe'
DEC = r'F:\JQKJ\ghidra-projects\iotCNC_PLC_IMM\decompile.txt'
OUT = r'F:\JQKJ\brand_address_raw.csv'

def parse_pe(path):
    with open(path, 'rb') as f:
        d = f.read()
    e_lfanew = struct.unpack_from('<I', d, 0x3c)[0]
    pe = e_lfanew
    opt = pe + 24
    magic = struct.unpack_from('<H', d, opt)[0]
    if magic == 0x20b:
        imgbase = struct.unpack_from('<Q', d, opt+24)[0]
        num_sec = struct.unpack_from('<H', d, pe+4+2)[0]
        sec_off = opt + 240
    else:
        imgbase = struct.unpack_from('<I', d, opt+28)[0]
        num_sec = struct.unpack_from('<H', d, pe+4+2)[0]
        sec_off = opt + 224
    secs = []
    for i in range(num_sec):
        b = sec_off + i*40
        name = d[b:b+8].split(b'\x00')[0].decode('latin-1','ignore')
        vaddr = struct.unpack_from('<I', d, b+12)[0]
        vsize = struct.unpack_from('<I', d, b+8)[0]
        rawoff = struct.unpack_from('<I', d, b+20)[0]
        secs.append((name, vaddr, vsize, rawoff))
    return imgbase, secs, d

def v2o(va, imgbase, secs):
    rva = va - imgbase
    for (_, vaddr, vsize, rawoff) in secs:
        if vaddr <= rva < vaddr + vsize:
            return rawoff + (rva - vaddr)
    return None

def rd8(va):
    off = v2o(va, imgbase, secs)
    if off is None: return None
    return d[off:off+8].hex()

def addr_code(f0_va):
    # f0 是指向 64 字节 KeyData 结构的指针；结构内偏移约 19 处存有该变量的协议地址码（4字节小端）
    if not f0_va: return ""
    o = v2o(f0_va, imgbase, secs)
    if o is None: return ""
    for off in range(16, 32):
        v = struct.unpack_from('<i', d, o+off)[0]
        if 0 < v < 0x100000:
            return v
    return 0

imgbase, secs, d = parse_pe(BIN)

with open(DEC, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

brand = None
entries = []
cur_fields = []          # list of (lineno, va)
cur_ints = {}            # 'f3'/'f4' -> value
mapre = re.compile(r'map_string_cnc_(\w+KeyData)___Map_type')
symre = re.compile(r'=\s*(?:PTR_)?DAT_([0-9a-fA-F]+)\s*;')
keyre = re.compile(r's(?:_\w+)?\.str\s*=\s*(?:"([^"]*)"|PTR_s_\w+_([0-9a-fA-F]+))')
intre = re.compile(r'(local_58|uStack_50)\s*=\s*(0x[0-9a-fA-F]+)')

for li, ln in enumerate(lines):
    m = mapre.search(ln)
    if m:
        brand = m.group(1).replace('KeyData','').lower()
        cur_fields = []; cur_ints = {}
        continue
    if not brand: 
        continue
    for im in intre.finditer(ln):
        cur_ints[im.group(1)] = im.group(2)
    sm = symre.search(ln)
    if sm:
        cur_fields.append((li, int(sm.group(1),16)))
    km = keyre.search(ln)
    if km:
        key = km.group(1) if km.group(1) else ('PTR:'+km.group(2))
        # take the 3 pointer/value fields within 16 lines before this key
        near = [va for (nl, va) in cur_fields if (li - nl) <= 16 and (li - nl) >= 0]
        fv = near[-3:] if len(near) >= 3 else (near + [None]*(3-len(near)))
        f3 = cur_ints.get('local_58')
        f4 = cur_ints.get('uStack_50')
        if str(key).startswith('PTR:'):
            pass  # leave as PTR:xxx
        if len(entries) < 3:
            with open(r'F:\JQKJ\debug_out.txt','a',encoding='utf-8') as dbg:
                dbg.write(f'key={key} brand={brand} cur_fields={cur_fields} near={near} f3={f3} f4={f4}\n')
        entries.append((brand, key, fv[0], fv[1], fv[2], f3, f4))
        cur_fields = []; cur_ints = {}

print('total entries', len(entries), file=sys.stderr)
# resolve keys that are PTR: to nothing here; dump raw bytes
with open(OUT, 'w', encoding='utf-8') as o:
    o.write('brand,semanticVar,addrCode,f0_raw8,f1_raw8,f2_raw8,f3,f4\n')
    for (br, key, a, b, c, f3, f4) in entries:
        o.write(f'{br},{key},{addr_code(a)},{rd8(a) if a else ""},{rd8(b) if b else ""},{rd8(c) if c else ""},{f3 or ""},{f4 or ""}\n')

# also print per-brand variable counts and a few samples
from collections import defaultdict
cnt = defaultdict(int)
for e in entries: cnt[e[0]] += 1
print('brands:', dict(cnt), file=sys.stderr)
with open(OUT) as o:
    for i, l in enumerate(o):
        if i < 30: print(l.rstrip())
