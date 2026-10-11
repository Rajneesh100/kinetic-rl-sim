"""Evaluate a random/scripted/PPO policy and record actual episode telemetry."""
import argparse
import json
import time
from pathlib import Path

from rl_sim.sdk import LocalEnv, RemoteEnv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', default='driving')
    parser.add_argument('--steps', type=int, default=300)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--remote', action='store_true')
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--model', type=Path)
    parser.add_argument('--realtime', action='store_true', help='Pace for observation; physics remains fixed-step')
    parser.add_argument('--output', type=Path, default=Path('data/rollouts/latest.jsonl'))
    args = parser.parse_args()
    model = None
    if args.model:
        from stable_baselines3 import PPO
        model = PPO.load(args.model, device='cpu')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    total = 0.
    episodes = 0
    env = RemoteEnv(args.url, template=args.template) if args.remote else LocalEnv(template=args.template)
    try:
        if args.remote:
            print(f'Attach Studio to world: {env.world_id}', flush=True)
        print(f'Controller: {"saved PPO policy" if model else "random actions (not trained)"}', flush=True)
        env.action_space.seed(args.seed)
        observation, _ = env.reset(seed=args.seed)
        with args.output.open('w') as log:
            log.write(json.dumps({'template': args.template, 'seed': args.seed, 'description': env.description, 'policy': str(args.model) if model else 'random'}) + '\n')
            for step in range(args.steps):
                before = time.monotonic()
                action = model.predict(observation, deterministic=True)[0] if model else env.action_space.sample()
                observation, reward, terminated, truncated, info = env.step(action)
                total += reward
                log.write(json.dumps({'step': step, 'action': action.tolist(), 'reward': reward, 'terminated': terminated, 'truncated': truncated, 'info': info}) + '\n')
                if terminated or truncated:
                    episodes += 1
                    observation, _ = env.reset()
                if args.realtime:
                    time.sleep(max(0, env.description['dt'] - (time.monotonic() - before)))
    finally:
        env.close()
    print(json.dumps({'steps': args.steps, 'finished_episodes': episodes, 'total_reward': total, 'output': str(args.output)}))


if __name__ == '__main__':
    main()
