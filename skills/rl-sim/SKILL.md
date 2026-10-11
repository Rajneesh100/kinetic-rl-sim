---
name: rl-sim
description: Build and validate Kinetic RL Sim worlds, configure physical parameters, connect reinforcement-learning policies, and inspect training or evaluation through its local API and Gymnasium adapters. Use for this simulator's scenes, objects, terrain, fluid lab and model integration.
---

# Kinetic RL Sim

Work from the project root containing `pyproject.toml` and `rl_sim/`. Keep generated scenes, models, logs, docs and project memory in this project; do not write a global memory record or install this skill globally unless the user asks.

## Build or edit a world

1. Read [scene authoring](../../docs/scene-authoring.md) and get the live schema from `GET /api/v1/schema`, or inspect `rl_sim/schema.py` locally. Read [physics limits](../../docs/physics.md) when selecting models or interpreting results.
2. Export the closest template: `.venv/bin/rl-sim export driving --output data/worlds/my-world.json`. Templates are driving, quadruped, flight and sandbox.
3. Edit the JSON. SI units, z-up. Box dimensions are half-extents. Capsule/cylinder axes are local z. Rotations are XYZ Euler radians; returned quaternions are wxyz. Give objects unique names and avoid initial penetrations. Set static=false for dynamic bodies.
4. Compose ramps, walls and courses from primitives; use `examples/build_world.py` for a deterministic generated course. Expose the seed, gravity, friction, masses, wind and solver settings relevant to the user's experiment. Do not invent scene fields or claim an unsupported robot import works.
5. Compile with `.venv/bin/rl-sim validate data/worlds/my-world.json`. Fix the actual validation/compilation errors before running.
6. Create a session by posting `{"scene": <parsed scene>}` to `/api/v1/worlds`; retain its ID and returned action/observation description. Run a short seeded rollout, check finite values, collisions and termination, and inspect Studio. Save the final JSON and explain modeled assumptions.

## Connect a policy

Read [integration](../../docs/integration.md). Prefer `LocalEnv` for fast native training; use `RemoteEnv` when the user wants live visual inspection. Query `description.action_names` and dimensions. Policies output normalized actions [-1,1]; no client wall-clock timing should define physics.

For HTTP, reset then step with explicit `action`. `demo:true` is a scripted preview, not model training. Studio attaches to external sessions in observation mode so it does not advance training time. Reset on either terminated or truncated. Do not label a trained checkpoint successful without measuring evaluation behavior and recording seeds, scene and episode statistics.

For PPO use `examples/train_ppo.py`; for arbitrary models use `examples/rollout.py` or replace the policy call in the integration example. Store checkpoints under `data/models/`, experiment logs under `data/training/`, and evaluations under `data/rollouts/`. A custom reward can be supplied to the Python adapter; task-specific observations and termination can use Gymnasium wrappers.

## Hardware and fluid experiments

Read [hardware](../../docs/hardware.md) for native Apple Silicon vs optional MJX/JAX on NVIDIA. HTTP sessions are native CPU physics; do not imply a GPU switch changes them. Report actual devices and measured throughput, separating compilation time from stepping.

The fluid lab is independent 2-D incompressible flow with a passive dye field. Inspect `/api/v1/fluid/schema`, create with `POST /api/v1/fluids`, then advance `/fluids/{id}/step`. It does not provide forces to MuJoCo and is not 3-D CFD. MuJoCo's wind/density/viscosity controls model body-fluid forces approximately. State those boundaries in any conclusion about flight or real-world transfer.

For wind-tunnel authoring, read [fluid experiments](../../docs/fluid-lab.md) and start from [the airfoil example](../../examples/wind_tunnel.json). Use explicit named `obstacles` for circles, boxes, ellipses, NACA 0012/2412 or simple polygons. Fluid widths/heights are full dimensions and angles are degrees; do not reuse rigid-body half-extents/radians. Validate at the intended grid resolution: thin bodies must occupy at least four cells and clear boundary cells. Use `source_mode:"rake"` for smoke stripes. Run a short rollout and inspect actual masks, divergence, CFL and finite fields before returning a scene. Studio supports JSON import/export, draft obstacle edits, streamlines and cell probes. `pressure_correction` is the last zero-mean projection correction, not pressure in Pa or validated lift/drag. Exports contain diagnostics, not resumable solver checkpoints.

## Resume project work

Read [project memory](../../memory/PROJECT.md) for current decisions and [verification](../../docs/verification.md) for recorded checks. Runtime health: `/api/v1/health`; API docs: `/docs`. Do not mistake old verification notes for a current passing test. When a new feature is requested, update its code, schema/docs and behavior checks together.
