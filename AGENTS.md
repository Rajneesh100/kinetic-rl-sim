# RL Sim project instructions

All code, generated scenes, artifacts, model checkpoints, documentation and project-specific memory belong under this folder. Do not install project skills or memory globally. Keep caches under `.cache/` and dependencies under `.venv/` or `web/node_modules/`.

Read `skills/rl-sim/SKILL.md` for world creation, physical configuration and model integration. Read `memory/PROJECT.md` before substantial changes. The API/scene contracts and fidelity limitations are public behavior; update docs and relevant tests when changing them.

Verify backend work with `.venv/bin/python -m pytest --basetemp=.cache/pytest` and UI work with `cd web && npm run build`. Inspect the real studio when changing the viewport or interaction. Do not claim trained behavior from the scripted demo. Native CPU and MJX GPU are distinct execution paths.

When `/graphify` is explicitly invoked, read the installed graphify skill first. Keep any graph outputs inside this folder; exclude `.venv`, `.cache`, `node_modules`, `dist` and `data` from source analysis.
