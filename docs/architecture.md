# Kinetic / RL Sim architecture

Status: initial implementation, 12 October 2026. This is a usable research foundation, not a claim of parity with commercial multiphysics software.

## Intent
Build reusable training and evaluation worlds for driving, articulated quadrupeds and aircraft, with a professional visual studio, configurable physical parameters, and agent-assisted scene creation. All project code, docs, caches, experiment output and project memory stay under this directory. Apple Silicon is the primary local platform; Linux NVIDIA supports an optional batched MJX path. Every client language can use HTTP/JSON.

## Engine choice
Use native MuJoCo for rigid bodies, joint actuation, collisions and aerodynamic force approximations. This provides a mature open engine and native macOS ARM support. React/Three.js renders actual engine geom transforms. A separate 2-D incompressible fluid solver models a velocity/dye field. It is not coupled 3-D CFD and must never be described as validated CFD or physical-world fidelity. MJX is an optional JAX batched physics runner for NVIDIA; its availability and performance depend on hardware and JAX installation.

Alternatives considered: browser-only Rapier makes distribution easy but adds work for articulated RL robots and GPU batching; Isaac Sim/Lab offers rich NVIDIA workflows but would not satisfy a Mac-first native development experience. A custom physics engine would divert work from interoperability and world authoring.

## Boundaries
- `rl_sim/schema.py`: strict, portable JSON scene configuration, SI units, z-up, quaternion wxyz.
- `rl_sim/engine.py`, `scenes.py`: MJCF compilation, templates, deterministic reset/step, observations and bounded actions, actual geom snapshots.
- `rl_sim/fluids.py`: independent educational 2-D flow simulation, no hidden claim of coupling.
- `rl_sim/server.py`: versioned API, isolated world lifecycle, scene persistence and fluid sessions.
- `rl_sim/sdk.py`: Gymnasium adapter for direct local stepping or remote HTTP; clients own task rewards if desired.
- `web/`: studio, object hierarchy and editor, physical parameters, telemetry, import/export, API connect view.
- `skills/rl-sim/SKILL.md`: reproducible LLM world-building and integration workflow.

## Physical contract
Gravity, time step, solver iterations, friction, medium density/viscosity/wind, terrain roughness, mass, primitive dimensions/poses and actuator strength are explicit. Unknown scene keys and nonfinite values fail validation. User actions are normalized to [-1,1]. A step advances an explicit number of fixed substeps and never wall-clock time. Reset seed controls procedural terrain. Episode termination and truncation are separate. No trained policy is implied by the scripted demonstration controller.

## Scope and evolution
First release includes four templates, local save/import/export, scene JSON/schema/OpenAPI, independent sessions, direct and remote Gymnasium, JavaScript client example, numerical checks and browser verification. Follow-on work includes measured GPU throughput, photorealistic sensor rendering, traffic, CAD/URDF imports, deformables, 3-D CFD with coupling and validated sim-to-real calibration. Those features must remain listed as unsupported until implemented and verified.

## Validation
Check deterministic reset, finite long rollouts, meaningful action response, gravity/contact behavior, scene validation, lifecycle isolation, persisted reloads, Gymnasium conformance, fluid projection/dissipation and browser editing/playback. Record the actual machine and commands. GPU checks are distinguished from Mac checks.
