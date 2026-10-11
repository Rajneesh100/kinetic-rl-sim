import numpy as np
from gymnasium.utils.env_checker import check_env


def test_local_env_gymnasium_contract():
    from rl_sim.sdk import LocalEnv
    env = LocalEnv(template='driving')
    check_env(env, skip_render_check=True)
    obs, info = env.reset(seed=12)
    assert env.observation_space.contains(obs)
    state = env.step(env.action_space.sample())
    assert len(state) == 5 and np.isfinite(state[1])
    env.close()


def test_local_reset_repeatable_and_reward_override():
    from rl_sim.sdk import LocalEnv
    env = LocalEnv(template='quadruped', reward_fn=lambda state: 42.0)
    a, _ = env.reset(seed=7)
    _, reward, _, _, _ = env.step(np.zeros(env.action_space.shape, dtype=np.float32))
    assert reward == 42.0
    b, _ = env.reset(seed=7)
    np.testing.assert_array_equal(a, b)


def test_remote_env_matches_local_contract(tmp_path):
    from fastapi.testclient import TestClient
    from rl_sim.server import create_app
    from rl_sim.sdk import RemoteEnv
    with TestClient(create_app(data_dir=tmp_path)) as client:
        env = RemoteEnv(client=client, template='driving')
        check_env(env, skip_render_check=True)
        obs, _ = env.reset(seed=0)
        assert env.observation_space.contains(obs)
        assert env.step(np.zeros(env.action_space.shape))[0].shape == obs.shape
        world_id = env.world_id
        env.close()
        assert client.get('/api/v1/worlds/' + world_id).status_code == 404
