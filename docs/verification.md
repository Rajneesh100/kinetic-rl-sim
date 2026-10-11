# Verification record

12 October 2026. Local machine: macOS 26.5.2, arm64; Python 3.12.13; MuJoCo/MJX 3.15.0; NumPy 2.5.4. Package resolutions are in `uv.lock` and `web/package-lock.json`. These are recorded results, not a substitute for rerunning after changes.

## Automated checks

`.venv/bin/python -m pytest --basetemp=.cache/pytest-final -q`: **80 passed**, 7.03 seconds, with optional training and MJX dependencies installed. Base installs skip the optional tests. Five non-failing warnings: one Starlette/httpx deprecation and four Gymnasium advisories about unbounded observation spaces. Generalized coordinates and velocities intentionally have unbounded Box metadata; callers should normalize observations for their task.

Coverage includes actual MuJoCo contacts, gravity and action responses; steering clearance; sustained approximate flight; seeded terrain/reset; episode flags; initial pose/velocities; configured contact/solver/aerodynamic parameters; nonfinite/extreme value rejection; independent/concurrent HTTP sessions; persistence; both Gymnasium adapters; failed-checkpoint cleanup; fluid pressure projection/advection/dissipation; and real MJX CPU JIT/batching.

`npm run build --prefix web`: TypeScript compilation and production Vite build passed.

`uv lock --check`: dependency resolution consistent. Project-local skill validator: **Skill is valid**. CLI help, generated-course compilation, JavaScript HTTP example and saved-checkpoint rollout ran successfully.

## Actual training integration

```bash
.venv/bin/python examples/train_ppo.py --template driving --steps 512 --envs 2
```

Stable Baselines3 PPO completed 512 actual steps on CPU and saved `data/models/driving-ppo.zip`; training itself took approximately 0.33 s excluding imports/setup. A separate 100-step evaluation loaded that checkpoint. This is a smoke test for the training pipeline, not evidence of a competent driving policy. Logs are under `data/training/`; the rollout is under `data/rollouts/`.

## Browser interaction checks

Verified in the Codex in-app browser at its default 1280×720 viewport:

- Loaded real native world geometry and engine contact metrics.
- Advanced one control step: time changed from 0 to 0.02 s.
- Ran and paused the scripted driving controller with actual telemetry changes; reset returned to the initial state.
- Added a dynamic sphere, changed its mass to 3 kg, applied/recompiled, and saved the world successfully.
- Ran the fluid lab and observed advancing simulation time, dye and measured flow metrics.
- Attached to an independently created world and observed disabled playback/editing controls. Server state remained exactly one step/0.02 s while the viewer polled.
- Checked final viewport and flow scaling. Review fixes cover owned-session cleanup, follow-camera drift, stale geometry names, and preserving circular fluid obstacles under responsive layout.

The local server's development reload ends in-memory sessions; the UI displays expired-session errors. Restart/reload tests must create a new world. Saved scene JSON remains on disk.

### Follow-subject camera update

12 October 2026: production UI build passed. Live browser checks at 1280×720 showed the vehicle centered before and after 167 physics steps (3.34 s), with road markers moving across the view. Orbit and zoom preserved the subject lock; an episode reset restored the initial world while retaining the camera angle and distance. Switching the subject dropdown centered Marker 1 without changing inspector selection. Switching to the robotless sandbox selected Blue cube. The expanded toolbar was also checked at 864×878 and stacks below the status label to avoid clipping.

Tracking translates the camera and orbit pivot after control damping; it does not move physical bodies or alter world coordinates. Evidence images: `artifacts/follow-before.jpg` and `artifacts/follow-after.jpg` (local, Git-ignored).

## Wind-tunnel enhancement checks

12 October 2026: `.venv/bin/python -m pytest --basetemp=.cache/pytest -q` passed **101 tests** in 9.60 s, with the same five dependency/Gymnasium warnings. Added checks cover shape masks/rotation, NACA symmetry and camber, polygon validation, containment and cell occupancy, legacy circle compatibility, multiple-body API sessions, finite diagnostic fields, zero-mean pressure correction, vorticity sign, rake sources, and dye diffusion without leakage into solids.

The included `examples/wind_tunnel.json` was posted through the real FastAPI test client and advanced 20 steps successfully: 96×96 cells, time 0.40 s, one physical outline, divergence RMS 0.00337 and CFL 1.55. These are correctness/smoke checks for an educational model, not validation against wind-tunnel experiments or turbulence benchmarks.

The production TypeScript/Vite build passed. Browser checks covered initial loading, advancing and pausing the airfoil field, smoke/speed/pressure-correction/vorticity views, streamlines and velocity vectors, a fluid-cell probe, direct obstacle dragging with draft/apply behavior, importing the example with omitted optional shape fields, and polygon-to-cylinder editing. Experiment export produced JSON that validated against `FluidConfig`; the artifact is `artifacts/kinetic-flow-verified.json`. Playback was moved above the canvas after checking both the 1280×720 and 864×878 window layouts. Browser console error checks were empty. These UI interactions do not establish engineering CFD accuracy.

## Native Apple Silicon measurements

One short run of `scripts/benchmark.py --steps 1000`, under the current machine load. Rates include controller invocation, contacts, reward/state evaluation and resets. Each control step uses four 5 ms physics substeps. These are illustrative throughput measurements, not hardware-independent promises.

| Template | Control steps/s without geometry | With geometry serialization |
|---|---:|---:|
| Driving | 3,530 | 3,033 |
| Quadruped | 5,541 | 4,611 |
| Flight | 10,578 | 9,144 |
| Sandbox | 13,694 | 12,214 |

`LocalEnv` omits geometry serialization; the HTTP studio path includes geometry. Raw measurement: `data/benchmarks/latest.json`. Browser rendering uses WebGL separately from CPU physics.

## Independent review and fixes

Review found and the implementation addressed: huge finite vectors causing overflow/poisoned sessions; API error serialization of NaN; remote session leakage on failed model loading; owned UI world/fluid leaks; follow-camera drift; stale selection names after geometry replacement; and stretched fluid coordinates. Backend regressions have targeted tests. UI fixes were built and inspected in the browser.

## Not verified or not implemented

- NVIDIA hardware execution/performance; CUDA setup must be verified on the target Linux machine.
- Apple Metal physics; native CPU dynamics and WebGL rendering are the supported Mac paths.
- Native/MJX numerical equivalence or commercial simulator parity. The optional GPU runner is a low-level physics batch API with documented model compatibility limits.
- A learned autonomous driver or trained robust quadruped gait; bundled preview controllers are scripted.
- Coupled 3-D CFD, turbulence validation, photorealistic camera/LiDAR sensors, real-world safety or sim-to-real transfer.

## Publication checks — 12 October 2026

Before the first public push, all 101 backend tests passed in 8.89 seconds (five existing dependency/Gymnasium warnings), and the production frontend build passed. Scene, fluid and OpenAPI schemas matched their running definitions. The Python CLI/example help commands, JavaScript client syntax, and documented LocalEnv/HTTP lifecycle were checked successfully. Publishable source was scanned for credential patterns and private filesystem paths, with no hits.

The screenshots and videos under `docs/media/` were captured from the running application. All three H.264 videos decoded successfully; the combined clip is 11.90 seconds and the README GIF contains 95 frames. These demonstrate interface behavior and scripted control, not trained policy quality. Hardware limitations above still apply.
