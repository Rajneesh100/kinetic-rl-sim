# Wind tunnel and fluid experiments

Open **Fluid dynamics** in Studio. The four experiments are Cylinder flow, NACA airfoil, Bluff body and Twin obstacles. Presets are starting geometries for the same native CPU solver. Choose an experiment, run/pause, inspect a field, and click the fluid to place a measurement probe.

Select an obstacle in the list or canvas. Drag it, or edit its position, width and angle. Changes are drafts: **Apply & restart** builds a new field. The filled solid mask and measurements continue to show the applied experiment until then; outlines show the draft geometry. Inspecting a different field or moving a probe does not advance physics. Streamlines trace the current velocity field and are not particle histories.

## Fields and measurements

| View | Source | Interpretation |
| --- | --- | --- |
| Smoke | Passive dye concentration | Arbitrary concentration units, not material density. Jet and nine-stripe rake source modes are available. |
| Speed | `sqrt(u² + v²)` | Magnitude of the centered velocity field. |
| Pressure correction | Last projection potential divided by timestep | Zero-mean kinematic correction in m²/s², not static pressure in Pa, surface pressure coefficient or validated lift/drag. |
| Vorticity | `dv/dx - du/dy` | Signed 2-D curl in 1/s. Raster boundary derivatives can produce artifacts. |

Color ranges adapt to the current fluid-cell values. Signed fields use a symmetric scale around zero. The probe samples the cell under the cursor; solid cells are identified. Velocity arrows and instantaneous streamlines use the same returned velocity arrays.

Domain coordinates span a 1 m × 1 m square, with x to the right and y upward. Arrays are indexed `[y][x]`, with the bottom row first. Inlet and outlet prescribe equal horizontal velocity; the top/bottom and obstacle boundaries have zero normal flow and free slip. This is an educational incompressible model; no validated no-slip boundary layers, turbulence, separation/stall model, engineering force coefficients or 3-D coupling are provided. Change resolution and timestep, and monitor divergence and CFL before interpreting a result. High CFL remains stable under semi-Lagrangian advection but can lose transport detail.

## Shape contract

`GET /api/v1/fluid/schema` is authoritative. `obstacles` accepts up to 16 named objects. An explicit empty list removes all obstacles. Omitting it or passing null preserves the older `obstacle`/`obstacle_x`/`obstacle_y`/`obstacle_radius` circle interface.

- Every object has `name`, `shape`, `x`, `y`, `width`, `height` and `angle`. Dimensions are full lengths, unlike MuJoCo box half-extents. Angle is counterclockwise **degrees**, unlike rigid-body scene rotations in radians.
- `circle`: width is diameter; height is ignored.
- `box` and `ellipse`: width and height are full local dimensions.
- `naca0012` and `naca2412`: width is chord. Both use a fixed 12%-chord thickness and a closed trailing edge; height is ignored. The 2412 profile has 2% maximum camber at 40% chord. Position is the chord midpoint before rotation. These are rasterized profiles, not engineering-quality boundary meshes. See the [NACA coordinate reference](https://www.pdas.com/naca456.html).
- `polygon`: `points` contains 3–64 distinct local coordinate pairs in [-0.5, 0.5]. Scale by width/height, rotate, then translate to (x,y). Do not repeat the first point. Self-intersections and zero-area shapes are rejected.

Explicit obstacles must remain inside the domain after rotation, clear the outside cell ring, and occupy at least four cell centers. Increase the grid resolution or geometry size if a thin profile is rejected. Overlapping shapes form a union of solid cells; measurements do not attribute forces to individual obstacles.

## Language-independent API

The [example airfoil configuration](../examples/wind_tunnel.json) can be sent directly:

```bash
curl -s http://127.0.0.1:8000/api/v1/fluids \
  -H 'Content-Type: application/json' \
  --data-binary @examples/wind_tunnel.json
```

Retain the returned `id`. Send `{"steps":20}` to `POST /api/v1/fluids/{id}/step` to advance exactly 20 timesteps. `POST /api/v1/fluids/{id}/reset` restores the initial field; `DELETE /api/v1/fluids/{id}` releases it. Config changes create a new session. All routes run the native CPU backend on Mac or Linux.

Snapshots include `time`, `resolution`, `density`, centered `u`/`v`, `speed`, `vorticity`, `pressure_correction`, the boolean solid `obstacle` mask, and `obstacle_outlines` in world coordinates. Metrics report divergence RMS, kinetic energy, dye mass, maximum speed and CFL. Original snapshot fields are preserved for existing clients.

Experiment export stores the applied configuration, time, metrics and current probe diagnostics for inspection. Import starts a new simulation from the configuration; it does not restore the staggered solver state or continue a checkpoint. Use the API snapshot when you need full field arrays. Keep exported experiments under `data/` in this project. The fluid session is separate from the rigid-body Gymnasium adapters; it is not automatically a flight-training environment.

## Reference

Interaction ideas were informed by the [Ambystoma wind-tunnel simulator](https://ambystomatechnologies.github.io/wind-tunnel-simulator/). Kinetic keeps its own solver, API and rendering implementation. See the [review of all eight reference projects](ambystoma-reference-review.md) and [verification record](verification.md).
