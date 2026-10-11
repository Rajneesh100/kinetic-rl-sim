# Kinetic Implementation Plan

**Goal:** deliver a runnable Mac-first simulator studio with reusable RL contracts and a documented optional NVIDIA path.
**Architecture:** native MuJoCo engine behind a FastAPI API; Three.js visualizes engine state; Gymnasium wraps the same local/remote contract; independent 2-D fluid solver.
**Spec:** [architecture.md](architecture.md)

## Shared constraints
All artifacts stay inside rl_sim. SI units, z-up, wxyz quaternions. CPU works without CUDA. GPU is optional. No fake training metrics or invented fidelity claims.

## Review focus
Reject malformed/nonfinite physics inputs; preserve seed reproducibility and session isolation; handle expired sessions and server errors visibly; prevent client playback from double-stepping externally owned sessions; keep fluid stability and GPU capability limits explicit.

- [x] Physics: implement strict scenes, templates, native MuJoCo engine and test reproducibility, actions, collisions and rollouts.
- [x] Studio: implement scene library/editor, true 3-D transforms, physics controls, transport, telemetry, import/export and remote attach.
- [x] Fluids: implement isolated 2-D solver and numerical tests; expose validated HTTP lifecycle and studio visualization.
- [x] Integration: implement API/session persistence, local/HTTP Gymnasium adapters, language examples and focused contract tests.
- [x] Hardware: add optional MJX/JAX batching runner, platform documentation and capability reporting. NVIDIA hardware validation is outstanding; CPU JIT/batching was verified.
- [x] Delivery: write skill, user/developer docs and project memory; run backend suite, production build, real training smoke and browser checks.

Completed scope is the research foundation in the architecture document. Commercial simulator parity, coupled 3-D CFD, advanced sensor models and arbitrary robot imports remain future work.
