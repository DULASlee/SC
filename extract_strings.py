import re
path = r'F:\JQKJ\CNC\iot_CNC_PLC_IMM.exe'
with open(path, 'rb') as fh:
    data = fh.read()
runs = re.findall(rb'[\x20-\x7e]{4,}', data)
out = [r.decode('latin-1') for r in runs]
with open(r'F:\JQKJ\strings_imm.txt', 'w', encoding='utf-8') as w:
    w.write('\n'.join(out))
print('total strings', len(out))
