# ABL deployment (English summary)

The full step-by-step guide is Chinese-first: `docs/DEPLOY.zh.md`. This page is the same
sequence in brief.

| # | where | what |
|---|---|---|
| 1–2 | — | done: the code lives in `wyd1582/lasoai`, ABL under `abl/` |
| 3 | your machine | `git clone https://github.com/wyd1582/lasoai.git && cd lasoai/abl` → `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt` → `make test` → `make demo` → `make watch` |
| 4 | GitHub | ruleset on `main`: require PR, require checks `test (3.9)`, `test (3.11)`, `site`, block force pushes |
| 5 | Render | New → Blueprint → the `lasoai` repo; the root `render.yaml` (rootDir `abl`) is picked up; enter `ABL_DASHBOARD_PASSWORD`; first build ≈10–12 min |
| 6 | Vercel | import the repo, preset **Other**; the root `vercel.json` builds `abl/site/dist`; set `ABL_APP_URL` to the Render URL |
| 7 | DNS | `app` CNAME → the Render host (verify in Render); apex + `www` per Vercel's Domains page |
| 8 | Vercel | set `ABL_APP_URL=https://app.<domain>` and redeploy |

After that, every change is: branch → PR → CI green → merge; Render and Vercel deploy `main`
automatically. Roll back from Render **Events → Rollback** or Vercel **Deployments → Instant Rollback**.

Measured: the demo build peaks at ≈1 GB RAM and the dashboard at ≈183 MB RAM, so Render's 512 MB plans suffice (Starter stays
up; Free sleeps after 15 min idle). The deployed dashboard runs in demo mode (`ABL_DEMO=1`):
read-only, controls hidden, simulated data only, no API keys on the server.
