"""Gymnasium adapters: no transport dependencies in your policy."""
from __future__ import annotations

from collections.abc import Callable

import gymnasium as gym
import httpx
import numpy as np

from .engine import Simulation
from .schema import SceneConfig
from .scenes import get_template

Reward = Callable[[dict], float]


class _Env(gym.Env):
    metadata = {'render_modes': []}
    render_mode = None

    def _configure(self, description: dict, reward_fn: Reward | None):
        self.description = description
        self.reward_fn = reward_fn
        self.action_space = gym.spaces.Box(-1, 1, shape=(description['action_size'],), dtype=np.float32)
        self.observation_space = gym.spaces.Box(-np.inf, np.inf, shape=(description['observation_size'],), dtype=np.float64)

    def _reset_result(self, state):
        # Time/state available for task-specific rewards, termination and telemetry.
        self.last_state = state
        return np.asarray(state['observation'], dtype=np.float64), dict(state['info'])

    def _step_result(self, state):
        self.last_state = state
        reward = self.reward_fn(state) if self.reward_fn is not None else state['reward']
        if not np.isfinite(reward):
            raise ValueError('Reward function returned a nonfinite value')
        return (np.asarray(state['observation'], dtype=np.float64), float(reward),
                bool(state['terminated']), bool(state['truncated']), dict(state['info']))


class LocalEnv(_Env):
    """Fast in-process MuJoCo environment for RL training.

    Each instance owns a separate model and data. Use SyncVectorEnv or separate
    processes for batching. Rendering is in the HTTP studio, not this adapter.
    """

    def __init__(self, template='driving', scene: SceneConfig | dict | None = None, reward_fn: Reward | None = None):
        super().__init__()
        config = get_template(template) if scene is None else SceneConfig.model_validate(scene)
        self.simulation = Simulation(config)
        self._configure(self.simulation.description(), reward_fn)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        return self._reset_result(self.simulation.reset(seed=seed, include_geoms=False))

    def step(self, action):
        return self._step_result(self.simulation.step(np.asarray(action).tolist(), include_geoms=False))


class RemoteEnv(_Env):
    """Language-neutral HTTP environment, viewable by attaching in Studio.

    Created sessions are deleted on close. Attaching via world_id leaves the
    existing session intact on close. Injecting client is useful for integration
    tests; the caller retains ownership of that client.
    """

    def __init__(self, url='http://127.0.0.1:8000', template='driving', scene: SceneConfig | dict | None = None,
                 world_id: str | None = None, reward_fn: Reward | None = None, client=None):
        super().__init__()
        self._owns_client = client is None
        self.client = client if client is not None else httpx.Client(base_url=url, timeout=30)
        self._owns_world = world_id is None
        self._closed = False
        if world_id is None:
            body = {'template': template}
            if scene is not None:
                body['scene'] = SceneConfig.model_validate(scene).model_dump(mode='json')
            world = self._request('POST', '/worlds', json=body)
        else:
            world = self._request('GET', f'/worlds/{world_id}')
        self.world_id = world['id']
        self._configure(world['description'], reward_fn)

    def _request(self, method, path, **kwargs):
        response = self.client.request(method, '/api/v1' + path, **kwargs)
        response.raise_for_status()
        return response.json()

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        return self._reset_result(self._request('POST', f'/worlds/{self.world_id}/reset', json={'seed': seed}))

    def step(self, action):
        return self._step_result(self._request('POST', f'/worlds/{self.world_id}/step', json={'action': np.asarray(action).tolist()}))

    def close(self):
        if self._closed:
            return
        try:
            if self._owns_world:
                response = self.client.delete(f'/api/v1/worlds/{self.world_id}')
                if response.status_code != 404:
                    response.raise_for_status()
        finally:
            self._closed = True
            if self._owns_client:
                self.client.close()
