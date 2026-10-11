# Design references

Consulted 12 October 2026. These are conceptual and technical references; Kinetic is an independent interface and does not reuse proprietary assets or claim feature parity.

- [MuJoCo documentation](https://mujoco.readthedocs.io/en/stable/overview.html): mature articulated rigid-body engine and native simulation API. [Fluid force model](https://mujoco.readthedocs.io/en/stable/computation/fluid.html) distinguishes inertia/ellipsoid force approximations from resolving a surrounding fluid field.
- [MuJoCo MJX](https://mujoco.readthedocs.io/en/stable/mjx.html): JAX-based batching and accelerator execution, with different supported features and numerical properties from the native engine.
- [Gymnasium environment API](https://gymnasium.farama.org/api/env/): explicit reset/step semantics and separate termination and truncation flags.
- [CARLA synchrony and timestep](https://carla.readthedocs.io/en/latest/adv_synchrony_timestep/): explicit simulation advancement independent of client wall-clock speed.
- [Isaac Lab](https://isaac-sim.github.io/IsaacLab/main/index.html): modular tasks, batched environments and experiment workflows. Kinetic does not include Isaac Sim rendering or sensors.
- [MathWorks RoadRunner](https://www.mathworks.com/products/roadrunner.html): professional scene authoring, hierarchy and attribute inspection as interface references.
- [Ansys Fluent](https://www.ansys.com/products/fluids/ansys-fluent): an example of the far broader meshing, turbulence and engineering validation required for an industrial CFD product. The standalone fluid lab here does not claim those capabilities.
- [Ambystoma Technologies portfolio](https://ambystomatechnologies.github.io/): interactive scientific tools, particularly wind-tunnel geometry editing, field views, probes and experiment presets. See the [eight-project review and source caveats](ambystoma-reference-review.md). These are interaction references; no product code or assets were copied.

All rendering meshes for the initial scenes are generated from primitive geometry. No paid simulator binary or paid asset is required.
