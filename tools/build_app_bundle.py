#!/usr/bin/env python3
"""Build the MobileStudio in-app Python bundle from the wheelhouse.

targetSdk 29+ forbids dlopen()/execve() of .so files from app-writable
storage, so every native extension (stdlib dynload + wheels) ships inside
the APK (jniLibs) and is loaded via the ms_ext_hook meta-path finder
(MS_NATIVE_LIB_DIR). Pure Python files ship as an assets zip extracted to
filesDir on first run.

Outputs (default ./dist/app-bundle):
  jniLibs/arm64-v8a/   libpython3.13.so, libpyexec.so, libms*.so, dep libs
  assets/mobilestudio-python.zip
  PyBridge.java
"""
from __future__ import annotations

import json
import re
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WHEELHOUSE = ROOT / "wheelhouse"
RUNTIME = Path("/home/limsemin/AndroidPython")
DIST = ROOT / "dist" / "app-bundle"

EXT_SUFFIX = ".cpython-313-aarch64-linux-android.so"
ABI3_SUFFIX = ".abi3.so"
NDK = Path(os.environ.get("ANDROID_NDK_HOME",
                          "/home/limsemin/Android/Sdk/ndk/28.2.13676358"))
STRIP = NDK / "toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip"
PATCHELF = os.environ.get("PATCHELF", "/tmp/opencode/venv/bin/patchelf")

LIB_LIBS = {
    "chaquopy_openblas": "libopenblas.so",
    "chaquopy_libgfortran": "libgfortran.so",
    "chaquopy_libcxx": "libc++_shared.so",
    "chaquopy_freetype": "libfreetype.so",
    "chaquopy_libjpeg": "libjpeg.so",
    "chaquopy_libpng": "libpng.so",
    "chaquopy_libyaml": "libyaml.so",
    "chaquopy_libxml2": "libxml2.so",
    "chaquopy_libxslt": "libxslt.so",
    "chaquopy_libffi": "libffi.so",
}

PURE_COPY_DIRS = ("pip", "setuptools", "wheel", "certifi", "packaging",
                  "_distutils_hack", "distutils")
PURE_COPY_FILES = ("distutils-precedence.pth",)


def module_name(rel: Path) -> str | None:
    name = rel.name
    for suf in (EXT_SUFFIX, ABI3_SUFFIX, ".so"):
        if name.endswith(suf):
            stem = name[: -len(suf)]
            return ".".join(list(rel.parts[:-1]) + [stem])
    return None


EXCLUDE_DATA_EXT = {".a", ".h", ".hpp", ".hh", ".c", ".cc", ".cpp", ".cxx",
                    ".cmake", ".pc", ".pyx", ".pxd", ".pxi", ".pyxbld",
                    ".license", ".txt.in"}


def is_data_file(n: str) -> bool:
    if n.endswith(".so"):
        return False
    if "dist-info/" in n:
        return True  # keep METADATA/RECORD (licenses tiny enough)
    return not n.lower().endswith(tuple(EXCLUDE_DATA_EXT))


def strip_file(path: Path) -> None:
    subprocess.run([str(STRIP), "--strip-debug", str(path)], check=True)


NM = NDK / "toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-nm"


def is_python_ext(path: Path) -> bool:
    """True when the .so exports a PyInit_* symbol (i.e. is importable)."""
    out = subprocess.run([str(NM), "-D", "--defined-only", str(path)],
                         capture_output=True, text=True).stdout
    return "PyInit_" in out


def main() -> None:
    jni = DIST / "jniLibs" / "arm64-v8a"
    if jni.exists():
        shutil.rmtree(jni)
    jni.mkdir(parents=True, exist_ok=True)
    staging = DIST / "python-root"
    if staging.exists():
        shutil.rmtree(staging)
    (staging / "lib" / "python3.13").mkdir(parents=True)

    manifest: dict[str, str] = {}
    counter = 0

    def add_native(src: Path, mod: str) -> None:
        nonlocal counter
        counter += 1
        libname = f"libms{counter:04d}_{mod.replace('.', '_')}.so"
        shutil.copy2(src, jni / libname)
        strip_file(jni / libname)
        manifest[mod] = libname

    def add_lib(src: Path, libname: str) -> None:
        dest = jni / libname
        shutil.copy2(src, dest)
        strip_file(dest)

    # ---- runtime core ----
    shutil.copy2(RUNTIME / "lib" / "libpython3.13.so", jni / "libpython3.13.so")
    shutil.copy2(RUNTIME / "bin" / "python3.13", jni / "libpyexec.so")

    src_std = RUNTIME / "lib" / "python3.13"
    dst_std = staging / "lib" / "python3.13"
    skip_dirs = {"lib-dynload", "site-packages", "__pycache__", "test",
                 "idlelib", "tkinter", "turtledemo"}
    for item in src_std.iterdir():
        if item.name in skip_dirs:
            continue
        if item.is_dir():
            shutil.copytree(item, dst_std / item.name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc",
                                                          "*test*", "tests"))
        else:
            shutil.copy2(item, dst_std / item.name)

    # stdlib dynamic extensions -> jniLibs (W^X)
    for so in sorted((src_std / "lib-dynload").glob("*.so")):
        mod = so.name.split(".cpython-313-")[0]
        add_native(so, mod)

    # pure site-packages core
    sp_dst = dst_std / "site-packages"
    sp_dst.mkdir()
    sp_src = src_std / "site-packages"
    for name in (*PURE_COPY_DIRS, *PURE_COPY_FILES):
        p = sp_src / name
        if not p.exists():
            continue
        if p.is_dir():
            shutil.copytree(p, sp_dst / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(p, sp_dst / name)

    # ---- wheels: pick the HIGHEST version per distribution (no mixing) ----
    def _verkey(v: str):
        parts = re.findall(r"\d+", v)
        return [int(x) for x in parts] or [0]

    chosen: dict[str, tuple[str, Path]] = {}
    man_path = WHEELHOUSE / "MANIFEST.json"
    if man_path.exists():
        for w in json.loads(man_path.read_text())["wheels"]:
            cur = chosen.get(w["package"])
            if cur is None or _verkey(w["version"]) > _verkey(cur[0]):
                chosen[w["package"]] = (w["version"], WHEELHOUSE / w["filename"])
    else:
        for w in sorted(WHEELHOUSE.glob("*.whl")):
            chosen.setdefault(w.name.rsplit("-", 3)[0], ("", w))

    SELF_NAMED = {"cv2"}  # opencv's ext is cv2/cv2.<abi>.so == module "cv2"
    for _pkg, (_ver, wheel) in sorted(chosen.items()):
        if wheel.name.startswith("chaquopy_"):
            continue
        with zipfile.ZipFile(wheel) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                n = info.filename
                if n.endswith(".pyc") or "__pycache__" in n:
                    continue
                if n.endswith(".so"):
                    tmp = DIST / ".tmp.so"
                    tmp.write_bytes(zf.read(n))
                    if not is_python_ext(tmp):
                        base = os.path.basename(n)
                        dest = jni / base
                        if not dest.exists():
                            shutil.copy2(tmp, dest)
                            strip_file(dest)
                            print(f"[lib ] {base} <- {wheel.name}")
                    else:
                        mod = module_name(Path(n))
                        last = mod.rsplit(".", 1)[-1] if mod else ""
                        skip_mod = (mod is None or last == "tests"
                                    or last.endswith("_tests")
                                    or ".tests." in mod)
                        if not skip_mod:
                            head = mod.split(".")[0]
                            if head in SELF_NAMED and mod == head + "." + head:
                                mod = head
                            add_native(tmp, mod)
                    tmp.unlink(missing_ok=True)
                elif is_data_file(n):
                    target = sp_dst / n
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(zf.read(n))

    # ---- chaquopy runtime libraries (NEEDED-resolved) ----
    for prefix, libname in LIB_LIBS.items():
        matches = sorted(WHEELHOUSE.glob(f"{prefix}-*.whl"))
        if not matches:
            print(f"[warn] {prefix} wheel missing")
            continue
        dest = jni / libname
        if dest.exists() and prefix != "chaquopy_libgfortran":
            continue
        with zipfile.ZipFile(matches[-1]) as zf:
            so_files = [i for i in zf.namelist() if ".so" in os.path.basename(i)]
            tmp = DIST / ".tmp_lib.so"
            tmp.write_bytes(zf.read(so_files[0]))
        add_lib(tmp, libname)
        tmp.unlink(missing_ok=True)
        print(f"[lib ] {libname} <- {matches[-1].name}")

    # libgfortran soname fix: NEEDED "libgfortran.so.3" -> libgfortran.so
    gf = jni / "libgfortran.so"
    if gf.exists():
        subprocess.run([PATCHELF, "--set-soname", "libgfortran.so", str(gf)], check=True)
        for so in jni.glob("*.so"):
            if so == gf:
                continue
            out = subprocess.run([PATCHELF, "--print-needed", str(so)],
                                 capture_output=True, text=True).stdout
            if "libgfortran.so.3" in out:
                subprocess.run([PATCHELF, "--replace-needed",
                                "libgfortran.so.3", "libgfortran.so", str(so)], check=True)

    # NDK OpenMP runtime (needed by sklearn/scipy OpenMP extensions)
    omp = (NDK / "toolchains/llvm/prebuilt/linux-x86_64/lib/clang/19/lib/linux/aarch64/libomp.so")
    if omp.exists() and not (jni / "libomp.so").exists():
        add_lib(omp, "libomp.so")
        print("[lib ] libomp.so <- NDK clang runtime")

    # ---- python-side glue ----
    hook = (ROOT / "client" / "android" / "ms_ext_hook.py").read_text()
    (sp_dst / "ms_ext_hook.py").write_text(
        hook.replace("__MANIFEST_JSON__", json.dumps(manifest, sort_keys=True)))
    shutil.copy2(ROOT / "client" / "android" / "sitecustomize.py",
                 sp_dst / "sitecustomize.py")

    cv2_conf = sp_dst / "cv2" / "config-3.13.py"
    if cv2_conf.exists():
        cv2_lib = manifest.get("cv2", "")
        gen = (
            "import os\n"
            "import tempfile\n\n"
            "_ms_lib = (os.environ.get('MS_NATIVE_LIB_DIR')\n"
            "           or os.environ.get('MOBILESTUDIO_NATIVE_LIB_DIR', ''))\n"
            "_ms_target = os.path.join(_ms_lib, " + repr(cv2_lib) + ")\n"
            "_ms_dir = os.path.join(\n"
            "    os.environ.get('TMPDIR', tempfile.gettempdir()), 'ms-cv2-link')\n"
            "_ms_link = os.path.join(_ms_dir, 'cv2.cpython-313-aarch64-linux-android.so')\n"
            "try:\n"
            "    os.makedirs(_ms_dir, exist_ok=True)\n"
            "    if _ms_lib and (not os.path.exists(_ms_link)\n"
            "                    or os.readlink(_ms_link) != _ms_target):\n"
            "        if os.path.lexists(_ms_link):\n"
            "            os.remove(_ms_link)\n"
            "        os.symlink(_ms_target, _ms_link)\n"
            "except OSError:\n"
            "    pass\n\n"
            "PYTHON_EXTENSIONS_PATHS = [\n"
            "    _ms_dir if os.path.exists(_ms_link) else _ms_lib,\n"
            "    os.path.dirname(os.path.abspath(__file__)),\n"
            "] + PYTHON_EXTENSIONS_PATHS\n"
        )
        cv2_conf.write_text(gen)
        (sp_dst / "cv2" / "config.py").write_text("import os\n\nBINARIES_PATHS = []\n")

    manifest["__pyexec__"] = "libpyexec.so"
    (staging / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True))

    # ---- assets zip ----
    assets = DIST / "assets"
    assets.mkdir(exist_ok=True)
    zpath = assets / "mobilestudio-python.zip"
    if zpath.exists():
        zpath.unlink()
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in sorted(staging.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(staging))

    shutil.copy2(ROOT / "client" / "android" / "PyBridge.java", DIST / "PyBridge.java")
    mb = lambda p: round(sum(f.stat().st_size for f in Path(p).rglob("*") if f.is_file()) / 1e6, 1)
    print(f"jniLibs: {mb(jni)} MB ({len(list(jni.glob('*.so')))} files)")
    print(f"assets : {zpath.name} {round(zpath.stat().st_size / 1e6, 1)} MB")
    print(f"modules: {len(manifest)}")


if __name__ == "__main__":
    main()
