// ExportDecompileToFile.java
// Ghidra headless postScript: 遍历当前程序所有函数，反编译每个函数，输出到一个文本文件
// 调用方式: analyzeHeadless <proj> <name> -process -postScript ExportDecompileToFile.java <out.txt>
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.decompiler.DecompiledFunction;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.app.script.GhidraScript;
import java.io.*;

public class ExportDecompileToFile extends GhidraScript {

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String outFile;
        if (args.length > 0) {
            outFile = args[0];
        } else {
            outFile = "f:\\JQKJ\\.decomp\\ghidra\\decompile-export.txt";
        }

        println("[ExportDecompileToFile] Output: " + outFile);
        FunctionManager fm = currentProgram.getFunctionManager();
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        int total = 0;
        int ok = 0;
        int fail = 0;
        try (PrintWriter pw = new PrintWriter(new OutputStreamWriter(new FileOutputStream(outFile), "UTF-8"))) {
            pw.println("// Ghidra decompile export for: " + currentProgram.getName());
            pw.println("// Image base: " + currentProgram.getImageBase());
            pw.println("// Total functions: " + fm.getFunctionCount());
            pw.println();

            for (Function f : fm.getFunctions(true)) {
                total++;
                String header = "=== " + f.getName() + " @ " + f.getEntryPoint() +
                                " (size=" + f.getBody().getNumAddresses() + ") ===";
                pw.println(header);
                try {
                    DecompileResults res = decomp.decompileFunction(f, 60, monitor);
                    if (res != null && res.getDecompiledFunction() != null) {
                        pw.println(res.getDecompiledFunction().getC());
                        ok++;
                    } else {
                        pw.println("// [decompile returned no result]");
                        fail++;
                    }
                } catch (Exception e) {
                    pw.println("// [decompile error: " + e.getMessage() + "]");
                    fail++;
                }
                pw.println();
                if (total % 50 == 0) {
                    println("[ExportDecompileToFile] progress: " + total + "/" + fm.getFunctionCount() +
                            " (ok=" + ok + " fail=" + fail + ")");
                }
            }
        }
        println("[ExportDecompileToFile] DONE. total=" + total + " ok=" + ok + " fail=" + fail);
    }
}
