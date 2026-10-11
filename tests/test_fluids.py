"""Numerical behavior checks, independent of the rendering layer."""

import json

import numpy as np
import pytest
from pydantic import ValidationError

from rl_sim.fluids import FluidConfig, FluidSimulation


def quiet_config(**updates):
    return FluidConfig(**{
        "resolution": 32, "obstacle": False, "inflow": 0.0,
        "dye_source": 0.0, "diffusion": 0.0, "viscosity": 0.0,
        "dissipation": 0.0, "iterations": 150, **updates,
    })


def test_projection_removes_compressive_velocity():
    sim = FluidSimulation(quiet_config())
    rng = np.random.default_rng(14)
    sim.u[:, 1:-1] = rng.normal(0, 0.3, sim.u[:, 1:-1].shape)
    sim.v[1:-1, :] = rng.normal(0, 0.3, sim.v[1:-1, :].shape)
    before = np.sqrt(np.mean(sim.divergence() ** 2))
    sim.project()
    after = np.sqrt(np.mean(sim.divergence() ** 2))
    assert after < before * 0.01


def test_uniform_flow_advects_dye_by_velocity_times_time():
    sim = FluidSimulation(quiet_config(inflow=0.5, timestep=0.02))
    yy, xx = np.mgrid[:32, :32]
    sim.density[:] = np.exp(-((xx - 10) ** 2 + (yy - 16) ** 2) / 6)
    initial_x = np.sum(sim.density * (xx + 0.5) / 32) / sim.density.sum()
    sim.step(steps=5)
    final_x = np.sum(sim.density * (xx + 0.5) / 32) / sim.density.sum()
    assert final_x - initial_x == pytest.approx(0.05, abs=0.002)
    assert sim.time == pytest.approx(0.1)


def test_diffusion_spreads_dye_and_dissipation_decays_it():
    sim = FluidSimulation(quiet_config(diffusion=0.01, dissipation=1.0))
    sim.density[16, 16] = 1.0
    initial_mass = sim.density.sum()
    sim.step(steps=10)
    assert 0 < sim.density.max() < 0.2
    assert sim.density[16, 15] > 0
    assert sim.density.sum() == pytest.approx(initial_mass * np.exp(-0.2), rel=0.02)


def test_obstacle_blocks_flow_and_source_rollout_is_finite_reproducible():
    sim = FluidSimulation(FluidConfig(resolution=32))
    initial = sim.snapshot()
    state = sim.step(steps=80)
    assert state["time"] == pytest.approx(1.6)
    assert np.sum(state["density"]) > 0
    assert np.isfinite(state["density"]).all()
    assert np.isfinite(state["u"]).all()
    assert np.isfinite(state["v"]).all()
    assert np.all(sim.density[sim.obstacle] == 0)
    assert state["metrics"]["divergence_rms"] < 0.03
    json.dumps(state, allow_nan=False)
    sim.reset()
    assert sim.snapshot() == initial
    assert sim.step(steps=80) == state


@pytest.mark.parametrize("config", [
    {"resolution": 15}, {"resolution": 129}, {"viscosity": -0.1},
    {"inflow": float("nan")}, {"timestep": float("inf")},
    {"unknown_field": 4}, {"iterations": 10.5},
    {"obstacle_x": 0.05, "obstacle_radius": 0.15},
])
def test_config_rejects_unsafe_or_unknown_values(config):
    with pytest.raises(ValidationError):
        FluidConfig(**config)


@pytest.mark.parametrize("steps", [0, -1, 201, 1.5, True])
def test_invalid_step_count_does_not_advance(steps):
    sim = FluidSimulation(quiet_config())
    with pytest.raises(ValueError):
        sim.step(steps)
    assert sim.time == 0


def obstacle_spec(**updates):
    return {"name": "body", "shape": "box", "x": 0.5, "y": 0.5,
            "width": 0.4, "height": 0.2, "angle": 0.0, **updates}


def test_explicit_geometry_rotates_and_legacy_configuration_still_works():
    horizontal = FluidSimulation(FluidConfig(resolution=64, obstacles=[obstacle_spec()]))
    vertical = FluidSimulation(FluidConfig(resolution=64, obstacles=[obstacle_spec(angle=90.0)]))
    assert np.array_equal(horizontal.obstacle.T, vertical.obstacle)
    legacy = FluidSimulation(FluidConfig(resolution=64))
    circle = FluidSimulation(FluidConfig(resolution=64, obstacles=[obstacle_spec(
        shape="circle", x=0.45, width=0.2,
    )]))
    assert np.array_equal(legacy.obstacle, circle.obstacle)
    assert not FluidSimulation(FluidConfig(obstacles=[])).obstacle.any()


@pytest.mark.parametrize("shape", ["circle", "box", "ellipse", "naca0012", "naca2412", "polygon"])
def test_obstacle_shapes_block_faces_and_publish_contained_outlines(shape):
    body = obstacle_spec(shape=shape, angle=18.0, points=[[-0.5, -0.5], [0.5, -0.5], [0.0, 0.5]] if shape == "polygon" else None)
    sim = FluidSimulation(FluidConfig(resolution=64, iterations=200, obstacles=[body]))
    state = sim.step(8)
    assert sim.obstacle.sum() >= 4
    assert np.all(sim.u[:, 1:-1][~sim.open_u] == 0)
    assert np.all(sim.v[1:-1, :][~sim.open_v] == 0)
    assert np.all(sim.density[sim.obstacle] == 0)
    outline = state["obstacle_outlines"][0]
    assert outline["name"] == "body"
    points = np.asarray(outline["points"])
    assert len(points) >= 3
    assert np.all((points > 0) & (points < 1))
    assert state["metrics"]["divergence_rms"] < 0.03


def test_naca_camber_and_rotation_are_resolved_in_geometry():
    symmetric = FluidSimulation(FluidConfig(resolution=128, obstacles=[obstacle_spec(shape="naca0012", width=0.6)]))
    cambered = FluidSimulation(FluidConfig(resolution=128, obstacles=[obstacle_spec(shape="naca2412", width=0.6)]))
    assert np.array_equal(symmetric.obstacle, symmetric.obstacle[::-1])
    assert cambered.y[cambered.obstacle].mean() > 0.5
    tilted = FluidSimulation(FluidConfig(resolution=128, obstacles=[obstacle_spec(shape="naca0012", width=0.6, angle=25.0)]))
    assert np.cov(tilted.x[tilted.obstacle], tilted.y[tilted.obstacle])[0, 1] > 0


@pytest.mark.parametrize("bodies", [
    [obstacle_spec(), obstacle_spec()],
    [obstacle_spec(width=0.9, height=0.9, angle=45.0)],
    [obstacle_spec(shape="circle", width=0.01)],
    [obstacle_spec(shape="circle", x=0.105, width=0.2)],
    [obstacle_spec(shape="polygon", points=[[-0.5, -0.5], [0.5, 0.5], [-0.5, 0.5], [0.5, -0.5]])],
    [obstacle_spec(shape="polygon", points=[[-0.5, -0.5], [0.5, 0.5], [-0.5, 0.5], [0.3, -0.5]])],
    [obstacle_spec(shape="polygon", points=[[-0.5, 0.0], [0.0, 0.0], [0.5, 0.0]])],
    [obstacle_spec(shape="polygon", points=[[-0.6, -0.5], [0.5, -0.5], [0.0, 0.5]])],
    [obstacle_spec(shape="polygon", points=None)],
])
def test_invalid_obstacles_are_rejected_at_config_boundary(bodies):
    with pytest.raises(ValidationError):
        FluidConfig(resolution=32, obstacles=bodies)


def test_multiple_obstacles_and_rake_are_reproducible():
    config = FluidConfig(resolution=64, obstacles=[
        obstacle_spec(name="upper", x=0.55, y=0.7, width=0.2, height=0.15),
        obstacle_spec(name="lower", shape="ellipse", x=0.45, y=0.3, width=0.2, height=0.15),
    ], source_mode="rake", iterations=200)
    sim = FluidSimulation(config)
    rows = np.flatnonzero(sim.source.any(axis=1))
    groups = np.split(rows, np.flatnonzero(np.diff(rows) > 1) + 1)
    assert len(groups) == 9
    initial = sim.snapshot()
    stepped = sim.step(10)
    assert np.sum(stepped["density"]) > 0
    assert len(stepped["obstacle_outlines"]) == 2
    assert sim.reset() == initial
    assert sim.step(10) == stepped


def test_snapshot_diagnostics_match_velocity_and_pressure_gauge():
    sim = FluidSimulation(FluidConfig(resolution=32, iterations=200))
    state = sim.step(10)
    for name in ("speed", "vorticity", "pressure_correction"):
        field = np.asarray(state[name])
        assert field.shape == (32, 32)
        assert np.isfinite(field).all()
        assert np.all(field[sim.obstacle] == 0)
    assert np.asarray(state["pressure_correction"])[sim.fluid].mean() == pytest.approx(0, abs=1e-12)
    np.testing.assert_allclose(state["speed"], np.hypot(state["u"], state["v"]))
    json.dumps(state, allow_nan=False)
    quiet = FluidSimulation(quiet_config())
    quiet.u[:] = -quiet._uy
    quiet.v[:] = quiet._vx
    np.testing.assert_allclose(quiet.snapshot()["vorticity"], 2.0, atol=1e-12)


def test_diffusion_does_not_lose_uniform_dye_into_solid_obstacle():
    sim = FluidSimulation(quiet_config(obstacle=True, diffusion=0.1))
    sim.density[sim.fluid] = 1.0
    sim.step(4)
    np.testing.assert_allclose(sim.density[sim.fluid], 1.0, atol=1e-10)
    assert np.all(sim.density[sim.obstacle] == 0)
