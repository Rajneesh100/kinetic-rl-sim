# Hardware, batching and numerical limits

## Apple Silicon: primary local platform

The studio/API and Gymnasium adapter use native MuJoCo on the CPU. Rendering uses browser WebGL. The independent Flow Lab uses NumPy on the CPU. These are separate workloads: a browser GPU renderer does not make the physics GPU accelerated.

No CUDA installation is needed on a Mac. This project does not support Apple MPS/Metal physics. JAX lists Apple GPU support as experimental; the provided MJX runner accepts only `cpu` and Linux NVIDIA `gpu`. Keep native MuJoCo as the local development path. See the [JAX platform support table](https://docs.jax.dev/en/latest/installation.html).

The optional CPU MJX path is useful to check a batched model before moving it to a GPU machine:

```bash
UV_CACHE_DIR=.cache/uv uv pip install --python .venv/bin/python mujoco-mjx jax
PYTHONPYCACHEPREFIX=.cache/pycache JAX_COMPILATION_CACHE_DIR=.cache/jax \
  .venv/bin/python -m examples.gpu_batch --backend cpu --batch-size 4 --steps 10
```

## NVIDIA Linux: optional MJX batching

Use a separate Linux machine with a supported NVIDIA GPU and driver. Install the project GPU extra in its local environment:

```bash
UV_CACHE_DIR=.cache/uv uv pip install --python .venv/bin/python -e '.[gpu]'
PYTHONPYCACHEPREFIX=.cache/pycache JAX_COMPILATION_CACHE_DIR=.cache/jax \
  .venv/bin/python -m examples.gpu_batch --backend gpu --batch-size 128 --steps 100
```

The extra currently selects JAX's CUDA 12 wheels. JAX's published requirements include a Linux NVIDIA driver at least 525 for CUDA 12, but individual GPU generations can require newer CUDA/driver combinations. Check the current [official JAX installation instructions](https://docs.jax.dev/en/latest/installation.html) for the target machine. The runner rejects unavailable backends and incompatible hardware; it never silently substitutes CPU for a GPU request.

`rl_sim.gpu.MJXBatchSimulation` accepts an `mujoco.MjModel` or a self-contained MJCF XML string. It creates a batch of independent states, advances them with `jax.vmap`, `jax.jit` and a fixed substep loop, and returns synchronized NumPy `qpos`, `qvel` and `time` arrays. Actions have shape `(batch_size, model.nu)`, contain finite values in `[-1, 1]`, and map linearly into each limited actuator's `ctrlrange`. Unlimited actuators receive the normalized value directly. Reset restores the model's default pose, not a current native simulation state or a keyframe.

```python
import numpy as np
from rl_sim.gpu import MJXBatchSimulation

# native_simulation.model must use MJX-supported features.
batch = MJXBatchSimulation(
    native_simulation.model, backend="gpu", batch_size=128, frame_skip=5,
)
actions = np.zeros((128, batch.action_size), dtype=np.float32)
state = batch.step(actions)
print(state["qpos"].shape, batch.description())
```

This is a lower-level batch physics runner. It has per-actuator actions and no Gym task reward/termination logic. The native car's grouped throttle/steering actions and the aircraft's grouped actions require their own mapping before use here. Policies, observations, rewards and episode resets for GPU training remain the caller's responsibility. It is not a drop-in replacement for the local/HTTP Gymnasium adapter.

The example measures first-call compilation separately, warms up the compiled function, and synchronizes every timed step by copying state to the host. The reported throughput therefore includes host transfer. It is a measurement of the selected model and machine, not a promised speedup. For an end-to-end accelerator training loop, keep policy inference and state/reward calculations on device and benchmark that loop separately.

## MJX model compatibility

MJX-JAX does not implement every native MuJoCo feature; see the [official MJX documentation](https://mujoco.readthedocs.io/en/latest/mjx.html). The runner copies an input native model and disables only native energy-accounting diagnostics on the copy because MJX rejects that flag. This does not change dynamics and is reported in `description().disabled_diagnostics`. The caller's model is retained unchanged. Other unsupported features fail with the original compatibility detail.

The following checks were made with MuJoCo/MJX 3.15.0:

| Model | MJX-JAX result |
| --- | --- |
| Included batch slider example | Real CPU JIT/batching verified |
| Default driving world | Rejects cylinder–box collision pairs |
| Default flight world | Rejects ellipsoid–box collision pairs |
| Default quadruped and sandbox | Rejects the combination of `implicitfast` integrator and fluid drag |
| Quadruped and sandbox with explicit Euler | Transfer and one real two-world CPU step verified |

A supported integrator such as Euler can be selected explicitly for compatible models. Changing contact geometry, integrator or fluid settings can change dynamics; the runner does not make those substitutions automatically. Native MuJoCo remains the supported path for every built-in world. MJX-Warp is a separate implementation with different capabilities and is not implemented by this runner.

For the verified quadruped configuration, construct a separate scene before batching:

```python
from rl_sim.engine import Simulation
from rl_sim.scenes import get_template

scene = get_template("quadruped")
scene.physics.integrator = "Euler"
native_simulation = Simulation(scene)
# Pass native_simulation.model to MJXBatchSimulation as shown above.
```

That check establishes that the chosen configuration compiles and advances. It does not establish long-rollout stability, policy quality or numerical parity with the native integrator.

## Flow Lab model

The 2-D solver is independent of MuJoCo. It models passive dye and an incompressible velocity field in a unit square with matched left/right flow rates, free-slip top/bottom walls, and named solid obstacles (circles, boxes, ellipses, NACA profiles or polygons). It uses face-centered velocities, semi-Lagrangian advection, implicit diffusion and a masked conjugate-gradient pressure projection. A bounded iteration count limits solve accuracy. Snapshot velocities are cell centered; rows run from bottom to top. Fields and source positions use the unit-domain coordinate system.

`divergence_rms` measures the remaining compressive component after projection. `cfl` is maximum centered speed times timestep divided by cell width. Semi-Lagrangian sampling stays bounded at large timesteps, but larger CFL values reduce transport accuracy and can move dye past small features. Increasing resolution or timestep can require more projection iterations. Scalar diffusion enforces no flux through solid faces; velocity diffusion near solids remains approximate, and dye advection is not exactly mass conserving. Viscosity, diffusion, inflow, source, dissipation, geometry and iteration count are editable. See [fluid experiments](fluid-lab.md) for field interpretations and API examples.

This solver is an educational 2-D flow model. It does not simulate a validated turbulent flow, compressible flow, free surfaces or 3-D CFD. Its pressure/dye fields do not apply forces to aircraft, cars or robots. Native aircraft forces use MuJoCo's separate aerodynamic approximation.

## Verification recorded locally

Checked on 12 October 2026, macOS 26.5.2 arm64, Python 3.12, NumPy 2.5.4, MuJoCo/MJX 3.15.0, JAX/JAXlib 0.11.2:

- Fluid tests check pressure projection, known dye displacement, diffusion and dissipation, finite/reproducible obstacle rollouts and input validation.
- Optional MJX tests run actual JIT-compiled CPU batches, verify opposite controls on independent worlds, deterministic reset, correct simulated time and rejection of invalid controls.
- A four-world CPU batch example compiled and ran successfully. This is functional validation, not an NVIDIA benchmark.
- NVIDIA GPU execution and throughput have **not** been verified on this Mac. No GPU performance or cross-backend numerical equivalence is claimed.

Run the focused numerical checks from the project root:

```bash
PYTHONPYCACHEPREFIX=.cache/pycache JAX_COMPILATION_CACHE_DIR=.cache/jax \
  .venv/bin/python -m pytest tests/test_fluids.py tests/test_gpu.py -q -o cache_dir=.cache/pytest
```
