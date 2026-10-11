"""Measure native training vs geometry-export cost on the current machine."""
import argparse
import json
import platform
import time
from pathlib import Path

import mujoco

from rl_sim.engine import Simulation
from rl_sim.scenes import get_template


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--steps', type=int, default=1000)
    parser.add_argument('--output', type=Path, default=Path('data/benchmarks/latest.json'))
    args = parser.parse_args()
    if args.steps < 1:
        parser.error('--steps must be positive')
    rows = []
    for template in ['driving', 'quadruped', 'flight', 'sandbox']:
        for geometry in [False, True]:
            sim = Simulation(get_template(template))
            sim.reset(seed=42, include_geoms=False)
            start = time.perf_counter()
            for _ in range(args.steps):
                state = sim.step(sim.demo_action(), include_geoms=geometry)
                if state['terminated'] or state['truncated']:
                    sim.reset(seed=42, include_geoms=False)
            elapsed = time.perf_counter() - start
            rows.append(dict(template=template, geometry=geometry, control_steps=args.steps,
                             seconds=elapsed, control_steps_per_second=args.steps / elapsed,
                             simulated_seconds_per_wall_second=args.steps * sim.description()['dt'] / elapsed))
    result = dict(platform=platform.platform(), machine=platform.machine(), python=platform.python_version(), mujoco=mujoco.__version__, results=rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
