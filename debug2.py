import struct, re
BIN = r'F:\JQKJ\CNC\iot_CNC_PLC_IMM.exe'
with open(BIN,'rb') as f: d=f.read()
e_lfanew=struct.unpack_from('<I',d,0x3c)[0]
pe=e_lfanew
opt=pe+4+20
magic=struct.unpack_from('<H',d,opt)[0]
if magic==0x20b:
    imgbase=struct.unpack_from('<Q',d,opt+24)[0]
    num_sec=struct.unpack_from('<H',d,pe+4+2)[0]
    sec_off=opt+240
else:
    imgbase=struct.unpack_from('<I',d,opt+28)[0]
    num_sec=struct.unpack_from('<H',d,pe+4+2)[0]
    sec_off=opt+224
secs=[]
for i in range(num_sec):
    b=sec_off+i*40
    name=d[b:b+8].split(b'\x00')[0].decode('latin-1','ignore')
    vaddr=struct.unpack_from('<I',d,b+12)[0]
    rawoff=struct.unpack_from('<I',d,b+20)[0]
    vsize=struct.unpack_from('<I',d,b+8)[0]
    secs.append((name,vaddr,rawoff,vsize))
print('imgbase',hex(imgbase))
def v2o(va):
    rva=va-imgbase
    for(nm,v,ro,vs) in secs:
        if v<=rva<v+vs:
            return ro+(rva-v), nm
    return None,None
# locate "systemInfo" in file
idx=0
hits=[]
while True:
    idx=d.find(b'systemInfo',idx)
    if idx<0: break
    hits.append(idx); idx+=1
print('systemInfo file offsets:',hits[:5])
for h in hits[:3]:
    # reverse map
    va=None
    for(nm,v,ro,vs) in secs:
        if ro<=h<ro+(vs if vs>0 else 0) or ro<=h:
            pass
    # find section containing h
    for(nm,v,ro,vs) in secs:
        if ro<=h<ro+ (vs if vs<len(d) else 0x100000):
            va=imgbase+v+(h-ro); break
    print('  off',hex(h),'-> VA',hex(va) if va else None, 'sec',nm)
# dump 0x12afcd0
off,nm=v2o(0x12afcd0)
print('0x12afcd0 -> off',hex(off) if off else None,'sec',nm)
if off:
    chunk=d[off:off+32]
    print('  bytes:',chunk.hex())
    ptr=struct.unpack_from('<Q',d,off)[0]
    print('  ptr(8)=',hex(ptr))
    o2,n2=v2o(ptr) if ptr>imgbase else (None,None)
    print('  deref off/va',hex(o2) if o2 else None, hex(ptr))
