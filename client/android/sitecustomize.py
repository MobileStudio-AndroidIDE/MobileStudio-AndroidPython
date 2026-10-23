"""MobileStudio Android Python bootstrap.

Runs at interpreter start (site-packages/sitecustomize.py). On Android it
auto-configures pip so that a plain `pip install <pkg>` pulls wheels from
the MobileStudio GitHub Release index:

  * first run  : writes <sys.prefix>/pip.conf (idempotent, marker-guarded)
  * every run  : sets PIP_CONFIG_FILE so pip (any entry point, any version)
                 picks the config up

Set MOBILESTUDIO_NO_PIP_BOOTSTRAP=1 to disable.
"""
import os
import sys


def _ms_pip_bootstrap() -> None:
    if sys.platform != "android" or os.environ.get("MOBILESTUDIO_NO_PIP_BOOTSTRAP"):
        return
    try:
        import certifi  # system certifi shipped in site-packages

        ca = certifi.where()
    except Exception:
        return

    prefix = sys.prefix
    conf = os.path.join(prefix, "pip.conf")
    index = (
        "https://mobilestudio-androidide.github.io/"
        "MobileStudio-AndroidPython/simple/"
    )
    header = "# managed-by: mobilestudio-pip-bootstrap\n"
    body = (
        "[global]\n"
        f"index-url = {index}\n"
        "extra-index-url = https://pypi.org/simple\n"
        f"cert = {ca}\n"
        f"cache-dir = {os.path.join(os.path.dirname(prefix), 'pip-cache')}\n"
        # no compiler on-device: never attempt sdists, wheels only. This makes
        # pip fall back to our (older) release wheel instead of trying to
        # build a newer PyPI sdist.
        "only-binary = :all:\n"
    )
    try:
        content = ""
        if os.path.exists(conf):
            with open(conf, "r", encoding="utf-8") as fh:
                content = fh.read()
        if (header not in content or "only-binary" not in content
                or index not in content):  # upgrade stale confs
            with open(conf, "w", encoding="utf-8") as fh:
                fh.write(header + body)
        os.environ.setdefault("PIP_CONFIG_FILE", conf)
    except OSError:
        pass  # read-only filesystem: pip falls back to PyPI defaults


_ms_pip_bootstrap()
