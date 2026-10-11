# Project memory

User intent (12 October 2026): a reusable configurable simulator for self-driving, quadruped locomotion, aircraft and fluid experiments, with professional UI, language-agnostic model integration and an LLM agent skill for fast world/object creation. All project materials stay in rl_sim. Apple Silicon Macs are the primary work machines; Linux NVIDIA must have an optional path for larger batches.

Decisions: native MuJoCo core; React/Three.js studio; FastAPI HTTP/JSON; direct and remote Gymnasium adapters; optional MJX/JAX batch runner; separate educational 2-D incompressible fluid lab. No paid assets, cloud service or hosted model key. Original development history remains on codex/kinetic-simulator. Public repository: https://github.com/Rajneesh100/kinetic-rl-sim. Publication uses main with a clean initial history and the owner's GitHub no-reply identity; global Git and GitHub authentication settings remain unchanged. The simulator runs locally; no hosted simulation service is deployed.

Contracts: SI units, z-up, quaternion wxyz. Geometry dimensions follow MuJoCo halfsize conventions. Configured fixed timestep; explicit reset/step; seeded terrain. Studio demo is scripted, not learned. Native CPU is the HTTP service backend. Saved scene JSON is an initial world description, not a physics checkpoint.

Implementation state and evidence: consult docs/implementation-plan.md and docs/verification.md. Current checks must be rerun after changes. Linux/NVIDIA hardware validation is not implied by passing Mac or JAX CPU tests.

Future scope: validated sensor models/cameras/LiDAR; arbitrary robot imports and asset pipelines; richer navigation/traffic tasks; measured multi-GPU scaling; coupled 3-D CFD; deformables; task curricula and real-world calibration. These are not shipped features.
