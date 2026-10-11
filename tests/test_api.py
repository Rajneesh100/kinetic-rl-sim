import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    from rl_sim.server import create_app
    # Keep test files under project with --basetemp when running pytest.
    with TestClient(create_app(data_dir=tmp_path)) as value:
        yield value


def create(client, template='driving'):
    r = client.post('/api/v1/worlds', json={'template': template})
    assert r.status_code == 200, r.text
    return r.json()


def test_independent_worlds_explicit_step_and_delete(client):
    a, b = create(client), create(client)
    assert a['id'] != b['id']
    r = client.post(f"/api/v1/worlds/{a['id']}/step", json={'demo': True, 'frames': 4})
    assert r.status_code == 200, r.text
    assert r.json()['time'] > 0
    assert client.get(f"/api/v1/worlds/{b['id']}/state").json()['time'] == 0
    assert client.delete(f"/api/v1/worlds/{a['id']}").json()['deleted']
    assert client.get(f"/api/v1/worlds/{a['id']}/state").status_code == 404


def test_invalid_step_does_not_advance(client):
    world = create(client)
    path = f"/api/v1/worlds/{world['id']}"
    for body in [{}, {'action': [0]}, {'demo': True, 'frames': 0}, {'action': [9, 0]}, {'demo': True, 'action': [0, 0]}]:
        r = client.post(path + '/step', json=body)
        assert r.status_code == 422, (body, r.text)
        assert client.get(path + '/state').json()['time'] == 0


def test_invalid_scene_replacement_preserves_previous_world(client):
    world = create(client)
    invalid = dict(world['scene'], unsupported_field=True)
    path = f"/api/v1/worlds/{world['id']}"
    assert client.put(path + '/scene', json=invalid).status_code == 422
    assert client.get(path).json()['scene'] == world['scene']


def test_scene_save_and_reload(client):
    world = create(client)
    scene = world['scene']
    scene['name'] = '../../My experiment'
    saved = client.post('/api/v1/scenes', json=scene)
    assert saved.status_code == 200, saved.text
    assert '/' not in saved.json()['filename']
    listed = client.get('/api/v1/scenes').json()
    assert len(listed) == 1 and listed[0]['scene'] == scene
    assert create(client)['scene']['robot']['kind'] == 'car'


def test_templates_schema_health_and_unknown_template(client):
    assert len(client.get('/api/v1/templates').json()) >= 4
    assert 'properties' in client.get('/api/v1/schema').json()
    assert client.get('/api/v1/health').json()['status'] == 'ok'
    assert client.post('/api/v1/worlds', json={'template': 'no-such-template'}).status_code == 422
    assert client.post('/api/v1/worlds', json={'unknown': 1}).status_code == 422


def test_fluid_lifecycle_and_validation(client):
    r = client.post('/api/v1/fluids', json={'resolution': 16})
    assert r.status_code == 200, r.text
    fluid = r.json()
    p = f"/api/v1/fluids/{fluid['id']}"
    stepped = client.post(p + '/step', json={'steps': 2})
    assert stepped.status_code == 200, stepped.text
    assert stepped.json()['time'] > 0
    assert len(stepped.json()['density']) == 16
    assert client.post(p + '/step', json={'steps': 0}).status_code == 422
    assert client.post(p + '/reset').json()['time'] == 0
    assert client.delete(p).json()['deleted']
    assert client.post(p + '/step', json={'steps': 1}).status_code == 404


def test_fluid_geometry_and_diagnostics_are_available_over_http(client):
    body = {'name': 'wing', 'shape': 'naca2412', 'x': 0.45, 'y': 0.5, 'width': 0.5, 'height': 0.2, 'angle': 10.0}
    response = client.post('/api/v1/fluids', json={'resolution': 64, 'source_mode': 'rake', 'obstacles': [body]})
    assert response.status_code == 200, response.text
    state = response.json()['state']
    assert state['obstacle_outlines'][0]['name'] == 'wing'
    for field in ('speed', 'vorticity', 'pressure_correction'):
        assert len(state[field]) == 64
        assert all(len(row) == 64 for row in state[field])
    schema = client.get('/api/v1/fluid/schema').json()
    assert 'obstacles' in schema['properties']
    assert schema['$defs']['FluidObstacle']['properties']['angle']['description'].startswith('Counterclockwise')
    invalid = client.post('/api/v1/fluids', json={'obstacles': [body, body]})
    assert invalid.status_code == 422
    assert 'unique' in invalid.text


def test_concurrent_steps_are_serialized(client):
    world = create(client)
    url = f"/api/v1/worlds/{world['id']}/step"
    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(pool.map(lambda _: client.post(url, json={'demo': True, 'frames': 1}).status_code, range(20)))
    assert statuses == [200] * 20
    state = client.get(f"/api/v1/worlds/{world['id']}/state").json()
    assert state['time'] == pytest.approx(20 * world['scene']['physics']['timestep'])


def test_nonfinite_and_noninteger_inputs_return_validation_errors(client):
    world = create(client)
    path = f"/api/v1/worlds/{world['id']}"
    for action in [[float('nan'), 0], [float('inf'), 0]]:
        response = client.post(path + '/step', content=json.dumps({'action': action}), headers={'content-type': 'application/json'})
        assert response.status_code == 422
    for frames in [True, 2.0, '2']:
        response = client.post(path + '/step', json={'demo': True, 'frames': frames})
        assert response.status_code == 422
    assert client.get(path + '/state').json()['time'] == 0


def test_extreme_finite_scene_rejected_without_poisoning_sessions(client):
    for scene in [{'physics': {'gravity': [0, 0, 1e308]}}, {'robot': {'position': [1e308, 0, 1]}}]:
        response = client.post('/api/v1/worlds', json={'scene': scene})
        assert response.status_code == 422
        assert client.get('/api/v1/worlds').json() == []
    world = create(client)
    scene = world['scene']
    scene['physics']['gravity'] = [0, 0, 1e308]
    assert client.put(f"/api/v1/worlds/{world['id']}/scene", json=scene).status_code == 422
    assert client.get(f"/api/v1/worlds/{world['id']}/state").status_code == 200
