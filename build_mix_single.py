"""Build the single-file Kaggle submission bundle for mix_agent.

Kaggle ERRORS on multi-file tar.gz for this competition — the submission MUST
be a single self-contained main.py. This script embeds purearch_opponent.py
and c27_agent.py (both stdlib-only) as zlib+base85 blobs, then embeds
mix_agent.py's source VERBATIM (auto-synced) with `c27_agent.` redirected to
the embedded namespace `c27` and the module imports dropped (the wrapper
defines `pa` / `c27` from the blobs).

Output: submissions/mix_single/main.py
Usage:   python build_mix_single.py
"""
from __future__ import annotations

import base64
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "submissions" / "mix_single" / "main.py"


def _blob(path: Path) -> str:
    src = path.read_text(encoding="utf-8")
    idx = src.find("if __name__")
    if idx > 0:
        src = src[:idx]
    return base64.b85encode(zlib.compress(src.encode("utf-8"))).decode("utf-8")


def build() -> None:
    pa_src = ROOT / "reference" / "opponents" / "purearch_opponent.py"
    c27_src = ROOT / "c27_agent.py"
    pa_b = _blob(pa_src)
    c27_b = _blob(c27_src)

    # mix_agent.py body, auto-synced. Transform: drop the two module imports
    # (the wrapper defines `pa`/`c27` from blobs), redirect `c27_agent.` -> `c27.`.
    mix_src = (ROOT / "mix_agent.py").read_text(encoding="utf-8")
    idx = mix_src.find("if __name__")
    if idx > 0:
        mix_src = mix_src[:idx]
    # Remove the sys.path manipulation + imports that would fail standalone.
    lines = []
    for line in mix_src.splitlines():
        s = line.strip()
        if s.startswith("import purearch_opponent as pa"):
            continue
        if s == "import c27_agent" or s.startswith("import c27_agent  #"):
            continue
        if s.startswith("sys.path.insert"):
            continue
        if s.startswith('_HERE = os.path.dirname'):
            continue
        if s.startswith("sys.path.insert(0, _HERE)"):
            continue
        if s.startswith("import os"):
            continue
        if s.startswith("import sys"):
            continue
        if s.startswith("from __future__ import annotations"):
            continue  # the wrapper header already has it (must be first)
        lines.append(line)
    mix_src = "\n".join(lines)
    mix_src = mix_src.replace("c27_agent.", "c27.")

    mix_body = (
        "# ---------------------------------------------------------------------------\n"
        "# mix_agent logic (auto-synced from mix_agent.py: module refs -> embedded ns)\n"
        "# ---------------------------------------------------------------------------\n"
        + mix_src
    )

    header = f'''"""mix_agent - single-file Kaggle submission bundle.

purearch base trace + clone front-run + maturity front-run + market-flow
adaptive-horizon preempt + order-slot sell-first.

Built by build_mix_single.py. Self-contained: embeds purearch_opponent.py and
c27_agent.py (stdlib-only) as zlib+base85 blobs.
"""
from __future__ import annotations

import base64
import types
import zlib

_PA_B85 = {pa_b!r}
_C27_B85 = {c27_b!r}


def _load(blob, modname):
    code = zlib.decompress(base64.b85decode(blob)).decode("utf-8")
    ns = types.ModuleType(modname)
    ns.__file__ = modname + ".py"
    exec(compile(code, modname + ".py", "exec"), ns.__dict__)
    return ns


pa = _load(_PA_B85, "purearch_opponent")
c27 = _load(_C27_B85, "c27_agent")
'''

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(header + mix_body, encoding="utf-8")
    print(f"OK -> {OUT} ({OUT.stat().st_size} bytes)")
    print(f"    pa blob: {len(pa_b)} chars | c27 blob: {len(c27_b)} chars")


if __name__ == "__main__":
    build()
