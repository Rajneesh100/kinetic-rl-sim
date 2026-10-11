# Physics and task semantics

## Native rigid-body engine

MuJoCo solves articulated rigid-body dynamics, joint actuation and contact constraints. All Studio geometry comes from the same compiled model and updated engine transforms. This release generates native MJCF from scene JSON; it does not implement its own rigid-body integrator.

The default solver is Newton with an elliptic friction cone and `implicitfast` integration. Scene configuration exposes gravity, timestep, solver iterations/tolerance, integrator/solver choice, sliding/torsional/rolling friction, contact dimension, contact reference time constant and damping ratio. A friction coefficient has an effect only when the selected contact dimension enables it. Contact dimension 1 is frictionless, 3 adds sliding, 4 adds torsion, and 6 adds rolling.

These are model parameters, not an assurance of physical accuracy. Check convergence with smaller timesteps and higher solver accuracy for your intended scale/mass/contact regime. All built-in models are simplified research examples.

## Models

| Model | Actions | Interpretation |
|---|---|---|
| Car | throttle, steer | Four driven wheel motors; front steering position targets. Throttle is signed drive torque, steering maps to ±0.5 rad. No differential, suspension or calibrated tyre model. |
| Quadruped | front-right hip/knee, front-left hip/knee, rear-right hip/knee, rear-left hip/knee | Eight position-controlled joints with finite torque limits. Hip targets = -0.25 + 0.65a rad; knee targets = 0.65 + 0.75a rad. Simplified two-joint legs. |
| Aircraft | throttle, roll, pitch, yaw | Body-axis thrust and torques plus MuJoCo ellipsoid fluid forces. Throttle maps [-1,1] to [0,motor_strength]; attitude controls are direct torque commands, not actuated aerodynamic control surfaces. |
| Sandbox | empty array | Free dynamic primitives and static obstacles; no robot controller. |

Robot `mass` is the nominal assembled robot mass distributed over its bodies. `motor_strength` sets drive/servo torque scales or aircraft thrust scale. Detailed internal robot geometry and actuator gains currently use template/compiler definitions. Primitive object sizes, poses and masses are independent scene parameters.

## Observations, rewards and episodes

The observation is `[simulation_time, ...qpos, ...qvel]`. `description.observation_layout` publishes offsets and lengths. Native generalized coordinates are ordered by the compiled model: authored dynamic objects precede the robot. Free-joint qpos uses 3 positions followed by a wxyz quaternion; its velocity has 3 linear and 3 angular components. Do not assume the robot is always at observation index 1. For direct access use `env.simulation.model` and MuJoCo named joint addresses. Scene changes may change dimensions and require a new policy/network.

Default locomotion reward is forward displacement along world x divided by control duration, minus `0.01 * sum(action²)`, minus 5 on physical/task termination. Sandbox reward is zero. This is a simple dense progress reward, not autonomous navigation, target tracking or certified flight control. `info.speed` is the magnitude of robot root linear velocity; distance is horizontal displacement from its reset position; contacts counts current engine contacts; energy is native potential plus kinetic energy.

An episode terminates on numerical instability, leaving the configured terrain region, or a model-specific fallen/grounded condition. A car terminates below 0.12 m or upside down; a quadruped below 0.22 m or excessively tilted; an aircraft below 0.25 m. Excessive altitude (>500 m) or falling below -10 m also terminates. Maximum control-step count truncates otherwise continuing episodes. Call reset after either flag. The scripted demo resets only when instructed by the client; it is not a learned controller or a performance benchmark.

## Aerodynamics

`physics.density`, `physics.viscosity` and `physics.wind` configure the surrounding medium. Aircraft geoms use MuJoCo ellipsoid fluid forces; `robot.aero_coefficients` contains five coefficients: blunt drag, slender drag, angular drag, Kutta lift and Magnus lift. These forces approximate body-fluid interaction without solving a surrounding velocity/pressure volume. See [MuJoCo fluid models](https://mujoco.readthedocs.io/en/stable/computation/fluid.html).

No validated airfoil polar, stall/compressibility model, propeller slipstream, thermal model or turbulent wake interaction is supplied. Flight behavior needs calibration for any intended aircraft. The car/quadruped can also experience native medium forces, but there is no resolved wake field.

## Separate fluid lab

The fluid lab solves an independent 2-D incompressible channel with passive dye, configurable inflow, viscosity, diffusion and multiple circles, boxes, ellipses, NACA profiles or polygons. It has its own fields and timesteps. Its visual dye is a scalar concentration, not physical smoke density, and does not modify medium density in a rigid-body world. Scalar diffusion blocks solid faces; velocity diffusion and semi-Lagrangian transport remain approximate near rasterized boundaries. Pressure correction is a solver diagnostic, not validated static pressure or force telemetry. See [fluid experiments](fluid-lab.md) for shape units, fields and API usage. Numerical details, stability caveats and GPU distinctions are in [hardware.md](hardware.md).

## Determinism and fidelity

Fixed timestep, explicit calls and seeded procedural terrain enable repeatable tests on the same stack. Reset without a seed retains the most recently chosen seed. Cross-platform bitwise reproducibility and native/MJX equivalence are not promised. Camera, LiDAR, IMU noise, domain randomization distributions, traffic behavior, deformables, coupled 3-D CFD and arbitrary articulated asset import are future extensions. A model working here does not establish safe operation on physical hardware.
