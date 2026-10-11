"""Run a real MJX batch; first-call compilation is measured separately."""

import argparse
import json
from pathlib import Path
import time

import numpy as np

from rl_sim.gpu import MJXBatchSimulation


DEMO_XML = """
<mujoco model="batch_cart"><option timestep="0.005" gravity="0 0 -9.81"/>
  <worldbody><geom type="plane" size="10 10 0.1"/>
    <body pos="0 0 0.3"><joint name="slide" type="slide" axis="1 0 0"/>
      <geom type="box" size="0.2 0.15 0.1" mass="1"/></body></worldbody>
  <actuator><motor joint="slide" ctrlrange="-2 2"/></actuator>
</mujoco>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["gpu", "cpu"], default="gpu")
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--frame-skip", type=int, default=5)
    parser.add_argument("--mjcf", type=Path, help="Optional self-contained MJCF XML file")
    args = parser.parse_args()
    if args.steps < 1:
        parser.error("--steps must be positive")
    xml = args.mjcf.read_text() if args.mjcf else DEMO_XML
    try:
        sim = MJXBatchSimulation(
            xml, batch_size=args.batch_size, backend=args.backend, frame_skip=args.frame_skip,
        )
    except (RuntimeError, ValueError) as exc:
        parser.exit(2, f"{exc}\n")
    actions = np.zeros((args.batch_size, sim.action_size), dtype=np.float32)
    if sim.action_size:
        actions[:, 0] = np.linspace(-0.5, 0.5, args.batch_size)
    started = time.perf_counter()
    sim.step(actions)
    compile_and_first_step_seconds = time.perf_counter() - started
    sim.reset()
    started = time.perf_counter()
    for _ in range(args.steps):
        state = sim.step(actions)
    elapsed = time.perf_counter() - started
    print(json.dumps({
        **sim.description(), "compile_and_first_step_seconds": compile_and_first_step_seconds,
        "measured_seconds": elapsed,
        "physics_steps_per_second": args.steps * args.batch_size * args.frame_skip / elapsed,
        "simulated_seconds_per_world": float(state["time"][0]),
        "includes_host_state_transfer": True,
    }, indent=2))


if __name__ == "__main__":
    main()
