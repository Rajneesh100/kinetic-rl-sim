# Connect an RL project

## One interface, two transports

`LocalEnv` runs native physics in your Python process. It is the preferred CPU training path. `RemoteEnv` speaks the same reset/step semantics over HTTP and makes the world visible to Studio. Remote stepping carries geometry for inspection and is slower. A policy can be implemented in Python, JavaScript, Rust, Go, C++, Julia, or any language that can send JSON HTTP requests.

Gymnasium `reset(seed=42)` returns `(observation, info)`. `step(action)` returns `(observation, reward, terminated, truncated, info)`. Keep the two episode flags separate and reset after either is true. Do not bootstrap a learning target across physical termination; follow your algorithm's truncation handling for time limits.

Observations are float64 arrays with a shape published in the world description. They contain engine generalized positions/velocities; see [physics.md](physics.md) for exact ordering and task semantics. Actions are float arrays normalized to [-1,1] with labels in `description.action_names`. A robot-less sandbox has an empty action vector. Query the description; never hard-code one robot's action shape for another robot.

```python
from rl_sim.sdk import LocalEnv
env = LocalEnv(template="driving", reward_fn=lambda state: state["info"]["speed"])
```

A reward override gets the full latest snapshot and must return a finite scalar. For custom termination/observation logic, wrap the environment with a Gymnasium wrapper. This API deliberately does not execute code uploaded over HTTP.

## HTTP example

```bash
curl -s http://127.0.0.1:8000/api/v1/templates
curl -s -X POST http://127.0.0.1:8000/api/v1/worlds \
  -H 'Content-Type: application/json' -d '{"template":"driving"}'
```

Keep the returned `id`. The creation response contains `scene`, `description` and `state`. Replace `WORLD_ID` below:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/worlds/WORLD_ID/reset \
  -H 'Content-Type: application/json' -d '{"seed":42}'
curl -s -X POST http://127.0.0.1:8000/api/v1/worlds/WORLD_ID/step \
  -H 'Content-Type: application/json' -d '{"action":[0.4,0.0]}'
curl -s http://127.0.0.1:8000/api/v1/worlds/WORLD_ID/state
curl -s -X DELETE http://127.0.0.1:8000/api/v1/worlds/WORLD_ID
```

Calls are synchronous. Each `/step` advances `frames` physics steps, defaulting to `scene.physics.substeps`. Simulated duration is `frames * timestep`, independent of network latency and browser FPS. Do not step one world concurrently from multiple policy clients: calls serialize, but arrival order is not a reproducible policy schedule. Use separate worlds for separate policies.

`POST /step` accepts exactly one of `action` or `demo:true`. The latter uses the engine's scripted demonstration controller. Invalid action lengths, nonfinite values, unknown configuration keys, and out-of-range physics parameters return 422. Missing/deleted worlds return 404. Live sessions are capped at 64 per type; delete unused sessions.

## Inspect a running policy

Create `RemoteEnv`, print its world ID, and attach through Studio's Policy integration workspace. Keep the training process alive. Studio polls `/state` and must not call `/step` while attached. Closing an owned `RemoteEnv` deletes its world; passing `world_id=` attaches without taking ownership, so close preserves it.

To evaluate a saved PPO model visually:

```bash
.venv/bin/python examples/rollout.py --template driving --remote --model data/models/driving-ppo.zip --steps 1000 --realtime
```

## Train

Install the optional training dependency with `.venv/bin/python -m pip install --cache-dir .cache/pip -e '.[train]'` (or uv equivalent). Then:

```bash
.venv/bin/python examples/train_ppo.py --template driving --steps 50000 --envs 4
```

PPO trains an example dense locomotion reward; it is not a self-driving stack, navigation curriculum or pretrained walking gait. The example saves checkpoints under `data/models/` and logs under `data/training/`. Modify the task reward, sensors, domain randomization and curriculum for your actual task. A smoke training run validates integration, not policy quality.

## Reproducibility and persistence

Export scene JSON, record the seed, action schedule, package lock and hardware. Initial reset uses the configured terrain seed; subsequent reset without a seed retains the latest seed. Seeds do not imply bitwise equivalence across hardware, MuJoCo versions or native/MJX solvers. Saved scenes describe initial conditions; they are not full mid-episode checkpoints. `PUT /worlds/{id}/scene` recompiles and resets a world. Live engine state is in memory only.

The built-in service binds to loopback by default and has no multi-user authentication or distributed scheduler. Linux training workers can use the same package independently; the optional GPU runner is a separate in-process batching path, not a GPU toggle for HTTP worlds.
