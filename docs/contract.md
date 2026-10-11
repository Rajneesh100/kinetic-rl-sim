# Internal contract v1

API prefix `/api/v1`. JSON scene uses the schema in `rl_sim/schema.py`.

Engine: `Simulation(scene: SceneConfig)`, `.scene`, `.model`, `.data`, `.reset(seed: int | None = None) -> dict`, `.step(action: list[float], frames: int | None = None) -> dict`, `.snapshot() -> dict`, `.demo_action() -> list[float]`, `.description() -> dict`.
`scenes.py`: `templates() -> list[dict]` each `{id,name,description,category,scene}`; `get_template(id) -> SceneConfig`.

Snapshot JSON: `{time, step, observation: number[], reward, terminated, truncated, info: {speed, height, distance, contacts, energy}, geoms: [{id,name,type,position:[x,y,z],quaternion:[w,x,y,z],size:[x,y,z],rgba:[r,g,b,a]}]}`. Geom sizes follow MuJoCo: half-extents boxes/planes; sphere radius in size[0]; capsule/cylinder radius and half-length size[0:2]. Geometry type names: plane,box,sphere,capsule,cylinder,ellipsoid. `description`: `{action_size,observation_size,action_names,dt,backend}`.

GET `/health`: `{status,version,capabilities}`. GET `/templates`: template list. GET `/schema`: JSON schema.
POST `/worlds` body `{template?: 'driving',scene?: SceneConfig}` (scene takes precedence) -> `{id,scene,description,state}`.
GET `/worlds` -> `[{id,name,robot,time}]`. GET `/worlds/{id}` -> same world envelope. DELETE -> `{deleted:true}`.
POST `/worlds/{id}/reset` body `{seed?:int}` -> snapshot.
POST `/worlds/{id}/step` body `{action?:number[],frames?:int,demo?:boolean}` -> snapshot. Explicit action required unless demo=true. No automatic server advancement.
PUT `/worlds/{id}/scene` body SceneConfig -> world envelope, recompiles and resets.
GET `/worlds/{id}/state` -> snapshot; poll for externally stepped session without advancing it.
POST `/scenes` body SceneConfig -> `{name,filename}`. GET `/scenes` -> `[{name,filename,scene}]`.

Fluid: `FluidConfig` Pydantic, `FluidSimulation(config)`, `.step(steps=1)`, `.reset()`, `.snapshot()` containing `density`, centered `u`,`v`, `speed`, `vorticity`, `pressure_correction` and boolean `obstacle` 2D arrays, physical `obstacle_outlines`, plus `time`,`resolution`, metrics. Optional explicit `obstacles` supports up to16 named circles, boxes, ellipses, NACA0012/2412 profiles or polygons; omitted/null retains the legacy circle controls. `source_mode` selects jet or rake. API GET `/fluid/schema`; POST `/fluids` config -> `{id,state}`; POST `/fluids/{id}/step` `{steps:1}` -> state; POST `/fluids/{id}/reset` -> state; DELETE `/fluids/{id}`. See [fluid contract details](fluid-lab.md) for units and diagnostic limitations.

Root integrates API/SDK/docs. Physics agent owns schema.py/engine.py/scenes.py/tests/test_engine.py. UI agent owns web/. Fluid agent owns fluids.py/tests/test_fluids.py, then optional GPU runner if assigned. Communicate contract changes before editing another owner's files.
