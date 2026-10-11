"""Native MuJoCo rigid-body simulation, with a small JSON-friendly RL boundary.

The scripted controllers are demonstrations, not trained policies. Aircraft fluid
forces are MuJoCo's ellipsoid approximation, not computational fluid dynamics.
"""
from __future__ import annotations

import math
from numbers import Real
from xml.etree.ElementTree import Element, SubElement, tostring

import mujoco
import numpy as np

from .schema import SceneConfig


def _numbers(values) -> str:
    return " ".join(format(float(value), ".12g") for value in values)


def _geom(parent, name, kind, size, **kwargs):
    attrs = {"name": name, "type": kind, "size": _numbers(size)}
    attrs.update({key: _numbers(value) if isinstance(value, (list, tuple, np.ndarray)) else str(value) for key, value in kwargs.items()})
    return SubElement(parent, "geom", attrs)


def _terrain(world, scene, seed):
    terrain = scene.terrain
    _geom(world, "terrain_floor", "plane", [terrain.size[0] / 2, terrain.size[1] / 2, .1], rgba=[.29, .35, .40, 1])
    if terrain.kind == "rough":
        rng = np.random.default_rng(seed)
        # Colliding boxes keep the exported visual geometry identical to physics.
        # A clear start zone avoids spawning the robot inside a random obstacle.
        nx = ny = 12
        dx, dy = terrain.size[0] / nx / 2, terrain.size[1] / ny / 2
        for ix in range(nx):
            for iy in range(ny):
                x = -terrain.size[0] / 2 + (2 * ix + 1) * dx
                y = -terrain.size[1] / 2 + (2 * iy + 1) * dy
                height = rng.uniform(0, terrain.roughness)
                if (abs(x) < dx + 1 and abs(y) < dy + 1) or height < .001:
                    continue
                _geom(world, f"terrain_tile_{ix}_{iy}", "box", [dx, dy, height / 2], pos=[x, y, height / 2], rgba=[.34, .40, .42, 1])
    elif terrain.kind == "stairs" and terrain.roughness > 0:
        for index in range(10):
            height = terrain.roughness * (index + 1)
            _geom(world, f"terrain_step_{index}", "box", [.4, min(terrain.size[1] / 2, 3), height / 2], pos=[2.4 + .8 * index, 0, height / 2], rgba=[.43, .49, .54, 1])


def _car(body, actuators, mass, strength):
    _geom(body, "robot_chassis", "box", [.78, .36, .13], mass=mass * .56, rgba=[.17, .42, .93, 1])
    _geom(body, "robot_cabin", "box", [.32, .31, .15], pos=[-.16, 0, .26], mass=mass * .08, rgba=[.09, .17, .27, 1])
    _geom(body, "robot_roof", "box", [.33, .32, .025], pos=[-.16, 0, .43], mass=mass * .015, rgba=[.26, .58, 1, 1])
    _geom(body, "robot_hood", "box", [.2, .335, .025], pos=[.52, 0, .16], mass=mass * .015, rgba=[.25, .53, .98, 1])
    for y in [-.24, .24]:
        _geom(body, f"robot_headlight_{y}", "box", [.015, .08, .045], pos=[.795, y, .04], mass=0, contype=0, conaffinity=0, rgba=[.98, .95, .72, 1])
    # Wheel clearance includes the swept tire volume at full steering lock.
    for index, (x, y) in enumerate([(.55, -.56), (.55, .56), (-.55, -.56), (-.55, .56)]):
        parent = body
        wheel_position = [x, y, -.15]
        if index < 2:
            parent = SubElement(body, "body", name=f"robot_steering_{index}", pos=_numbers(wheel_position))
            SubElement(parent, "joint", name=f"robot_steer_{index}", type="hinge", axis="0 0 1", range="-.55 .55", damping="1")
            _geom(parent, f"robot_knuckle_{index}", "sphere", [.04], mass=mass * .005, rgba=[.2, .24, .3, 1], contype=0, conaffinity=0)
            SubElement(actuators, "position", name=f"steering_{index}", joint=f"robot_steer_{index}", kp="100", kv="8", ctrlrange="-.5 .5", forcerange=_numbers([-strength * 3, strength * 3]))
            wheel_position = [0, 0, 0]
        wheel = SubElement(parent, "body", name=f"robot_wheel_body_{index}", pos=_numbers(wheel_position))
        SubElement(wheel, "joint", name=f"robot_wheel_joint_{index}", type="hinge", axis="0 1 0", damping=".03", armature=".015")
        _geom(wheel, f"robot_tire_{index}", "cylinder", [.23, .085], euler=[math.pi / 2, 0, 0], mass=mass * .08, rgba=[.075, .09, .12, 1])
        _geom(wheel, f"robot_hub_{index}", "cylinder", [.105, .086], euler=[math.pi / 2, 0, 0], mass=0, rgba=[.67, .74, .83, 1], contype=0, conaffinity=0)
        SubElement(actuators, "motor", name=f"drive_{index}", joint=f"robot_wheel_joint_{index}", gear=str(strength), ctrlrange="-1 1")


def _quadruped(body, actuators, mass, strength):
    _geom(body, "robot_torso", "box", [.42, .19, .115], mass=mass * .65, rgba=[.91, .70, .24, 1])
    _geom(body, "robot_head", "box", [.10, .15, .08], pos=[.5, 0, .05], mass=mass * .03, rgba=[.15, .22, .30, 1])
    _geom(body, "robot_sensor", "sphere", [.035], pos=[.605, 0, .06], mass=0, rgba=[.19, .85, .9, 1], contype=0, conaffinity=0)
    for index, (x, y) in enumerate([(.32, -.25), (.32, .25), (-.32, -.25), (-.32, .25)]):
        upper = SubElement(body, "body", name=f"robot_upper_{index}", pos=_numbers([x, y, 0]))
        SubElement(upper, "joint", name=f"robot_hip_{index}", type="hinge", axis="0 1 0", range="-1.4 1.4", damping=".8", armature=".02")
        _geom(upper, f"robot_thigh_{index}", "capsule", [.045], fromto="0 0 0 0 0 -.25", mass=mass * .04, rgba=[.25, .31, .38, 1])
        lower = SubElement(upper, "body", name=f"robot_lower_{index}", pos="0 0 -.25")
        SubElement(lower, "joint", name=f"robot_knee_{index}", type="hinge", axis="0 1 0", range="-.1 2.4", damping=".7", armature=".02")
        _geom(lower, f"robot_shin_{index}", "capsule", [.035], fromto="0 0 0 0 0 -.25", mass=mass * .03, rgba=[.69, .73, .79, 1])
        _geom(lower, f"robot_foot_{index}", "sphere", [.055], pos=[0, 0, -.25], mass=mass * .01, rgba=[.12, .16, .2, 1])
        for joint, limits in [(f"robot_hip_{index}", "-1.4 1.4"), (f"robot_knee_{index}", "-.1 2.4")]:
            SubElement(actuators, "position", name=f"act_{joint}", joint=joint, kp=str(strength * 6), kv=str(math.sqrt(strength) * 1.5), ctrlrange=limits, forcerange=_numbers([-strength, strength]))


def _aircraft(body, mass, coefficients):
    aero = {"fluidshape": "ellipsoid", "fluidcoef": _numbers(coefficients)}
    _geom(body, "robot_fuselage", "ellipsoid", [.8, .12, .13], mass=mass * .5, rgba=[.85, .9, .96, 1], **aero)
    _geom(body, "robot_wing", "ellipsoid", [.28, 1.5, .025], pos=[.05, 0, 0], euler=[0, -.06, 0], mass=mass * .3, rgba=[.22, .56, .97, 1], **aero)
    _geom(body, "robot_tailplane", "ellipsoid", [.18, .48, .018], pos=[-.67, 0, .06], mass=mass * .12, rgba=[.23, .57, .97, 1], **aero)
    _geom(body, "robot_fin", "ellipsoid", [.16, .025, .24], pos=[-.65, 0, .22], mass=mass * .05, rgba=[.23, .57, .97, 1], **aero)
    _geom(body, "robot_nose", "sphere", [.13], pos=[.78, 0, 0], mass=mass * .03, rgba=[.95, .62, .19, 1], **aero)


def compile_scene(scene: SceneConfig, seed: int | None = None) -> str:
    """Compile validated scene data to explicit, portable MJCF (no external assets)."""
    root = Element("mujoco", model=scene.name)
    SubElement(root, "compiler", angle="radian", autolimits="true")
    physics = scene.physics
    option = SubElement(root, "option", timestep=str(physics.timestep), gravity=_numbers(physics.gravity), iterations=str(physics.iterations), integrator=physics.integrator, solver=physics.solver, tolerance=str(physics.tolerance), cone="elliptic", density=str(physics.density), viscosity=str(physics.viscosity), wind=_numbers(physics.wind))
    SubElement(option, "flag", energy="enable")
    defaults = SubElement(root, "default")
    SubElement(defaults, "geom", friction=_numbers([physics.friction, physics.friction_torsional, physics.friction_rolling]), solref=_numbers([physics.contact_timeconst, physics.contact_dampratio]), solimp=".9 .95 .001", condim=str(physics.contact_dimension))
    world = SubElement(root, "worldbody")
    _terrain(world, scene, scene.terrain.seed if seed is None else seed)
    for obj in scene.objects:
        body = SubElement(world, "body", name=f"object_{obj.name}", pos=_numbers(obj.position), euler=_numbers(obj.rotation))
        if not obj.static:
            SubElement(body, "freejoint", name=f"free_{obj.name}")
        used_sizes = obj.size if obj.kind == "box" else obj.size[:1 if obj.kind == "sphere" else 2]
        _geom(body, obj.name, obj.kind, used_sizes, mass=obj.mass, rgba=obj.color)
    actuators = SubElement(root, "actuator")
    robot = scene.robot
    if robot.kind != "none":
        body = SubElement(world, "body", name="robot", pos=_numbers(robot.position), euler=_numbers(robot.rotation))
        SubElement(body, "freejoint", name="robot_free")
        if robot.kind == "car":
            _car(body, actuators, robot.mass, robot.motor_strength)
        elif robot.kind == "quadruped":
            _quadruped(body, actuators, robot.mass, robot.motor_strength)
        else:
            _aircraft(body, robot.mass, robot.aero_coefficients)
    return tostring(root, encoding="unicode")


_ACTIONS = {
    "car": ["throttle", "steer"],
    "quadruped": [f"{leg}_{joint}" for leg in ["front_right", "front_left", "rear_right", "rear_left"] for joint in ["hip", "knee"]],
    "aircraft": ["throttle", "roll", "pitch", "yaw"],
    "none": [],
}
_GEOM_TYPES = {int(getattr(mujoco.mjtGeom, "mjGEOM_" + name.upper())): name for name in ["plane", "box", "sphere", "capsule", "cylinder", "ellipsoid"]}


class Simulation:
    def __init__(self, scene: SceneConfig):
        self.scene = SceneConfig.model_validate(scene.model_dump(mode="python"))
        self._seed = self.scene.terrain.seed
        self._build()
        self.reset()

    def _build(self):
        self.xml = compile_scene(self.scene, self._seed)
        self.model = mujoco.MjModel.from_xml_string(self.xml)
        self.data = mujoco.MjData(self.model)
        self._geom_metadata = [
            {"id": index, "name": mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_GEOM, index) or f"geom_{index}", "type": _GEOM_TYPES[int(self.model.geom_type[index])], "size": self.model.geom_size[index].tolist(), "rgba": self.model.geom_rgba[index].astype(float).tolist()}
            for index in range(self.model.ngeom)
        ]
        self._robot_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "robot")
        self._root_qpos = self._root_dof = None
        if self._robot_id >= 0:
            joint = self.model.body_jntadr[self._robot_id]
            self._root_qpos = int(self.model.jnt_qposadr[joint])
            self._root_dof = int(self.model.jnt_dofadr[joint])

    def description(self) -> dict:
        names = _ACTIONS[self.scene.robot.kind]
        return {"action_size": len(names), "observation_size": self.model.nq + self.model.nv + 1, "action_names": list(names), "dt": self.scene.physics.timestep * self.scene.physics.substeps, "backend": f"mujoco-{mujoco.__version__}", "observation_layout": [{"name": "time", "start": 0, "length": 1}, {"name": "qpos", "start": 1, "length": self.model.nq}, {"name": "qvel", "start": self.model.nq + 1, "length": self.model.nv}]}

    def reset(self, seed: int | None = None, *, include_geoms: bool = True) -> dict:
        if seed is not None:
            if type(seed) is not int or not 0 <= seed <= 4294967295:
                raise ValueError("seed must be an integer between 0 and 4294967295")
            if seed != self._seed and self.scene.terrain.kind == "rough":
                self._seed = seed
                self._build()
            self._seed = seed
        mujoco.mj_resetData(self.model, self.data)
        if self.scene.robot.kind == "quadruped":
            for index in range(4):
                for kind, position in [("hip", -.25), ("knee", .65)]:
                    joint = self.model.joint(f"robot_{kind}_{index}").id
                    self.data.qpos[self.model.jnt_qposadr[joint]] = position
        if self._root_dof is not None:
            self.data.qvel[self._root_dof:self._root_dof + 3] = self.scene.robot.velocity
            self.data.qvel[self._root_dof + 3:self._root_dof + 6] = self.scene.robot.angular_velocity
        self._step = 0
        self._reward = 0.0
        self._terminated = self._truncated = False
        self._last_action = np.zeros(len(_ACTIONS[self.scene.robot.kind]))
        self._apply_action(self._last_action)
        mujoco.mj_forward(self.model, self.data)
        self._origin = self._position().copy()
        return self.snapshot(include_geoms=include_geoms)

    def _position(self):
        return self.data.xpos[self._robot_id] if self._robot_id >= 0 else np.zeros(3)

    def _apply_action(self, action):
        kind = self.scene.robot.kind
        if kind == "car":
            for index in range(4):
                self.data.ctrl[self.model.actuator(f"drive_{index}").id] = action[0]
            for index in range(2):
                self.data.ctrl[self.model.actuator(f"steering_{index}").id] = .5 * action[1]
        elif kind == "quadruped":
            self.data.ctrl[:] = [(-.25 + .65 * value) if index % 2 == 0 else (.65 + .75 * value) for index, value in enumerate(action)]
        elif kind == "aircraft":
            rotation = self.data.xmat[self._robot_id].reshape(3, 3)
            strength = self.scene.robot.motor_strength
            self.data.xfrc_applied[self._robot_id, :3] = rotation @ np.array([strength * (action[0] + 1) / 2, 0, 0])
            # Approximate control authority, in N m, with sufficient pitch moment
            # to trim the model's ellipsoid aerodynamic forces at cruise speed.
            self.data.xfrc_applied[self._robot_id, 3:] = rotation @ (np.array(action[1:]) * strength * np.array([.4, .8, .2]))

    def step(self, action: list[float], frames: int | None = None, *, include_geoms: bool = True) -> dict:
        if self._terminated or self._truncated:
            raise RuntimeError("Episode is finished; call reset before stepping again")
        count = len(_ACTIONS[self.scene.robot.kind])
        if not isinstance(action, (list, tuple, np.ndarray)) or len(action) != count:
            raise ValueError(f"Expected {count} normalized actions")
        if any(isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not math.isfinite(value) or not -1 <= value <= 1 for value in action):
            raise ValueError("Actions must be finite numbers in [-1, 1]")
        frames = self.scene.physics.substeps if frames is None else frames
        if type(frames) is not int or not 1 <= frames <= 100:
            raise ValueError("frames must be an integer between 1 and 100")
        previous = self._position().copy()
        self._last_action = np.asarray(action, dtype=float)
        previous_time = float(self.data.time)
        warnings_before = self.data.warning.number.copy()
        for _ in range(frames):
            self._apply_action(self._last_action)
            mujoco.mj_step(self.model, self.data)
        # mj_step integrates qpos after computing geom_xpos; forward synchronizes
        # the rendered geometry, contacts, energies and velocities with that qpos.
        mujoco.mj_forward(self.model, self.data)
        self._step += 1
        position = self._position()
        finite = np.isfinite(self.data.qpos).all() and np.isfinite(self.data.qvel).all()
        unstable = not finite or self.data.time < previous_time or any(self.data.warning.number[i] > warnings_before[i] for i in [mujoco.mjtWarning.mjWARN_BADQPOS, mujoco.mjtWarning.mjWARN_BADQVEL, mujoco.mjtWarning.mjWARN_BADQACC])
        kind = self.scene.robot.kind
        fallen = False
        if self._robot_id >= 0:
            upright = self.data.xmat[self._robot_id].reshape(3, 3)[2, 2]
            fallen = (kind == "quadruped" and (position[2] < .22 or upright < .25)) or (kind == "car" and (position[2] < .12 or upright < .1)) or (kind == "aircraft" and position[2] < .25)
        outside = self._robot_id >= 0 and (abs(position[0]) > self.scene.terrain.size[0] / 2 or abs(position[1]) > self.scene.terrain.size[1] / 2 or position[2] > 500 or position[2] < -10)
        self._terminated = bool(unstable or fallen or outside)
        self._truncated = bool(self._step >= self.scene.max_episode_steps and not self._terminated)
        if not finite:
            # Preserve a finite, terminal response rather than leaking invalid JSON.
            mujoco.mj_resetData(self.model, self.data)
            mujoco.mj_forward(self.model, self.data)
        velocity_reward = (position[0] - previous[0]) / (frames * self.scene.physics.timestep)
        self._reward = float(velocity_reward - .01 * np.square(self._last_action).sum() - (5 if self._terminated else 0)) if kind != "none" else 0.0
        if not math.isfinite(self._reward):
            self._reward = -5.0
        return self.snapshot(include_geoms=include_geoms)

    def snapshot(self, *, include_geoms: bool = True) -> dict:
        position = self._position()
        speed = float(np.linalg.norm(self.data.qvel[self._root_dof:self._root_dof + 3])) if self._root_dof is not None else 0.0
        geoms = []
        for metadata in self._geom_metadata if include_geoms else []:
            index = metadata["id"]
            quaternion = np.zeros(4)
            mujoco.mju_mat2Quat(quaternion, self.data.geom_xmat[index])
            geoms.append({**metadata, "position": self.data.geom_xpos[index].tolist(), "quaternion": quaternion.tolist(), "size": metadata["size"].copy(), "rgba": metadata["rgba"].copy()})
        return {"time": float(self.data.time), "step": self._step, "observation": np.concatenate([[self.data.time], self.data.qpos, self.data.qvel]).tolist(), "reward": self._reward, "terminated": self._terminated, "truncated": self._truncated, "info": {"speed": speed, "height": float(position[2]), "distance": float(np.linalg.norm(position[:2] - self._origin[:2])), "contacts": int(self.data.ncon), "energy": float(self.data.energy.sum())}, "geoms": geoms}

    def demo_action(self) -> list[float]:
        time = float(self.data.time)
        kind = self.scene.robot.kind
        if kind == "car":
            # A gentle corridor drive; external policies can supply arbitrary actions.
            return [.22, .10 * math.sin(time * .65)]
        if kind == "quadruped":
            phase = 2 * math.pi * 1.3 * time
            return [value for offset in [0, math.pi, math.pi, 0] for value in [.22 * math.sin(phase + offset), .16 * max(0, math.sin(phase + offset))]]
        if kind == "aircraft":
            matrix = self.data.xmat[self._robot_id].reshape(3, 3)
            roll = math.atan2(matrix[2, 1], matrix[2, 2])
            pitch = math.asin(np.clip(-matrix[2, 0], -1, 1))
            omega = self.data.qvel[self._root_dof + 3:self._root_dof + 6]
            # Trim + attitude PD for this template only; this is not a learned
            # policy or a controller calibrated to arbitrary aircraft parameters.
            return np.clip([.4, -3 * roll - 1.3 * omega[0], .6 - 3 * (pitch + .02) - 1.3 * omega[1], -1.3 * omega[2]], -1, 1).tolist()
        return []
