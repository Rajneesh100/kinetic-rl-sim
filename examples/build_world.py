"""Generate a physical obstacle course; all output stays under the project."""
import argparse
import json
from pathlib import Path

import numpy as np

from rl_sim.engine import Simulation
from rl_sim.schema import ObjectConfig
from rl_sim.scenes import get_template


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('data/worlds/obstacle-course.json'))
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    scene = get_template('quadruped')
    scene.name = 'Seeded locomotion course'
    scene.terrain.kind = 'flat'
    scene.terrain.seed = args.seed
    rng = np.random.default_rng(args.seed)
    scene.objects = []
    for index in range(12):
        height = float(rng.uniform(.03, .15))
        scene.objects.append(ObjectConfig(name=f'step_{index}', kind='box',
            size=[.18, .9, height / 2], position=[2 + index * .65, 0., height / 2],
            mass=1., static=True, color=[.42, .5, .59, 1.]))
    scene.objects.append(ObjectConfig(name='ramp', kind='box', size=[1.5, 1., .08],
        position=[12., 0., .3], rotation=[0., -.18, 0.], static=True,
        color=[.95, .48, .22, 1.]))
    Simulation(scene)  # Compile before publishing a malformed scene.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(scene.model_dump_json(indent=2) + '\n')
    print(json.dumps({'scene': str(args.output), 'seed': args.seed, 'objects': len(scene.objects)}))


if __name__ == '__main__':
    main()
