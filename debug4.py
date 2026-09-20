import csv, struct
BIN=r'F:\JQKJ\CNC\iot_CNC_PLC_IMM.exe'
with open(BIN,'rb') as f: d=f.read()
e=struct.unpack_from('<I',d,0x3c)[0]; pe=e; opt=pe+24
magic=struct.unpack_from('<H',d,opt)[0]
imgbase=struct.unpack_from('<Q',d,opt+24)[0] if magic==0x20b else struct.unpack_from('<I',d,opt+28)[0]
sec_off=opt+240 if magic==0x20b else opt+224
num_sec=struct.unpack_from('<H',d,pe+4+2)[0]
secs=[]
for i in range(num_sec):
    b=sec_off+i*40
    vaddr=struct.unpack_from('<I',d,b+12)[0]; rawoff=struct.unpack_from('<I',d,b+20)[0]; vsize=struct.unpack_from('<I',d,b+8)[0]
    secs.append((vaddr,rawoff,vsize))
def v2o(va):
    rva=va-imgbase
    for(v,ro,vs) in secs:
        if v<=rva<v+vs: return ro+(rva-v)
    return None
def rd64(va):
    o=v2o(va)
    if o is None: return None
    return d[o:o+64]
rows=list(csv.DictReader(open(r'F:\JQKJ\brand_address_raw.csv')))
fanuc=[r for r in rows if r['brand']=='fanuc'][:8]
for r in fanuc:
    f0=r['f0_raw8']
    if not f0: continue
    ptr=int.from_bytes(bytes.fromhex(f0),'little')
    buf=rd64(ptr)
    asc=''.join(chr(c) if 32<=c<127 else '.' for c in buf)
    print(r['semanticVar'], 'ptr=%#x'%ptr)
    print('  hex:', buf.hex())
    print('  asc:', asc)
