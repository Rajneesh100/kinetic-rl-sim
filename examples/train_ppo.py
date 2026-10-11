"""Minimal real PPO integration; the example reward is forward locomotion."""
import argparse
import json
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', default='driving', choices=['driving', 'quadruped', 'flight'])
    parser.add_argument('--steps', type=int, default=50000)
    parser.add_argument('--envs', type=int, default=4)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--device', default='cpu', choices=['cpu', 'cuda', 'mps', 'auto'])
    args = parser.parse_args()
    if args.steps < 1 or args.envs < 1:
        parser.error('--steps and --envs must be positive')
    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.env_util import make_vec_env
        from stable_baselines3.common.logger import configure
    except ImportError:
        parser.error("Install training support: uv pip install --python .venv/bin/python -e '.[train]'")
    from rl_sim.sdk import LocalEnv
    run_dir = Path('data/training') / f'{args.template}-{time.time_ns()}'
    run_dir.mkdir(parents=True)
    env = make_vec_env(lambda: LocalEnv(template=args.template), n_envs=args.envs, seed=args.seed)
    model = PPO('MlpPolicy', env, verbose=1, seed=args.seed, device=args.device,
                n_steps=128, batch_size=64, n_epochs=4, policy_kwargs={'net_arch': [64, 64]})
    model.set_logger(configure(str(run_dir), ['stdout', 'csv']))
    start = time.perf_counter()
    try:
        model.learn(total_timesteps=args.steps)
        target = Path('data/models') / f'{args.template}-ppo'
        target.parent.mkdir(parents=True, exist_ok=True)
        model.save(target)
        result = dict(template=args.template, requested_steps=args.steps, actual_steps=model.num_timesteps,
                      envs=args.envs, seed=args.seed, device=str(model.device), seconds=time.perf_counter() - start,
                      checkpoint=str(target.with_suffix('.zip')), note='Training integration only; evaluate policy quality separately.')
        (run_dir / 'run.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))
    finally:
        env.close()


if __name__ == '__main__':
    main()
