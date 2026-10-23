// MobileStudio PyBridge — embeds the bundled CPython 3.13 (ARM64) runtime.
//
// First call extracts assets/mobilestudio-python.zip into
//   <filesDir>/ms-python/            (stdlib + pure site-packages + manifest)
// Native extensions live in the APK (jniLibs) and are loaded from
//   applicationInfo.nativeLibraryDir  (W^X safe on targetSdk 29+).
//
// Simple JSON API:
//   PyBridge.Result r = PyBridge.run(context, "import sys; print(sys.version)");
//   PyBridge.Result r = PyBridge.pip(context, "install", "numpy");
//
// exec() spawns <nativeLibraryDir>/libpyexec.so with a sandboxed env
// (PYTHONHOME/PYTHONPATH/LD_LIBRARY_PATH/MS_NATIVE_LIB_DIR are all set).
package com.aide.mobilestudio.python;

import android.content.Context;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

public final class PyBridge {

    public static final String BUNDLE_ASSET = "mobilestudio-python.zip";
    public static final String BUNDLE_VERSION = "2026-10-23.2"; // bump to re-extract

    private static volatile boolean sReady;

    private PyBridge() {}

    public static final class Result {
        public final int exitCode;
        public final String stdout;
        public final String stderr;
        Result(int exitCode, String stdout, String stderr) {
            this.exitCode = exitCode;
            this.stdout = stdout;
            this.stderr = stderr;
        }
        public boolean ok() { return exitCode == 0; }
        @Override public String toString() {
            return "Result{exit=" + exitCode + ", out=" + stdout + ", err=" + stderr + "}";
        }
    }

    // ------------------------------------------------------------------ //

    public static synchronized void ensureReady(Context ctx) throws IOException {
        if (sReady) return;
        File root = pythonRoot(ctx);
        File marker = new File(root, ".bundle-" + BUNDLE_VERSION);
        if (!marker.exists()) {
            extract(ctx, BUNDLE_ASSET, root);
            marker.createNewFile();
        }
        sReady = true;
    }

    /** Run Python code, return captured output. */
    public static Result run(Context ctx, String code) throws IOException, InterruptedException {
        ensureReady(ctx);
        return exec(ctx, "-c", code);
    }

    /** Run pip (e.g. pip(ctx, "install", "numpy")). Uses the MobileStudio index. */
    public static Result pip(Context ctx, String... args) throws IOException, InterruptedException {
        ensureReady(ctx);
        List<String> argv = new ArrayList<>();
        argv.add("-m");
        argv.add("pip");
        Collections.addAll(argv, args);
        return exec(ctx, argv.toArray(new String[0]));
    }

    /** Low-level: spawn the bundled interpreter with the app env. */
    public static Result exec(Context ctx, String... args)
            throws IOException, InterruptedException {
        ensureReady(ctx);
        File root = pythonRoot(ctx);
        String nativeDir = ctx.getApplicationInfo().nativeLibraryDir;
        File pyExec = new File(nativeDir, "libpyexec.so");

        Map<String, String> env = baseEnv(ctx);

        ProcessBuilder pb;
        try {
            pb = spawn(pyExec.getAbsolutePath(), args, env, ctx);
        } catch (IOException directFailed) {
            // extracted natives may lack the +x bit; go through the linker
            pb = spawn("/system/bin/linker64", prepend(pyExec.getAbsolutePath(), args), env, ctx);
        }

        Process p = pb.start();
        StreamReader out = new StreamReader(p.getInputStream());
        StreamReader err = new StreamReader(p.getErrorStream());
        out.start(); err.start();
        boolean finished = p.waitFor(10, TimeUnit.MINUTES);
        if (!finished) {
            p.destroyForcibly();
            throw new IOException("python timed out");
        }
        out.join(5000); err.join(5000);
        return new Result(p.exitValue(), out.text(), err.text());
    }

    private static ProcessBuilder spawn(String bin, String[] args,
                                        Map<String, String> env, Context ctx)
            throws IOException {
        List<String> argv = new ArrayList<>();
        argv.add(bin);
        Collections.addAll(argv, args);
        ProcessBuilder pb = new ProcessBuilder(argv);
        pb.environment().putAll(env);
        pb.directory(ctx.getCacheDir());
        pb.redirectErrorStream(false);
        return pb;
    }

    private static String[] prepend(String first, String[] rest) {
        String[] out = new String[rest.length + 1];
        out[0] = first;
        System.arraycopy(rest, 0, out, 1, rest.length);
        return out;
    }

    public static Map<String, String> baseEnv(Context ctx) {
        File root = pythonRoot(ctx);
        String nativeDir = ctx.getApplicationInfo().nativeLibraryDir;
        Map<String, String> env = new LinkedHashMap<>();
        env.put("PYTHONHOME", root.getAbsolutePath());
        env.put("PYTHONPATH", sitePackages(ctx));
        env.put("PYTHONUSERBASE", new File(root, "user").getAbsolutePath());
        env.put("LD_LIBRARY_PATH", nativeDir);
        env.put("MS_NATIVE_LIB_DIR", nativeDir);
        env.put("MOBILESTUDIO_NATIVE_LIB_DIR", nativeDir);
        env.put("PATH", new File(root, "bin").getAbsolutePath()
                + ":/system/bin:/system/xbin");
        env.put("HOME", ctx.getFilesDir().getAbsolutePath());
        env.put("TMPDIR", ctx.getCacheDir().getAbsolutePath());
        env.put("MPLCONFIGDIR", new File(ctx.getCacheDir(), "mpl").getAbsolutePath());
        env.put("PIP_CONFIG_FILE", new File(root, "pip.conf").getAbsolutePath());
        return env;
    }

    public static File pythonRoot(Context ctx) {
        return new File(ctx.getFilesDir(), "ms-python");
    }

    public static String sitePackages(Context ctx) {
        return new File(pythonRoot(ctx),
                "lib/python3.13/site-packages").getAbsolutePath();
    }

    // ------------------------------------------------------------------ //

    private static void extract(Context ctx, String asset, File destDir)
            throws IOException {
        if (!destDir.exists() && !destDir.mkdirs()) {
            throw new IOException("cannot mkdir " + destDir);
        }
        try (InputStream in = ctx.getAssets().open(asset);
             ZipInputStream zin = new ZipInputStream(in)) {
            ZipEntry e;
            byte[] buf = new byte[1 << 16];
            while ((e = zin.getNextEntry()) != null) {
                File f = new File(destDir, e.getName());
                if (e.isDirectory()) { f.mkdirs(); continue; }
                File parent = f.getParentFile();
                if (parent != null && !parent.exists() && !parent.mkdirs()) {
                    throw new IOException("cannot mkdir " + parent);
                }
                try (FileOutputStream fo = new FileOutputStream(f)) {
                    int n;
                    while ((n = zin.read(buf)) > 0) fo.write(buf, 0, n);
                }
            }
        }
    }

    private static final class StreamReader extends Thread {
        private final InputStream in;
        private final StringBuilder sb = new StringBuilder();
        StreamReader(InputStream in) { this.in = in; setDaemon(true); }
        @Override public void run() {
            try (BufferedReader r = new BufferedReader(
                    new InputStreamReader(in, StandardCharsets.UTF_8))) {
                char[] buf = new char[8192];
                int n;
                while ((n = r.read(buf)) > 0) sb.append(buf, 0, n);
            } catch (IOException ignored) {
            }
        }
        String text() { return sb.toString(); }
    }
}
