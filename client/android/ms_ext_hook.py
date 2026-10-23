"""MobileStudio native-extension import hook (bundled builds).

targetSdk 29+ forbids mmap-PROT_EXEC of .so files under app-writable
storage, so every extension module ships inside the APK (jniLibs) and is
loaded from ``MS_NATIVE_LIB_DIR`` (set by PyBridge to
``applicationInfo.nativeLibraryDir``).

This module is emitted into site-packages by tools/build_app_bundle.py
with ``__MANIFEST_JSON__`` replaced by {import-name: jniLib-filename}.
The finder is appended LAST so packages that ship their own bootstrap
(OpenCV) keep working, and plain libraries dlopen'd by NEEDED entries
resolve from the same directory.
"""
import importlib.machinery
import importlib.util
import json
import os
import sys

_MANIFEST = __MANIFEST_JSON__
_LIB_DIR = (os.environ.get("MS_NATIVE_LIB_DIR")
            or os.environ.get("MOBILESTUDIO_NATIVE_LIB_DIR", ""))


def _install() -> None:
    if not _LIB_DIR or not _MANIFEST:
        return

    # packages whose __init__ bootstraps its own extension (OpenCV)
    SELF_BOOTSTRAP = {"cv2"}

    class NativeExtFinder:
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in SELF_BOOTSTRAP:
                return None  # let the package bootstrap resolve it
            libname = _MANIFEST.get(fullname)
            if not libname:
                return None
            full = os.path.join(_LIB_DIR, libname)
            if not os.path.exists(full):
                return None
            loader = importlib.machinery.ExtensionFileLoader(fullname, full)
            spec = importlib.util.spec_from_loader(fullname, loader, origin=full)
            return spec

    if not any(type(f).__name__ == "NativeExtFinder" for f in sys.meta_path):
        # front of meta_path: stub/typing-only package dirs (e.g. .pyi-only)
        # must not shadow the real native extension
        sys.meta_path.insert(0, NativeExtFinder())

    # llvmlite loads its shared library by absolute path from the package
    # directory (writable storage = blocked). Fall back to the bare soname,
    # which resolves from nativeLibraryDir.
    try:
        import ctypes

        orig_cdll = ctypes.CDLL

        def _cdll(name, *a, **k):  # noqa: ANN001, ANN002, ANN003
            try:
                return orig_cdll(name, *a, **k)
            except OSError:
                if isinstance(name, (str, bytes, os.PathLike)) and os.path.basename(
                    os.fspath(name)
                ) != os.fspath(name):
                    return orig_cdll(os.path.basename(os.fspath(name)), *a, **k)
                raise

        if not getattr(ctypes, "_ms_patched", False):
            ctypes.CDLL = _cdll
            ctypes._ms_patched = True
    except Exception:
        pass


_install()
