"""Physical and episode contracts, using the real native MuJoCo engine."""
import json

import mujoco
import numpy as np
import pytest
from pydantic import ValidationError

from rl_sim.engine import Simulation
from rl_sim.schema import SceneConfig
from rl_sim.scenes import get_template, templates


@pytest.mark.parametrize("patch", [
    {"unexpected": 1},
    {"physics": {"gravity": [0, 0, float("nan")]}},
    {"physics": {"timestep": 0}},
    {"physics": {"friction": -1}},
    {"objects": [{"name": "bad", "size": [0, 1, 1]}]},
    {"objects": [{"name": "same"}, {"name": "same"}]},
])
def test_scene_rejects_invalid_physics_and_ambiguous_names(patch):
    with pytest.raises(ValidationError):
        SceneConfig.model_validate(patch)


@pytest.mark.parametrize("template_id,action_size", [
    ("driving", 2), ("quadruped", 8), ("flight", 4), ("sandbox", 0),
])
def test_templates_compile_and_rollout_finitely(template_id, action_size):
    sim = Simulation(get_template(template_id))
    description = sim.description()
    assert description["action_size"] == action_size
    assert description["backend"].startswith("mujoco")
    for _ in range(400):
        state = sim.step(sim.demo_action())
        assert np.isfinite(state["observation"]).all()
        assert len(state["observation"]) == description["observation_size"]
        assert all(np.isfinite(list(state["info"].values())))
        json.dumps(state, allow_nan=False)
        if state["terminated"] or state["truncated"]:
            sim.reset()
    assert {x["id"] for x in templates()} == {"driving", "quadruped", "flight", "sandbox"}


def test_gravity_drops_free_body_and_floor_stops_it():
    scene = SceneConfig.model_validate({
        "robot": {"kind": "none"},
        "physics": {"density": 0, "viscosity": 0},
        "objects": [{"name": "ball", "kind": "sphere", "size": [.2, .2, .2], "position": [0, 0, 2]}],
    })
    sim = Simulation(scene)
    initial_height = next(g["position"][2] for g in sim.snapshot()["geoms"] if g["name"] == "ball")
    for _ in range(10):
        state = sim.step([])
    height = next(g["position"][2] for g in state["geoms"] if g["name"] == "ball")
    assert initial_height - .3 < height < initial_height - .1
    for _ in range(150):
        state = sim.step([])
    height = next(g["position"][2] for g in state["geoms"] if g["name"] == "ball")
    assert .18 < height < .22
    assert state["info"]["contacts"] > 0


def test_actions_drive_car_and_steering_changes_heading():
    straight = Simulation(get_template("driving"))
    turning = Simulation(get_template("driving"))
    for _ in range(120):
        a = straight.step([.35, 0])
        b = turning.step([.35, .6])
    assert a["info"]["distance"] > 1.0
    straight_position = straight.data.body("robot").xpos
    turning_position = turning.data.body("robot").xpos
    assert abs(straight_position[1]) < .1
    assert abs(turning_position[1]) > .2
    assert np.linalg.norm(straight.data.body("robot").xquat - turning.data.body("robot").xquat) > .05


def test_aircraft_thrust_and_control_torque_change_physical_state():
    neutral = Simulation(get_template("flight"))
    commanded = Simulation(get_template("flight"))
    for _ in range(10):
        neutral.step([-1, 0, 0, 0])
        commanded.step([1, .5, .2, 0])
    assert commanded.data.qvel[0] > neutral.data.qvel[0] + .2
    assert np.linalg.norm(commanded.data.qvel[3:6] - neutral.data.qvel[3:6]) > .05


def test_flight_demo_maintains_airborne_forward_flight_for_eight_seconds():
    sim = Simulation(get_template("flight"))
    for _ in range(400):
        state = sim.step(sim.demo_action(), include_geoms=False)
        assert not state["terminated"]
    assert state["info"]["height"] > 5
    assert state["info"]["distance"] > 50
    assert abs(sim.data.body("robot").xpos[1]) < 1


def test_seed_replays_terrain_and_dynamic_trajectory():
    config = get_template("quadruped").model_dump()
    config["terrain"].update(kind="rough", roughness=.1)
    sim = Simulation(SceneConfig.model_validate(config))
    first = sim.reset(seed=17)
    for _ in range(12):
        a = sim.step([.1] * 8)
    second = sim.reset(seed=17)
    for _ in range(12):
        b = sim.step([.1] * 8)
    assert first == second
    assert a == b
    other = sim.reset(seed=18)
    assert [g["position"] for g in other["geoms"]] != [g["position"] for g in first["geoms"]]


@pytest.mark.parametrize("action", [[0], [0, 2], [0, float("nan")], [0, float("inf")], ["1", 0]])
def test_invalid_action_is_rejected_without_advancing(action):
    sim = Simulation(get_template("driving"))
    before = sim.snapshot()
    with pytest.raises(ValueError):
        sim.step(action)
    assert sim.snapshot() == before


def test_episode_limit_is_truncation_and_requires_reset():
    scene = get_template("driving").model_dump()
    scene["max_episode_steps"] = 2
    sim = Simulation(SceneConfig.model_validate(scene))
    assert not sim.step([0, 0])["truncated"]
    final = sim.step([0, 0])
    assert final["truncated"] and not final["terminated"]
    with pytest.raises(RuntimeError, match="reset"):
        sim.step([0, 0])
    reset = sim.reset()
    assert reset["step"] == 0 and reset["time"] == 0
    assert not reset["truncated"] and not reset["terminated"]
    assert reset["reward"] == 0


def test_fallen_quadruped_is_terminated():
    sim = Simulation(get_template("quadruped"))
    sim.data.qpos[2] = .1
    state = sim.step([0] * 8, frames=1)
    assert state["terminated"] and not state["truncated"]


def test_snapshot_geom_transforms_are_current_after_integration():
    sim = Simulation(get_template("sandbox"))
    state = sim.step([])
    for geom in state["geoms"]:
        assert geom["position"] == pytest.approx(sim.data.geom_xpos[geom["id"]])
        assert np.linalg.norm(geom["quaternion"]) == pytest.approx(1)
    assert state["time"] == pytest.approx(.02)


def test_training_can_omit_geometry_without_changing_observation_or_dynamics():
    rendered = Simulation(get_template("driving"))
    training = Simulation(get_template("driving"))
    assert training.reset(include_geoms=False)["geoms"] == []
    for _ in range(5):
        expected = rendered.step([.2, .1])
        actual = training.step([.2, .1], include_geoms=False)
        assert actual["geoms"] == []
        expected["geoms"] = []
        assert expected == actual
    assert training.snapshot()["geoms"]


@pytest.mark.parametrize("frames", [0, 101, 1.5, True])
def test_invalid_substep_override_does_not_advance(frames):
    sim = Simulation(get_template("driving"))
    with pytest.raises(ValueError):
        sim.step([0, 0], frames=frames)
    assert sim.snapshot()["time"] == 0


def test_custom_solver_contact_and_aerodynamics_reach_native_model():
    config = get_template("flight").model_dump()
    config["physics"].update(
        integrator="RK4", solver="CG", tolerance=.00002,
        friction_torsional=.012, friction_rolling=.003,
        contact_timeconst=.03, contact_dampratio=.8,
        gravity=[0, 0, -3], wind=[1, 2, 0], iterations=72,
    )
    config["robot"]["aero_coefficients"] = [.7, .3, 1.7, .8, .9]
    sim = Simulation(SceneConfig.model_validate(config))
    assert sim.model.opt.integrator == mujoco.mjtIntegrator.mjINT_RK4
    assert sim.model.opt.solver == mujoco.mjtSolver.mjSOL_CG
    assert sim.model.opt.tolerance == pytest.approx(.00002)
    assert sim.model.opt.gravity == pytest.approx([0, 0, -3])
    assert sim.model.opt.wind == pytest.approx([1, 2, 0])
    assert sim.model.opt.iterations == 72
    assert sim.model.geom_friction[0] == pytest.approx([1, .012, .003])
    assert sim.model.geom_solref[0] == pytest.approx([.03, .8])
    wing_id = sim.model.geom("robot_wing").id
    assert sim.model.geom_fluid[wing_id, 1:6] == pytest.approx([.7, .3, 1.7, .8, .9])


@pytest.mark.parametrize("template_id", ["driving", "quadruped", "flight"])
def test_robot_mass_matches_total_assembled_mass(template_id):
    scene = get_template(template_id)
    sim = Simulation(scene)
    body = sim.model.body("robot").id
    assert sim.model.body_subtreemass[body] == pytest.approx(scene.robot.mass)


@pytest.mark.parametrize("patch", [
    {"physics": {"gravity": [0, 0, 1e308]}},
    {"physics": {"wind": [-1e308, 0, 0]}},
    {"robot": {"position": [1e308, 0, 1]}},
    {"robot": {"rotation": [0, 1e308, 0]}},
    {"robot": {"velocity": [0, 0, -1e308]}},
    {"robot": {"angular_velocity": [0, 0, 1e308]}},
    {"objects": [{"name": "Unsafe", "position": [0, 1e308, 0]}]},
    {"objects": [{"name": "Unsafe", "rotation": [1e308, 0, 0]}]},
])
def test_extreme_finite_vectors_are_rejected_before_native_compilation(patch):
    with pytest.raises(ValidationError):
        SceneConfig.model_validate(patch)


def test_configured_robot_pose_and_velocities_restore_on_reset_without_mutating_scene():
    config = get_template("driving").model_dump()
    config["robot"].update(
        rotation=[0, 0, np.pi / 2], velocity=[1, 2, .3],
        angular_velocity=[.1, .2, .3], position=[2, 3, 1],
    )
    scene = SceneConfig.model_validate(config)
    original = scene.model_dump()
    sim = Simulation(scene)
    initial = sim.snapshot()
    assert sim.data.body("robot").xpos == pytest.approx([2, 3, 1])
    assert sim.data.body("robot").xquat == pytest.approx([2 ** -.5, 0, 0, 2 ** -.5])
    assert sim.data.joint("robot_free").qvel == pytest.approx([1, 2, .3, .1, .2, .3])
    sim.step([.1, 0])
    restored = sim.reset(seed=41)
    assert restored == initial
    assert scene.model_dump() == original


def test_flight_initial_speed_is_configured_and_can_be_disabled():
    config = get_template("flight").model_dump()
    assert config["robot"]["velocity"] == [12, 0, 0]
    config["robot"]["velocity"] = [0, 0, 0]
    sim = Simulation(SceneConfig.model_validate(config))
    assert sim.data.joint("robot_free").qvel[:3] == pytest.approx([0, 0, 0])
