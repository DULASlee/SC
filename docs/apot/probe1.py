import os,io
p0=r"F:\JQKJ\docs\ai-workspace"
print("os.path.realpath:", os.path.realpath(p0))
try:
    st=os.lstat(p0)
    print("lstat st_mode=%o"%st.st_mode, "islink=False" if False else "")
except FileNotFoundError:
    print("lstat: 不存在")
for r,d,f in os.walk(r"F:\JQKJ\LnkCollector_src"):
    rel=os.path.relpath(r,r"F:\JQKJ\LnkCollector_src")
    print("WALK", rel if rel!="." else "【根】", "实时存在" if os.path.exists(r) else "(探不到)")
    for n in f[:8]:
        print("   -",n)
    if os.path.normpath(r)!=os.path.normpath(r"F:\JQKJ\LnkCollector_src"): break