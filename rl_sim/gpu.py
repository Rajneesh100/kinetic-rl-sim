"""Optional, explicit-device MJX-JAX batching. Imports no JAX until constructed.

This lower-level runner batches native MuJoCo actuator controls; it does not
implement the task rewards, termination or grouped actions of the Gym adapter.
"""

from __future__ import annotations

import sys
from copy import copy

import numpy as np


class MJXBatchSimulation:
    """Advance independent copies of one MJCF model with JIT-compiled vmap.

    ``backend='gpu'`` requires a detected NVIDIA GPU on Linux and never falls
    back to CPU. ``backend='cpu'`` is useful for functional checks, including
    Apple Silicon. Construction transfers the model; first step compiles it.
    """

    def __init__(self, model_or_xml, *, batch_size=128, backend="gpu", frame_skip=1):
        if type(batch_size) is not int or not 1 <= batch_size <= 16384:
            raise ValueError("batch_size must be an integer between 1 and 16384")
        if type(frame_skip) is not int or not 1 <= frame_skip <= 1000:
            raise ValueError("frame_skip must be an integer between 1 and 1000")
        if backend not in {"cpu", "gpu"}:
            raise ValueError("backend must be 'cpu' or 'gpu'; Apple MPS is not supported")
        if backend == "gpu" and sys.platform != "linux":
            raise RuntimeError(
                "NVIDIA MJX requires Linux with a compatible CUDA JAX installation. "
                "Use backend='cpu' for MJX functional checks on this machine, or "
                "use native Simulation for local Apple Silicon physics."
            )
        try:
            import jax
            import jax.numpy as jnp
            import mujoco
            from mujoco import mjx
        except ImportError as exc:
            raise RuntimeError(
                "MJX is optional. On Linux NVIDIA install 'rl-sim[gpu]'; for CPU "
                "checks install mujoco-mjx and jax in the project environment."
            ) from exc
        try:
            devices = jax.devices(backend)
        except RuntimeError as exc:
            raise RuntimeError(
                f"JAX backend {backend!r} is unavailable. For NVIDIA install the "
                "GPU extra and verify CUDA/driver compatibility; no CPU fallback was used."
            ) from exc
        if not devices:
            raise RuntimeError(f"No JAX {backend} device was detected")
        device = devices[0]
        device_platform = str(getattr(device.client, "platform_version", "")).lower()
        if backend == "gpu" and not (
            "cuda" in device_platform or "nvidia" in device.device_kind.lower()
        ):
            raise RuntimeError(f"Expected NVIDIA GPU, found {device.device_kind!r}")
        if isinstance(model_or_xml, str):
            native_model = mujoco.MjModel.from_xml_string(model_or_xml)
        elif isinstance(model_or_xml, mujoco.MjModel):
            native_model = copy(model_or_xml)
        else:
            raise TypeError("model_or_xml must be an MjModel or MJCF XML string")
        self.batch_size = batch_size
        self.frame_skip = frame_skip
        self.backend = backend
        self.device_name = device.device_kind
        self.device = device
        self.action_size = native_model.nu
        energy_flag = int(mujoco.mjtEnableBit.mjENBL_ENERGY)
        self.disabled_diagnostics = ["energy"] if native_model.opt.enableflags & energy_flag else []
        # MJX rejects this native diagnostic flag. It changes energy accounting,
        # not equations of motion; never alter the caller's native model.
        native_model.opt.enableflags &= ~energy_flag
        self.dt = float(native_model.opt.timestep) * frame_skip
        self._jax, self._jnp = jax, jnp
        limited = np.asarray(native_model.actuator_ctrllimited, dtype=bool)
        ranges = np.asarray(native_model.actuator_ctrlrange)
        self._center = np.where(limited, ranges.mean(axis=1), 0).astype(np.float32)
        self._scale = np.where(limited, (ranges[:, 1] - ranges[:, 0]) / 2, 1).astype(np.float32)
        native_data = mujoco.MjData(native_model)
        mujoco.mj_forward(native_model, native_data)
        try:
            with jax.default_device(device):
                self.model = mjx.put_model(native_model, device=device)
                initial = mjx.put_data(native_model, native_data, device=device)
                self._initial = jax.tree.map(
                    lambda a: jnp.broadcast_to(a, (batch_size,) + a.shape), initial,
                )
        except (NotImplementedError, ValueError) as exc:
            raise RuntimeError(
                "This model uses a feature unsupported by MJX-JAX. Use native "
                f"Simulation or a compatible MJCF model; see docs/hardware.md. Detail: {exc}"
            ) from exc

        def advance(data, controls):
            def one_world(world_data, control):
                world_data = world_data.replace(ctrl=control)
                return jax.lax.fori_loop(
                    0, frame_skip, lambda _, state: mjx.step(self.model, state), world_data,
                )
            return jax.vmap(one_world)(data, controls)

        self._advance = jax.jit(advance)
        self.data = self._initial

    def reset(self) -> dict:
        self.data = self._initial
        return self.snapshot()

    def step(self, actions) -> dict:
        """Normalized actions shape (batch_size, model.nu), each in [-1, 1]."""
        try:
            values = np.asarray(actions, dtype=np.float32)
        except (TypeError, ValueError) as exc:
            raise ValueError("actions must be a finite numeric batch") from exc
        expected = (self.batch_size, self.action_size)
        if values.shape != expected:
            raise ValueError(f"Expected actions shape {expected}, got {values.shape}")
        if not np.isfinite(values).all() or np.any(np.abs(values) > 1):
            raise ValueError("Every normalized action must be finite and within [-1, 1]")
        controls = values * self._scale + self._center
        controls = self._jax.device_put(controls, self.device)
        candidate = self._advance(self.data, controls)
        # Host transfer synchronizes asynchronous JAX execution before return.
        state = {
            "qpos": np.asarray(candidate.qpos).copy(),
            "qvel": np.asarray(candidate.qvel).copy(),
            "time": np.asarray(candidate.time).copy(),
        }
        if not all(np.isfinite(value).all() for value in state.values()):
            raise RuntimeError("MJX produced nonfinite state; previous state is retained")
        self.data = candidate
        return state

    def snapshot(self) -> dict:
        return {
            "qpos": np.asarray(self.data.qpos).copy(),
            "qvel": np.asarray(self.data.qvel).copy(),
            "time": np.asarray(self.data.time).copy(),
        }

    def description(self) -> dict:
        return {
            "backend": f"mjx-jax-{self.backend}", "device": self.device_name,
            "batch_size": self.batch_size, "action_size": self.action_size,
            "dt": self.dt, "frame_skip": self.frame_skip,
            "disabled_diagnostics": self.disabled_diagnostics,
        }
