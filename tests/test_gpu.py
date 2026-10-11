"""MJX batching checks run on CPU when the optional package is installed."""

import sys

import numpy as np
import pytest

from rl_sim.gpu import MJXBatchSimulation


SLIDER_XML = """
<mujoco><option timestep="0.02" gravity="0 0 0"/>
  <worldbody><body><joint name="slide" type="slide" axis="1 0 0"/>
    <geom type="sphere" size="0.1" mass="1"/></body></worldbody>
  <actuator><motor joint="slide" ctrlrange="-2 2" ctrllimited="true"/></actuator>
</mujoco>
"""


def test_batch_worlds_have_independent_actions_and_deterministic_reset():
    pytest.importorskip("mujoco.mjx")
    sim = MJXBatchSimulation(SLIDER_XML, batch_size=2, backend="cpu", frame_skip=5)
    state = sim.step([[-1.0], [1.0]])
    assert state["qpos"].shape == (2, 1)
    assert state["qpos"][0, 0] < 0 < state["qpos"][1, 0]
    np.testing.assert_allclose(state["qpos"][0], -state["qpos"][1], atol=1e-6)
    np.testing.assert_allclose(state["time"], [0.1, 0.1], atol=1e-6)
    # Unit mass, controls ±2 N: v=a*t=±0.2 m/s.
    np.testing.assert_allclose(state["qvel"][:, 0], [-0.2, 0.2], atol=1e-6)
    sim.reset()
    np.testing.assert_allclose(sim.snapshot()["qpos"], 0)
    repeat = sim.step([[-1.0], [1.0]])
    np.testing.assert_array_equal(repeat["qpos"], state["qpos"])


def test_bad_actions_fail_before_advancing_any_batch_member():
    pytest.importorskip("mujoco.mjx")
    sim = MJXBatchSimulation(SLIDER_XML, batch_size=2, backend="cpu")
    for action in ([[0]], [[float("nan")], [0]], [[1.01], [0]]):
        with pytest.raises(ValueError):
            sim.step(action)
    np.testing.assert_array_equal(sim.snapshot()["time"], [0, 0])


def test_native_model_energy_diagnostics_do_not_block_batching_or_mutate_source():
    pytest.importorskip("mujoco.mjx")
    import mujoco
    native = mujoco.MjModel.from_xml_string(SLIDER_XML)
    native.opt.enableflags = int(mujoco.mjtEnableBit.mjENBL_ENERGY)
    sim = MJXBatchSimulation(native, batch_size=2, backend="cpu")
    state = sim.step([[-1.0], [1.0]])
    assert state["qpos"][0, 0] < 0 < state["qpos"][1, 0]
    assert native.opt.enableflags == int(mujoco.mjtEnableBit.mjENBL_ENERGY)


@pytest.mark.skipif(sys.platform != "darwin", reason="Mac capability check")
def test_mac_gpu_request_rejects_instead_of_silently_running_cpu():
    with pytest.raises(RuntimeError, match="NVIDIA"):
        MJXBatchSimulation(SLIDER_XML, batch_size=2, backend="gpu")


@pytest.mark.parametrize("kwargs", [
    {"batch_size": 0}, {"batch_size": True}, {"frame_skip": 0},
    {"backend": "mps"},
])
def test_invalid_batch_settings_fail(kwargs):
    with pytest.raises(ValueError):
        MJXBatchSimulation(SLIDER_XML, **kwargs)
