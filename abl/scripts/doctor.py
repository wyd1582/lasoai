"""make doctor — check the local environment before launching anything. Read-only; exits 1 on a blocker."""
from __future__ import annotations

import importlib
import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = ["numpy", "pandas", "scipy", "sklearn", "duckdb", "yaml", "pytest", "streamlit", "rdata", "matplotlib"]


def main() -> int:
    ok = True
    def row(status, what, detail=""):
        nonlocal ok
        mark = {"ok": "OK ", "warn": "!! ", "fail": "XX "}[status]
        if status == "fail": ok = False
        print(f"{mark} {what:<34} {detail}")

    v = sys.version_info
    row("ok" if v >= (3, 9) else "fail", "Python", f"{v.major}.{v.minor}.{v.micro} at {sys.executable}")
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    row("ok" if in_venv else "warn", "virtualenv", sys.prefix if in_venv else "not in a venv (run: . .venv/bin/activate)")
    inside = Path(sys.prefix).resolve().is_relative_to(ROOT) if hasattr(Path, "is_relative_to") else str(Path(sys.prefix).resolve()).startswith(str(ROOT))
    row("ok" if inside else "warn", "venv is project-local", "yes" if inside else "venv lives outside abl/ (fine, but keep it separate from other projects)")
    for m in REQUIRED:
        try:
            mod = importlib.import_module(m); row("ok", f"import {m}", getattr(mod, "__version__", ""))
        except Exception as e:
            row("fail", f"import {m}", f"{type(e).__name__}: pip install -r requirements.lock")
    lock = ROOT / "requirements.lock"
    if lock.exists():
        try:
            out = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True, timeout=60).stdout
            have = {l.split("==")[0].lower(): l.split("==")[1] for l in out.splitlines() if "==" in l}
            drift = [l for l in lock.read_text().splitlines() if "==" in l and have.get(l.split("==")[0].lower()) not in (None, l.split("==")[1])]
            row("ok" if not drift else "warn", "versions match requirements.lock", "yes" if not drift else f"{len(drift)} differ, e.g. {drift[0]} (installed {have.get(drift[0].split('==')[0].lower())})")
        except Exception as e:
            row("warn", "versions match requirements.lock", f"could not check: {e}")
    for rel, what in [("data/vendor/pig_cleveland_curated.rdata", "pig data"), ("data/vendor/wheat.RData", "wheat data"), ("gates/thresholds.yaml", "gate thresholds"), ("control/RUN", "control/RUN")]:
        p = ROOT / rel; row("ok" if p.exists() else "fail", what, str(p) if p.exists() else f"missing: {p}")
    if (ROOT / "control" / "PAUSE").exists():
        row("warn", "control/PAUSE present", "the loop will stop before its first step; delete it or press RESUME in the dashboard")
    db = ROOT / "registry" / "abl.sqlite"
    row("ok" if db.exists() else "warn", "demo ledger", f"{db.stat().st_size // 1024} KB" if db.exists() else "none yet: run `make demo` (8 min) before `make watch`")
    port = int(os.environ.get("PORT", "8501"))
    with socket.socket() as s:
        free = s.connect_ex(("127.0.0.1", port)) != 0
    row("ok" if free else "warn", f"port {port}", "free" if free else f"in use: run `PORT={port + 1} make watch`")
    key = "set" if os.environ.get("ANTHROPIC_API_KEY") else "not set"
    row("ok", "LLM backend", f"anthropic (ANTHROPIC_API_KEY {key})" if key == "set" else "stub (offline, deterministic); set ANTHROPIC_API_KEY to use claude-opus-5")
    try:
        git = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%h %s"], capture_output=True, text=True, timeout=10).stdout.strip()
        row("ok", "git HEAD", git)
    except Exception:
        pass
    print("\nall clear: run `make watch`" if ok else "\nfix the XX lines first")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
