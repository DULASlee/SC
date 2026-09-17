import struct
BIN=r'F:\JQKJ\CNC\iot_CNC_PLC_IMM.exe'
with open(BIN,'rb') as f: d=f.read()
e=struct.unpack_from('<I',d,0x3c)[0]
pe=e; opt=pe+24
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
def cstr(off,n=80):
    end=d.find(b'\x00',off)
    if end==-1 or end-off>n: end=off+n
    return d[off:end]
# dump the deref target of 0x12afcd0
off=v2o(0x12afcd0)
ptr=struct.unpack_from('<Q',d,off)[0]
print('0x12afcd0 -> ptr',hex(ptr),'-> off',hex(v2o(ptr)))
print('  string at target:', cstr(v2o(ptr)))
# dump raw bytes around target
to=v2o(ptr)
print('  raw:', d[to:to+48].hex())
# also dump the systemInfo literal location
idx=d.find(b'systemInfo')
print('systemInfo literal at off',hex(idx),':', cstr(idx))
# resolve a few more fanuc fields: 0x12afcf0 (spindleSpeed field0)
for va in [0x12afcf0,0x12afcf8,0x12afd00]:
    o=v2o(va); p=struct.unpack_from('<Q',d,o)[0]
    print(hex(va),'-> ptr',hex(p),'str:', cstr(v2o(p)) if v2o(p) else '?')
