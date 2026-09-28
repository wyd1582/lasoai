#!/usr/bin/env python3
"""make replay — run one compact A+D campaign on the simulation twice (ABL_LANG=zh, ABL_LANG=en) in
throw-away ABL_ROOTs, export both, merge into reports/replay/sim_D_replay.json, and refresh the
hypothesis bank export. Nothing under abl/registry is touched. ~3 minutes with the offline model."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
OUT = PROJECT / "reports" / "replay"


def run_campaign(root: Path, lang: str) -> None:
    for d in ("control", "data/snapshots", "holdout", "registry", "reports"):
        (root / d).mkdir(parents=True, exist_ok=True)
    (root / "control" / "RUN").touch()
    if not (root / "gates").exists():
        os.symlink(PROJECT / "gates", root / "gates")
    code = ("import subprocess, sys; subprocess.check_call([sys.executable, 'scripts/seal_holdout.py']);"
            "from campaigns.runner import Campaign; from registry import Registry; from scripts._common import sim_bundle;"
            "c = Campaign(sim_bundle(), registry=Registry(), seed=0, n_proposals=24, budget_full_evals=4, run_tag='replay'); c.run_all('AD')")
    env = dict(os.environ, ABL_ROOT=str(root), ABL_LANG=lang, ABL_LLM="stub", PYTHONPATH=str(PROJECT))
    subprocess.check_call([sys.executable, "-c", code], cwd=PROJECT, env=env)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="abl_replay_") as tmp:
        parts = []
        for lang in ("zh", "en"):
            root = Path(tmp) / lang
            run_campaign(root, lang)
            out = Path(tmp) / f"replay.{lang}.json"
            subprocess.check_call([sys.executable, "scripts/export_replay.py", "--root", str(root), "--campaign", "sim_D_s0_rreplay", "--lang", lang, "--out", str(out)],
                                  cwd=PROJECT, env=dict(os.environ, PYTHONPATH=str(PROJECT), ABL_LLM="stub"))
            parts.append(str(out))
        subprocess.check_call([sys.executable, "scripts/export_replay.py", "--merge", *parts, "--out", str(OUT / "sim_D_replay.json")], cwd=PROJECT, env=dict(os.environ, PYTHONPATH=str(PROJECT)))
    subprocess.check_call([sys.executable, "scripts/export_replay.py", "--bank", "--out", str(OUT / "bank.json")], cwd=PROJECT, env=dict(os.environ, PYTHONPATH=str(PROJECT), ABL_LLM="stub"))
    print(f"replay + bank → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
