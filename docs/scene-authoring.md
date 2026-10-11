# Build a world

Every world is a JSON `SceneConfig`. Download the current schema from `/api/v1/schema`, or export a template:

```bash
.venv/bin/rl-sim export quadruped --output data/worlds/terrain.json
.venv/bin/rl-sim validate data/worlds/terrain.json
.venv/bin/python examples/build_world.py --output data/worlds/obstacle-course.json
```

Import that file in Studio, or `POST /api/v1/worlds` with `{"scene": <JSON object>}`. Scene changes rebuild the physics model and reset the episode; pause and export before changing a training world.

## Coordinates and dimensions

Units are SI: metres, kilograms, seconds, radians. World axes are right-handed and z-up. Object `rotation` is an XYZ Euler-angle vector in radians. Snapshot orientation is a quaternion `[w,x,y,z]`. A box's `size` is **half-extents**, so `[1,0.5,0.25]` makes a 2 m × 1 m × 0.5 m box. A sphere uses `size[0]` as radius. Cylinders and capsules use `size[0]` as radius and `size[1]` as cylinder half-length along local z. Three positive numbers are required in all size vectors for a portable schema.

```json
{
  "name": "Payload test",
  "robot": {"kind":"none"},
  "objects": [
    {"name":"payload","kind":"box","size":[0.5,0.3,0.2],
     "position":[0,0,2],"mass":2.0,"static":false,
     "color":[0.95,0.4,0.18,1]}
  ]
}
```

Unspecified fields use schema defaults. The payload falls under gravity and collides with terrain. Static objects are fixed; their mass field does not make them dynamic. Avoid intersecting bodies in the initial state unless testing contact recovery deliberately.

## Scene controls

| Section | Controls |
|---|---|
| `robot` | `kind`: car, quadruped, aircraft, none; initial `position`, `rotation`, `velocity`, `angular_velocity`; total `mass`, `motor_strength`, five `aero_coefficients` |
| `physics` | `gravity`, `timestep`, `substeps`, solver/integrator/iterations/tolerance; sliding/torsional/rolling friction; contact dimension/time constant/damping; medium `density`, `viscosity`, `wind` |
| `terrain` | flat, rough or stairs; `size`, `roughness`, `seed` |
| `objects` | up to 200 named boxes, spheres, cylinders or capsules; sizes, poses, mass, static flag, RGBA |
| `max_episode_steps` | time-limit truncation in control steps |

Names must be unique. Object names start with a letter and contain letters, digits, spaces, underscores, periods or hyphens; `robot_` and `terrain_` prefixes are reserved. The schema rejects unknown properties so a misspelled friction or density setting cannot silently do nothing.

`friction` applies to the global contact model; per-material pair tables are not yet exposed. Robot mass is total assembled mass. Initial robot rotation is XYZ Euler radians, velocity is world-frame m/s, and angular velocity is body-frame rad/s. The flight template sets an initial forward velocity of 12 m/s; you can change it. Detailed robot geometry and joint configuration live in the engine compiler and are not yet arbitrary scene parameters. Decreasing time step generally improves stability at the cost of more computation. Large mass ratios, stiff contacts and high actuator forces require convergence checks; valid parameter bounds do not guarantee an accurate model for every combination.

## LLM-assisted authoring

An agent should start from the closest template, modify structured JSON, validate/compile it, run a seeded rollout and inspect the result. Create compound structures from multiple primitives. The included skill explains how to add a ramp, terrain course or randomized obstacle layout. Objects are physical collision geometry; decorative road markings in templates may also be static collision geometry, so keep their thickness and placement appropriate.

Custom CAD meshes, arbitrary articulated robot imports, soft bodies and fluid-rigid coupling are not supported by this scene format yet. Add an explicit schema version/migration when expanding it, and keep current templates backward-compatible.
