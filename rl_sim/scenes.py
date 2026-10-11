"""Four editable starting worlds. Every physical object is in the scene configuration."""
from copy import deepcopy

from .schema import SceneConfig


_TEMPLATES = {
    "driving": {
        "name": "Autonomous driving",
        "description": "Four driven wheels, front steering and a physical obstacle corridor.",
        "category": "Ground vehicle",
        "scene": {
            "name": "Coastal proving ground",
            "robot": {"kind": "car", "position": [0, 0, .48], "mass": 12, "motor_strength": 7},
            "terrain": {"size": [120, 60]},
            "objects": [
                {"name": "North barrier", "position": [25, 4.5, .3], "size": [35, .12, .3], "static": True, "color": [.64, .69, .74, 1]},
                {"name": "South barrier", "position": [25, -4.5, .3], "size": [35, .12, .3], "static": True, "color": [.64, .69, .74, 1]},
                {"name": "Marker 1", "position": [12, 2.4, .5], "size": [.5, .5, .5], "mass": 15, "color": [1, .38, .12, 1]},
                {"name": "Marker 2", "position": [24, -2.4, .5], "size": [.5, .5, .5], "mass": 15, "color": [1, .38, .12, 1]},
                {"name": "Marker 3", "position": [38, 2.4, .5], "size": [.5, .5, .5], "mass": 15, "color": [1, .38, .12, 1]},
            ],
        },
    },
    "quadruped": {
        "name": "Quadruped locomotion",
        "description": "Eight position-controlled hip and knee joints with genuine contact dynamics.",
        "category": "Articulated robot",
        "scene": {
            "name": "Legged robotics lab",
            "robot": {"kind": "quadruped", "position": [0, 0, .65], "mass": 8, "motor_strength": 20},
            "objects": [
                {"name": "Low platform", "position": [3, 0, .08], "size": [.7, 1.2, .08], "static": True, "color": [.32, .39, .49, 1]},
                {"name": "Practice block", "position": [5, 1.8, .3], "size": [.45, .45, .3], "static": True, "color": [.94, .54, .2, 1]},
            ],
        },
    },
    "flight": {
        "name": "Fixed-wing flight",
        "description": "Free aircraft with thrust, body torques, and MuJoCo ellipsoid lift and drag.",
        "category": "Aerodynamics",
        "scene": {
            "name": "Flight dynamics range",
            "robot": {"kind": "aircraft", "position": [0, 0, 8], "velocity": [12, 0, 0], "mass": 3, "motor_strength": 18, "aero_coefficients": [.05, .025, 1.5, 1, 1]},
            "terrain": {"size": [300, 180]},
            "objects": [
                {"name": "Runway", "position": [30, 0, .015], "size": [60, 4, .015], "static": True, "color": [.22, .27, .32, 1]},
                {"name": "Beacon left", "kind": "cylinder", "position": [20, 7, .6], "size": [.25, .6, .25], "static": True, "color": [.98, .58, .18, 1]},
                {"name": "Beacon right", "kind": "cylinder", "position": [20, -7, .6], "size": [.25, .6, .25], "static": True, "color": [.98, .58, .18, 1]},
            ],
        },
    },
    "sandbox": {
        "name": "Physics sandbox",
        "description": "Falling primitive bodies for contact, gravity, material and scene experiments.",
        "category": "Custom environment",
        "scene": {
            "name": "Open physics sandbox",
            "robot": {"kind": "none"},
            "objects": [
                {"name": "Blue cube", "position": [0, 0, 2], "size": [.5, .5, .5], "color": [.2, .55, .98, 1]},
                {"name": "Amber sphere", "kind": "sphere", "position": [1.7, 0, 3], "size": [.5, .5, .5], "color": [.98, .62, .16, 1]},
                {"name": "Teal capsule", "kind": "capsule", "position": [-1.5, .5, 2.3], "size": [.3, .6, .3], "rotation": [0, .3, .2], "color": [.13, .72, .63, 1]},
                {"name": "Ramp", "position": [0, 3, .6], "size": [2, 1, .15], "rotation": [0, .25, 0], "static": True, "color": [.48, .55, .65, 1]},
            ],
        },
    },
}


def get_template(template_id: str) -> SceneConfig:
    if template_id not in _TEMPLATES:
        raise ValueError(f"Unknown template {template_id!r}; choose {', '.join(_TEMPLATES)}")
    return SceneConfig.model_validate(deepcopy(_TEMPLATES[template_id]["scene"]))


def templates() -> list[dict]:
    return [
        {"id": key, "name": value["name"], "description": value["description"], "category": value["category"], "scene": get_template(key).model_dump(mode="json")}
        for key, value in _TEMPLATES.items()
    ]
