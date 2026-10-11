import sys

import pytest
from fastapi.testclient import TestClient


def test_failed_model_loading_does_not_leak_remote_world(monkeypatch, tmp_path):
    pytest.importorskip('stable_baselines3')
    from examples import rollout
    from rl_sim.sdk import RemoteEnv
    from rl_sim.server import create_app
    with TestClient(create_app(data_dir=tmp_path)) as client:
        monkeypatch.setattr(rollout, 'RemoteEnv', lambda *args, **kwargs: RemoteEnv(client=client, **kwargs))
        monkeypatch.setattr(sys, 'argv', ['rollout', '--remote', '--model', str(tmp_path / 'missing-model.zip')])
        with pytest.raises(FileNotFoundError):
            rollout.main()
        assert client.get('/api/v1/worlds').json() == []
