// ExportBrandMap.java
// Ghidra headless postScript: 仅反编译名称含品牌/映射关键字的接口，导出到文本文件。
// 用法: analyzeHeadless <projDir> <projName> -postScript ExportBrandMap.java <out.txt> -process
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.app.script.GhidraScript;
import java.io.*;
import java.util.regex.*;

public class ExportBrandMap extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String outFile = args.length > 0 ? args[0] : "f:\\JQKJ\\brandmap.txt";
        String[] keys = {"mitsubishi","fanuc","siemens","haidehan","gsk","syntec",
                         "brother","knd","mazak","keydata","keyset","loadsettings",
                         "handleoverride","position","mach","imm","plc","cnc.",
                         "readvar","vardef","command","calculateoee","parseresponse",
                         "getdata","getvalue","override","default"};
        Pattern pat = Pattern.compile(".*(" + String.join("|", keys) + ").*", Pattern.CASE_INSENSITIVE);
        FunctionManager fm = currentProgram.getFunctionManager();
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);
        int total = 0, ok = 0, fail = 0, skip = 0;
        try (PrintWriter pw = new PrintWriter(new OutputStreamWriter(new FileOutputStream(outFile), "UTF-8"))) {
            pw.println("// brand map decompile export for: " + currentProgram.getName());
            for (Function f : fm.getFunctions(true)) {
                String nm = f.getName();
                if (!pat.matcher(nm).matches()) { skip++; continue; }
                total++;
                pw.println("=== " + nm + " @ " + f.getEntryPoint() + " ===");
                try {
                    DecompileResults res = decomp.decompileFunction(f, 90, monitor);
                    if (res != null && res.getDecompiledFunction() != null) {
                        pw.println(res.getDecompiledFunction().getC());
                        ok++;
                    } else { pw.println("// no result"); fail++; }
                } catch (Exception e) { pw.println("// err " + e.getMessage()); fail++; }
                pw.println();
            }
        }
        println("DONE total=" + total + " ok=" + ok + " fail=" + fail + " skip=" + skip);
    }
}
