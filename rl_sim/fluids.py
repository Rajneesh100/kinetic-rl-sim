"""Independent 2-D incompressible channel flow on a staggered MAC grid.

Semi-Lagrangian advection, implicit diffusion and a conjugate-gradient pressure
projection provide a small educational flow model. This is not 3-D CFD and does
not supply aerodynamic forces to the rigid-body engine. Coordinates span a
unit square; arrays use rows from bottom to top and columns from left to right.
"""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .fluid_geometry import FluidObstacle, obstacle_mask, obstacle_outline


class FluidConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    resolution: int = Field(default=64, ge=16, le=128)
    timestep: float = Field(default=0.02, ge=0.001, le=0.1)
    viscosity: float = Field(default=0.0001, ge=0, le=0.1)
    diffusion: float = Field(default=0.00001, ge=0, le=0.1)
    inflow: float = Field(default=0.6, ge=0, le=3)
    dye_source: float = Field(default=2.0, ge=0, le=20)
    source_x: float = Field(default=0.12, ge=0, le=1)
    source_y: float = Field(default=0.5, ge=0, le=1)
    source_radius: float = Field(default=0.06, ge=0.01, le=0.3)
    source_mode: Literal["jet", "rake"] = Field(default="jet", description="Jet uses the circular source. Rake emits nine horizontal dye stripes near source_x, spanning y=0.1 to 0.9.")
    dissipation: float = Field(default=0.03, ge=0, le=5)
    obstacle: bool = True
    obstacle_x: float = Field(default=0.45, ge=0.05, le=0.95)
    obstacle_y: float = Field(default=0.5, ge=0.05, le=0.95)
    obstacle_radius: float = Field(default=0.1, ge=0.01, le=0.3)
    obstacles: list[FluidObstacle] | None = Field(default=None, max_length=16, description="Explicit obstacle objects. Null uses the legacy circle controls; an empty list creates a clean channel. Each object must occupy at least four grid cell centers and leave the outer cell ring fluid.")
    iterations: int = Field(default=60, ge=10, le=200)

    @model_validator(mode="after")
    def contained_obstacle(self):
        if self.obstacles is not None:
            names = [body.name for body in self.obstacles]
            if len(names) != len(set(names)):
                raise ValueError("Obstacle names must be unique")
            centers = (np.arange(self.resolution) + 0.5) / self.resolution
            x, y = np.meshgrid(centers, centers)
            for body in self.obstacles:
                mask = obstacle_mask(body, x, y)
                if int(mask.sum()) < 4:
                    raise ValueError(f"Obstacle {body.name!r} must occupy at least four cells; increase its size or grid resolution")
                if mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any():
                    raise ValueError(f"Obstacle {body.name!r} must leave the outer grid cell ring fluid; move it away from channel boundaries")
        elif self.obstacle and not (
            self.obstacle_radius < self.obstacle_x < 1 - self.obstacle_radius
            and self.obstacle_radius < self.obstacle_y < 1 - self.obstacle_radius
        ):
            raise ValueError("The obstacle circle must fit strictly inside the channel")
        return self


class FluidSimulation:
    """Deterministic channel with matched left inflow/right outflow.

    Top/bottom and obstacle boundaries have zero normal velocity (free slip).
    ``u`` is n×(n+1) and ``v`` is (n+1)×n on faces; the JSON snapshot returns
    centered n×n velocities. Density is a passive dye concentration. Pressure
    convergence is limited by ``iterations`` and reported through divergence.
    """

    def __init__(self, config: FluidConfig):
        self.config = config.model_copy(deep=True)
        self.n = config.resolution
        self.h = 1.0 / self.n
        centers = (np.arange(self.n) + 0.5) * self.h
        self.x, self.y = np.meshgrid(centers, centers)
        self.obstacle = np.zeros((self.n, self.n), dtype=bool)
        self.obstacle_outlines = []
        if config.obstacles is not None:
            for body in config.obstacles:
                self.obstacle |= obstacle_mask(body, self.x, self.y)
                self.obstacle_outlines.append({"name": body.name, "points": obstacle_outline(body).tolist()})
        elif config.obstacle:
            self.obstacle = (
                (self.x - config.obstacle_x) ** 2
                + (self.y - config.obstacle_y) ** 2
            ) < config.obstacle_radius ** 2
            body = FluidObstacle(name="obstacle", x=config.obstacle_x, y=config.obstacle_y, width=2 * config.obstacle_radius)
            self.obstacle_outlines.append({"name": body.name, "points": obstacle_outline(body).tolist()})
        self.fluid = ~self.obstacle
        self.open_u = self.fluid[:, :-1] & self.fluid[:, 1:]
        self.open_v = self.fluid[:-1, :] & self.fluid[1:, :]
        self.degree = np.zeros((self.n, self.n))
        self.degree[:, :-1] += self.open_u
        self.degree[:, 1:] += self.open_u
        self.degree[:-1, :] += self.open_v
        self.degree[1:, :] += self.open_v
        if config.source_mode == "rake":
            self.source = np.zeros_like(self.obstacle)
            column = min(self.n - 1, int(config.source_x * self.n))
            for position in np.linspace(0.1, 0.9, 9):
                self.source[min(self.n - 1, int(position * self.n)), column] = True
        else:
            self.source = (
                (self.x - config.source_x) ** 2 + (self.y - config.source_y) ** 2
            ) < config.source_radius ** 2
        self.source &= self.fluid
        self._ux, self._uy = np.meshgrid(np.arange(self.n + 1) * self.h, centers)
        self._vx, self._vy = np.meshgrid(centers, np.arange(self.n + 1) * self.h)
        self.reset()

    def reset(self) -> dict:
        self.time = 0.0
        self._steps = 0
        self.u = np.full((self.n, self.n + 1), self.config.inflow)
        self.v = np.zeros((self.n + 1, self.n))
        self.density = np.zeros((self.n, self.n))
        self.project()
        return self.snapshot()

    def _boundaries(self):
        self.u[:, 0] = self.config.inflow
        self.u[:, -1] = self.config.inflow
        self.v[0, :] = 0
        self.v[-1, :] = 0
        self.u[:, 1:-1] *= self.open_u
        self.v[1:-1, :] *= self.open_v
        self.density[self.obstacle] = 0

    def divergence(self) -> np.ndarray:
        return (
            self.u[:, 1:] - self.u[:, :-1] + self.v[1:, :] - self.v[:-1, :]
        ) / self.h

    def _pressure_matrix(self, field):
        result = self.degree * field
        result[:, :-1] -= self.open_u * field[:, 1:]
        result[:, 1:] -= self.open_u * field[:, :-1]
        result[:-1, :] -= self.open_v * field[1:, :]
        result[1:, :] -= self.open_v * field[:-1, :]
        return result

    def project(self):
        """Remove compressive velocity with a masked discrete Poisson solve."""
        self._boundaries()
        rhs = -self.divergence() * self.h ** 2
        rhs[self.obstacle] = 0
        rhs[self.fluid] -= rhs[self.fluid].mean()
        pressure = np.zeros_like(rhs)
        residual = rhs.copy()
        diagonal = np.maximum(self.degree, 1)
        z = residual / diagonal
        direction = z.copy()
        rz = float(np.sum(residual * z))
        tolerance = max(float(np.sum(rhs * rhs)) * 1e-12, 1e-24)
        for _ in range(self.config.iterations):
            if float(np.sum(residual * residual)) <= tolerance:
                break
            product = self._pressure_matrix(direction)
            denominator = float(np.sum(direction * product))
            if denominator <= 1e-30:
                break
            alpha = rz / denominator
            pressure += alpha * direction
            residual -= alpha * product
            z = residual / diagonal
            next_rz = float(np.sum(residual * z))
            direction = z + (next_rz / rz) * direction
            rz = next_rz
        self.u[:, 1:-1] -= self.open_u * np.diff(pressure, axis=1) / self.h
        self.v[1:-1, :] -= self.open_v * np.diff(pressure, axis=0) / self.h
        # The last projection's potential / dt is a diagnostic correction,
        # not the total physical pressure of a calibrated aerodynamic model.
        pressure[self.fluid] -= pressure[self.fluid].mean()
        pressure[self.obstacle] = 0
        self.pressure_correction = pressure / self.config.timestep
        self._boundaries()

    @staticmethod
    def _sample(field, grid_x, grid_y):
        """Bilinear sample in index coordinates, clamped at domain edges."""
        gx = np.clip(grid_x, 0, field.shape[1] - 1)
        gy = np.clip(grid_y, 0, field.shape[0] - 1)
        x0 = np.floor(gx).astype(int)
        y0 = np.floor(gy).astype(int)
        x1 = np.minimum(x0 + 1, field.shape[1] - 1)
        y1 = np.minimum(y0 + 1, field.shape[0] - 1)
        fx, fy = gx - x0, gy - y0
        return (
            (1 - fy) * ((1 - fx) * field[y0, x0] + fx * field[y0, x1])
            + fy * ((1 - fx) * field[y1, x0] + fx * field[y1, x1])
        )

    def _diffuse(self, field, coefficient):
        if coefficient == 0:
            return field.copy()
        a = coefficient * self.config.timestep / self.h ** 2
        original = field.copy()
        result = field.copy()
        for _ in range(self.config.iterations):
            padded = np.pad(result, 1, mode="edge")
            neighbors = padded[:-2, 1:-1] + padded[2:, 1:-1]
            neighbors += padded[1:-1, :-2] + padded[1:-1, 2:]
            result = (original + a * neighbors) / (1 + 4 * a)
        return result

    def _diffuse_dye(self):
        """Implicit no-flux scalar diffusion across open fluid-cell faces."""
        a = self.config.diffusion * self.config.timestep / self.h ** 2
        if a == 0:
            return self.density.copy()
        original = self.density.copy()
        original[self.obstacle] = 0
        result = original.copy()
        for _ in range(self.config.iterations):
            neighbors = np.zeros_like(result)
            neighbors[:, :-1] += self.open_u * result[:, 1:]
            neighbors[:, 1:] += self.open_u * result[:, :-1]
            neighbors[:-1, :] += self.open_v * result[1:, :]
            neighbors[1:, :] += self.open_v * result[:-1, :]
            result = (original + a * neighbors) / (1 + a * self.degree)
        return result

    def _advance(self):
        dt = self.config.timestep
        self.u = self._diffuse(self.u, self.config.viscosity)
        self.v = self._diffuse(self.v, self.config.viscosity)
        self.project()
        old_u, old_v = self.u.copy(), self.v.copy()
        cross_v = self._sample(old_v, self._ux / self.h - 0.5, self._uy / self.h)
        cross_u = self._sample(old_u, self._vx / self.h, self._vy / self.h - 0.5)
        self.u = self._sample(
            old_u, (self._ux - dt * old_u) / self.h,
            (self._uy - dt * cross_v) / self.h - 0.5,
        )
        self.v = self._sample(
            old_v, (self._vx - dt * cross_u) / self.h - 0.5,
            (self._vy - dt * old_v) / self.h,
        )
        self.project()
        uc, vc = self._centered_velocity()
        back_x, back_y = self.x - dt * uc, self.y - dt * vc
        self.density = self._diffuse_dye()
        self.density = self._sample(
            self.density, back_x / self.h - 0.5, back_y / self.h - 0.5,
        )
        self.density[back_x < 0] = 0  # The inlet carries clean fluid.
        self.density *= math.exp(-self.config.dissipation * dt)
        self.density[self.source] += self.config.dye_source * dt
        self._boundaries()
        self._steps += 1
        self.time = self._steps * dt

    def step(self, steps: int = 1) -> dict:
        if type(steps) is not int or not 1 <= steps <= 200:
            raise ValueError("steps must be an integer between 1 and 200")
        for _ in range(steps):
            self._advance()
        if not all(np.isfinite(a).all() for a in (self.u, self.v, self.density)):
            raise RuntimeError("Fluid state became nonfinite; reset and reduce timestep")
        return self.snapshot()

    def _centered_velocity(self):
        uc = 0.5 * (self.u[:, :-1] + self.u[:, 1:])
        vc = 0.5 * (self.v[:-1, :] + self.v[1:, :])
        uc[self.obstacle], vc[self.obstacle] = 0, 0
        return uc, vc

    def snapshot(self) -> dict:
        uc, vc = self._centered_velocity()
        speed2 = uc * uc + vc * vc
        vorticity = np.gradient(vc, self.h, axis=1) - np.gradient(uc, self.h, axis=0)
        vorticity[self.obstacle] = 0
        max_speed = float(np.sqrt(speed2.max()))
        return {
            "time": self.time, "resolution": self.n,
            "density": self.density.tolist(), "u": uc.tolist(), "v": vc.tolist(),
            "obstacle": self.obstacle.tolist(),
            "obstacle_outlines": deepcopy(self.obstacle_outlines),
            "speed": np.sqrt(speed2).tolist(),
            "vorticity": vorticity.tolist(),
            "pressure_correction": self.pressure_correction.tolist(),
            "metrics": {
                "divergence_rms": float(np.sqrt(np.mean(self.divergence()[self.fluid] ** 2))),
                "kinetic_energy": float(0.5 * speed2.sum() * self.h ** 2),
                "dye_mass": float(self.density.sum() * self.h ** 2),
                "max_speed": max_speed,
                "cfl": max_speed * self.config.timestep / self.h,
            },
        }
