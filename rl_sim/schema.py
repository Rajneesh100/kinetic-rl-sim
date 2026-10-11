"""Portable SI-unit scene configuration. Coordinates are z-up; angles are radians."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Finite = Annotated[float, Field(allow_inf_nan=False)]
Vector3 = Annotated[list[Annotated[Finite, Field(ge=-1e6, le=1e6)]], Field(min_length=3, max_length=3)]
Size3 = Annotated[list[Annotated[Finite, Field(gt=0, le=1000)]], Field(min_length=3, max_length=3)]
Color = Annotated[list[Annotated[Finite, Field(ge=0, le=1)]], Field(min_length=4, max_length=4)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)


class PhysicsConfig(StrictModel):
    gravity: Vector3 = Field(default_factory=lambda: [0.0, 0.0, -9.81])
    timestep: Finite = Field(default=.005, ge=.0001, le=.02)
    substeps: int = Field(default=4, ge=1, le=100)
    iterations: int = Field(default=50, ge=1, le=500)
    integrator: Literal["implicitfast", "Euler", "RK4", "implicit"] = "implicitfast"
    solver: Literal["Newton", "CG", "PGS"] = "Newton"
    tolerance: Finite = Field(default=1e-8, ge=1e-12, le=.1)
    friction: Finite = Field(default=1.0, ge=0, le=10)
    friction_torsional: Finite = Field(default=.005, ge=0, le=10)
    friction_rolling: Finite = Field(default=.0001, ge=0, le=10)
    contact_dimension: Literal[1, 3, 4, 6] = Field(default=6, description="1 frictionless; 3 sliding; 4 adds torsional; 6 adds rolling friction.")
    contact_timeconst: Finite = Field(default=.01, ge=.0001, le=1)
    contact_dampratio: Finite = Field(default=1.0, ge=.01, le=10)
    density: Finite = Field(default=1.225, ge=0, le=2000)
    viscosity: Finite = Field(default=.0000181, ge=0, le=100)
    wind: Vector3 = Field(default_factory=lambda: [0.0, 0.0, 0.0])


class TerrainConfig(StrictModel):
    kind: Literal["flat", "rough", "stairs"] = "flat"
    size: Annotated[list[Annotated[Finite, Field(ge=2, le=500)]], Field(min_length=2, max_length=2)] = Field(default_factory=lambda: [40.0, 40.0])
    roughness: Finite = Field(default=.15, ge=0, le=2)
    seed: int = Field(default=0, ge=0, le=4294967295)


class RobotConfig(StrictModel):
    kind: Literal["car", "quadruped", "aircraft", "none"] = "car"
    position: Vector3 = Field(default_factory=lambda: [0.0, 0.0, .7])
    rotation: Vector3 = Field(default_factory=lambda: [0.0, 0.0, 0.0], description="Initial XYZ Euler angles, radians.")
    velocity: Vector3 = Field(default_factory=lambda: [0.0, 0.0, 0.0], description="Initial world-frame linear velocity, metres per second.")
    angular_velocity: Vector3 = Field(default_factory=lambda: [0.0, 0.0, 0.0], description="Initial body-frame angular velocity, radians per second.")
    mass: Finite = Field(default=8.0, ge=.05, le=10000)
    motor_strength: Finite = Field(default=20.0, gt=0, le=10000)
    aero_coefficients: Annotated[list[Annotated[Finite, Field(ge=0, le=100)]], Field(min_length=5, max_length=5)] = Field(default_factory=lambda: [.5, .25, 1.5, 1.0, 1.0], description="Ellipsoid aerodynamic coefficients: blunt drag, slender drag, angular drag, Kutta lift, Magnus lift.")


class ObjectConfig(StrictModel):
    name: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z][A-Za-z0-9 _.-]*$")
    kind: Literal["box", "sphere", "cylinder", "capsule"] = "box"
    size: Size3 = Field(default_factory=lambda: [.5, .5, .5], description="MuJoCo sizes: box half-extents; sphere radius=size[0]; cylinder/capsule radius=size[0], half-length=size[1].")
    position: Vector3 = Field(default_factory=lambda: [0.0, 0.0, .5])
    rotation: Vector3 = Field(default_factory=lambda: [0.0, 0.0, 0.0], description="XYZ Euler angles, radians.")
    mass: Finite = Field(default=1.0, ge=.001, le=100000)
    static: bool = False
    color: Color = Field(default_factory=lambda: [.35, .64, .96, 1.0])


class SceneConfig(StrictModel):
    name: str = Field(default="Untitled world", min_length=1, max_length=120)
    robot: RobotConfig = Field(default_factory=RobotConfig)
    physics: PhysicsConfig = Field(default_factory=PhysicsConfig)
    terrain: TerrainConfig = Field(default_factory=TerrainConfig)
    objects: list[ObjectConfig] = Field(default_factory=list, max_length=200)
    max_episode_steps: int = Field(default=2000, ge=1, le=1000000)

    @model_validator(mode="after")
    def unique_object_names(self):
        names = [obj.name for obj in self.objects]
        if len(set(names)) != len(names):
            raise ValueError("Object names must be unique")
        if any(name.startswith("robot_") or name.startswith("terrain_") for name in names):
            raise ValueError("Prefixes robot_ and terrain_ are reserved for engine geometry")
        return self
