# Use Kinetic with a coding agent

Kinetic exposes the same world definitions and simulation controls to people, scripts and agents. An agent can generate a test environment, connect your existing policy, run measured rollouts and open the result in Studio. The included skill provides the workflow and unit conventions; your agent supplies the reasoning and code changes.

## Give the agent the project context

Clone and install the repository using the [README](../README.md#get-started). Open the repository root in your coding agent. Ask it to read:

- [The rl-sim skill](../skills/rl-sim/SKILL.md) for authoring and integration procedures.
- [Scene authoring](scene-authoring.md) for supported geometry and physical parameters.
- [Model integration](integration.md) for actions, observations, rewards and HTTP sessions.
- [Physics limitations](physics.md) before making claims about realism or transfer.

The skill is also discoverable through the project-local `.agents/skills/rl-sim` path in clients that support it. If your client does not discover skills, point it directly to `skills/rl-sim/SKILL.md`. Keep generated files inside this repository; installing the skill globally is unnecessary.

## Create a useful training world

Paste this into your agent, adjusting the task to your project:

> Read skills/rl-sim/SKILL.md. Create a quadruped locomotion course from the quadruped template with seeded low steps and one ramp. Put the generator and scene under data/worlds/. Expose terrain seed, step height and friction. Use the public scene schema and physical geometry. Validate and compile the scene, run a short seeded rollout, and check that observations remain finite. Import it into Studio and enable Follow subject for the quadruped. Describe the units and assumptions, and give me the command to regenerate the same course.

The supported starting templates are `driving`, `quadruped`, `flight` and `sandbox`. Begin with an existing template, then change the relevant parameters:

```bash
.venv/bin/rl-sim export quadruped --output data/worlds/terrain.json
.venv/bin/rl-sim validate data/worlds/terrain.json
```

For an existing procedural example:

```bash
.venv/bin/python examples/build_world.py \
  --seed 42 --output data/worlds/obstacle-course.json
.venv/bin/rl-sim validate data/worlds/obstacle-course.json
```

Import the JSON in Studio, or create an API world with `{"scene": <parsed JSON>}`. Validation checks the schema and compiles a MuJoCo model; it does not establish that a course is traversable or that a policy performs well.

### Geometry and physical settings

Ask for concrete values and ranges. “Add a 2 m long ramp with a 10° slope” is more reproducible than “make a challenging course.” The agent should translate requested dimensions into the schema's conventions:

| Setting | Rigid-body world convention |
| --- | --- |
| Units and axes | SI units; right-handed, z-up. |
| Box size | Half-extents: `[1, 0.5, 0.25]` makes a 2 m × 1 m × 0.5 m box. |
| Rotation | XYZ Euler angles in radians. Returned quaternions are `[w, x, y, z]`. |
| Primitives | Boxes, spheres, cylinders and capsules; compound structures use multiple objects. |
| Dynamic objects | Set `static: false` and configure mass. |
| Parameters | Gravity, contact friction, timestep, substeps, solver, medium density/viscosity/wind, robot mass and motor strength. |

Give objects unique names and avoid unintended initial overlap. Arbitrary CAD meshes, URDF robot imports, soft bodies and fluid-rigid coupling are not supported by the current scene format. Read the full [scene contract](scene-authoring.md) when constructing objects.

## Connect your existing model

Give the agent your model entry point, checkpoint location, observation format and action meaning. Keep any copied checkpoints under `data/models/` in this project. A useful prompt is:

> Read the rl-sim skill and docs/integration.md. My policy loads from [checkpoint] using [framework and entry point]. It expects [observation format] and returns [action format]. Build a small adapter under data/experiments/ that loads the checkpoint, maps observations and actions explicitly, and evaluates it in the driving template. Query the environment description rather than assuming dimensions. Record seeds, rewards, termination and truncation in data/rollouts/. Run a short smoke evaluation, then show a paced RemoteEnv rollout in Studio. Report measured results and any missing inputs before calling the model successful.

Use `LocalEnv` for training without HTTP overhead. A custom scene can be loaded directly:

```python
import json
from pathlib import Path
from rl_sim.sdk import LocalEnv

scene = json.loads(Path("data/worlds/obstacle-course.json").read_text())
env = LocalEnv(scene=scene)
print(env.description)
observation, info = env.reset(seed=42)
try:
    for _ in range(200):
        action = env.action_space.sample()  # Smoke test only; replace with your policy.
        observation, reward, terminated, truncated, info = env.step(action)
        if terminated or truncated:
            observation, info = env.reset()
finally:
    env.close()
```

Observations contain generalized positions and velocities as documented in [physics](physics.md). They are not camera or LiDAR observations. Actions are normalized to `[-1, 1]`; their dimensions and labels are in `env.description`. A custom reward can be passed with `reward_fn`; use Gymnasium wrappers for task-specific observations and episode logic.

For a visible HTTP session, replace the environment construction with:

```python
from rl_sim.sdk import RemoteEnv

env = RemoteEnv("http://127.0.0.1:8000", scene=scene)
print("Attach Studio to world:", env.world_id, flush=True)
```

In **Policy integration → Browse active sessions**, choose the printed session. The viewer reads state while your client advances it. Use one stepping client per world and reset after either `terminated` or `truncated`. Keep the client alive during inspection; closing an owned `RemoteEnv` deletes its world.

## Train the included PPO example

This prompt asks the agent to perform a bounded training run and a separate evaluation:

> Use the rl-sim skill to run the included driving PPO example for 50,000 requested timesteps with four environments and seed 42. Use CPU on this Mac. Save its metadata, checkpoint and logs in the project's data folder. Evaluate the checkpoint with seeds 43, 44 and 45, saving a separate JSONL file for each run. Summarize episode outcomes and reward statistics from the actual logs. Then start a paced remote evaluation so I can attach Studio and follow the vehicle. Do not describe the scripted Run controller as learned behavior.

The corresponding commands are:

```bash
.venv/bin/python -m pip install --cache-dir .cache/pip -e '.[train]'
.venv/bin/python examples/train_ppo.py \
  --template driving --steps 50000 --envs 4 --seed 42 --device cpu
.venv/bin/python examples/rollout.py \
  --template driving --model data/models/driving-ppo.zip \
  --steps 3000 --seed 43 --output data/rollouts/driving-seed-43.jsonl
```

Repeat evaluation with another seed and output file to compare runs. PPO may round the requested timestep budget up to its rollout size; the training metadata records the actual count. Repeating training for the same template overwrites `data/models/<template>-ppo.zip`, so copy checkpoints under distinct names when comparing experiments.

To view evaluation, keep `.venv/bin/rl-sim serve` running in another terminal and add `--remote --realtime` to the rollout command. `--realtime` paces the client for viewing; physics still uses a fixed timestep. The supplied reward encourages example locomotion. Navigation, obstacle avoidance and other goals need their own reward design, observations, curriculum and evaluation criteria.

## Keep the subject in frame

In **Scene editor**, enable **Follow subject** in the viewport toolbar and choose the robot or a named object. **SUBJECT LOCKED** indicates tracking. The camera translates with the target; the world's physics coordinates stay fixed. You can orbit and zoom while tracking, and episode resets re-center the subject.

Tracking is independent of the selected inspector object and works for both scripted previews and attached policy sessions. Panning is disabled while following. Disable tracking to explore freely, or use **Reset camera** for the default overview.

## Author a fluid experiment

Start from [examples/wind_tunnel.json](../examples/wind_tunnel.json) and ask:

> Read the rl-sim skill and docs/fluid-lab.md. Create a 2D wind-tunnel experiment with a NACA 2412 obstacle and a rake dye source. Expose angle, inlet speed, viscosity, grid resolution and timestep. Validate the configuration at the requested resolution, run a short rollout, and report finite-field checks, divergence RMS and CFL. Save the configuration under data/fluids/ and import it into Fluid dynamics. Show smoke and speed views with a measurement probe. Describe pressure correction as a diagnostic, not lift or drag.

The solver accepts circles, boxes, ellipses, NACA 0012/2412 profiles and simple polygons. Fluid geometry uses **full dimensions and degrees**, unlike rigid-body half-extents and radians. Thin obstacles must occupy at least four cell centers and clear the outer boundary cells. The [fluid schema](../schemas/fluid.json) and live `/api/v1/fluid/schema` endpoint define the accepted fields.

Create a session from the supplied example:

```bash
curl -s http://127.0.0.1:8000/api/v1/fluids \
  -H 'Content-Type: application/json' \
  --data-binary @examples/wind_tunnel.json
```

Use the returned ID with `POST /api/v1/fluids/{id}/step`, sending `{"steps":20}`. The API allows up to 20 timesteps per request. Use `DELETE /api/v1/fluids/{id}` when finished.

Fluid experiments are separate from rigid-body Gymnasium worlds. They are not a flight environment or a coupled force solver. Experiment exports contain configuration and diagnostics; importing starts a new simulation rather than restoring a mid-run checkpoint. See [the fluid guide](fluid-lab.md) for exact field meanings.

## Choose the execution path explicitly

- **Apple Silicon:** use native CPU MuJoCo for training and the studio. Rendering uses WebGL; the 2D fluid solver uses the CPU. There is no Metal/MPS physics backend.
- **Linux CPU:** use the same local and HTTP adapters.
- **Linux NVIDIA:** use the optional MJX batch runner for compatible models. It is a separate low-level API, not a setting that accelerates HTTP sessions or a drop-in task environment.

Ask the agent to read [hardware support](hardware.md), report actual devices, and separate compilation time from stepping benchmarks. NVIDIA throughput has not been verified on the development Mac. Passing CPU tests does not establish GPU performance or solver equivalence.

## Request a reproducible handoff

At the end of an experiment, have the agent return:

1. The saved scene or fluid configuration and command to reproduce it.
2. Seeds, policy/checkpoint identity, relevant parameters and package/hardware information.
3. Actual evaluation logs and a concise summary of measured outcomes.
4. A Studio session for inspection while the rollout is alive, with subject tracking where useful.
5. Model assumptions, unsupported features and any failed checks.

Use `data/worlds/` for scenes, `data/models/` for checkpoints, `data/training/` for training output and `data/rollouts/` for evaluations. These are ignored by Git. A scene JSON records initial conditions, not the full state of an episode. Keep distinct copies when comparing experiments.
