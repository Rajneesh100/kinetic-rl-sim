"""Validated, rasterized 2-D obstacles in the fluid lab's unit domain."""

from __future__ import annotations

import math
from typing import Annotated, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator


Coordinate = Annotated[float, Field(ge=-0.5, le=0.5)]
Point = Annotated[list[Coordinate], Field(min_length=2, max_length=2)]


class FluidObstacle(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    name: str = Field(min_length=1, max_length=64)
    shape: Literal["circle", "box", "ellipse", "naca0012", "naca2412", "polygon"] = "circle"
    x: float = Field(default=0.45, gt=0, lt=1)
    y: float = Field(default=0.5, gt=0, lt=1)
    width: float = Field(default=0.2, ge=0.01, le=0.9, description="Diameter, full box/ellipse width, or airfoil chord in unit-domain coordinates.")
    height: float = Field(default=0.2, ge=0.01, le=0.9, description="Full box/ellipse/polygon height. Ignored for circles and fixed 12%-chord NACA profiles.")
    angle: float = Field(default=0.0, ge=-180, le=180, description="Counterclockwise rotation in degrees about (x,y).")
    points: list[Point] | None = Field(default=None, min_length=3, max_length=64, description="Simple polygon vertices in local [-0.5,0.5] coordinates, scaled by width/height. Do not repeat the first vertex.")

    @model_validator(mode="after")
    def valid_geometry(self):
        if not self.name.strip():
            raise ValueError("Obstacle name must contain non-whitespace characters")
        if self.shape == "polygon":
            if self.points is None:
                raise ValueError("Polygon obstacles require points")
            _validate_polygon(np.asarray(self.points))
        elif self.points is not None:
            raise ValueError("Only polygon obstacles accept points")
        if self.shape in ("circle", "ellipse"):
            angle = math.radians(self.angle)
            a = self.width / 2
            b = a if self.shape == "circle" else self.height / 2
            rx = math.hypot(a * math.cos(angle), b * math.sin(angle))
            ry = math.hypot(a * math.sin(angle), b * math.cos(angle))
            contained = rx < self.x < 1 - rx and ry < self.y < 1 - ry
        else:
            points = obstacle_outline(self)
            contained = bool(np.all((points > 0) & (points < 1)))
        if not contained:
            raise ValueError(f"Obstacle {self.name!r} must fit strictly inside the channel after rotation")
        return self


def _validate_polygon(points: np.ndarray):
    """Reject repeated, degenerate or intersecting polygon edges."""
    if len(np.unique(points, axis=0)) != len(points):
        raise ValueError("Polygon vertices must be distinct")
    following = np.roll(points, -1, axis=0)
    area2 = np.sum(points[:, 0] * following[:, 1] - following[:, 0] * points[:, 1])
    if abs(area2) < 1e-8:
        raise ValueError("Polygon must enclose a nonzero area")

    def cross(a, b, c):
        ab, ac = b - a, c - a
        return ab[0] * ac[1] - ab[1] * ac[0]

    def on_segment(a, b, p):
        return abs(cross(a, b, p)) <= 1e-12 and np.all(p >= np.minimum(a, b) - 1e-12) and np.all(p <= np.maximum(a, b) + 1e-12)

    for i, (a, b) in enumerate(zip(points, following)):
        for j in range(i + 1, len(points)):
            if j == i + 1 or (i == 0 and j == len(points) - 1):
                continue
            c, d = points[j], following[j]
            intersects = cross(a, b, c) * cross(a, b, d) < 0 and cross(c, d, a) * cross(c, d, b) < 0
            touches = any((on_segment(a, b, c), on_segment(a, b, d), on_segment(c, d, a), on_segment(c, d, b)))
            if intersects or touches:
                raise ValueError("Polygon edges must not intersect or touch except at adjacent vertices")


def _naca_outline(cambered: bool) -> np.ndarray:
    """Closed trailing-edge NACA 0012/2412 with cosine-spaced chord samples."""
    x = (1 - np.cos(np.linspace(0, np.pi, 129))) / 2
    thickness = 5 * 0.12 * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1036 * x**4)
    m, p = (0.02, 0.4) if cambered else (0.0, 0.4)
    camber = np.where(x < p, m / p**2 * (2 * p * x - x**2), m / (1 - p)**2 * ((1 - 2*p) + 2*p*x - x**2))
    slope = np.where(x < p, 2*m / p**2 * (p - x), 2*m / (1-p)**2 * (p - x))
    theta = np.arctan(slope)
    upper = np.column_stack((x - thickness * np.sin(theta) - 0.5, camber + thickness * np.cos(theta)))
    lower = np.column_stack((x + thickness * np.sin(theta) - 0.5, camber - thickness * np.cos(theta)))
    return np.concatenate((upper[::-1], lower[1:-1]))


def obstacle_outline(body: FluidObstacle) -> np.ndarray:
    """Return the physical outline in world coordinates, without closing repeat."""
    if body.shape in ("circle", "ellipse"):
        theta = np.arange(64) * 2 * np.pi / 64
        height = body.width if body.shape == "circle" else body.height
        local = np.column_stack((np.cos(theta) * body.width / 2, np.sin(theta) * height / 2))
    elif body.shape.startswith("naca"):
        local = _naca_outline(body.shape == "naca2412") * body.width
    elif body.shape == "polygon":
        local = np.asarray(body.points) * [body.width, body.height]
    else:
        local = np.array([[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]]) * [body.width, body.height]
    angle = math.radians(body.angle)
    rotation = np.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
    return local @ rotation.T + [body.x, body.y]


def obstacle_mask(body: FluidObstacle, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    if body.shape in ("circle", "ellipse", "box"):
        angle = math.radians(body.angle)
        dx, dy = x - body.x, y - body.y
        lx = math.cos(angle) * dx + math.sin(angle) * dy
        ly = -math.sin(angle) * dx + math.cos(angle) * dy
        if body.shape == "box":
            return (np.abs(lx) < body.width / 2) & (np.abs(ly) < body.height / 2)
        height = body.width if body.shape == "circle" else body.height
        return (lx / (body.width / 2))**2 + (ly / (height / 2))**2 < 1
    points = obstacle_outline(body)
    inside = np.zeros_like(x, dtype=bool)
    for a, b in zip(points, np.roll(points, -1, axis=0)):
        if a[1] == b[1]:
            continue
        crosses = (a[1] > y) != (b[1] > y)
        edge_x = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
        inside ^= crosses & (x < edge_x)
    return inside
