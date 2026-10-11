"""HTTP transport. Only explicit step calls advance simulation time."""
from __future__ import annotations

import importlib.util
import platform
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import mujoco
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import __version__
from .engine import Simulation
from .fluids import FluidConfig, FluidSimulation
from .scenes import get_template, templates
from .schema import SceneConfig

ROOT = Path(__file__).resolve().parent.parent


class Request(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, strict=True)


class WorldRequest(Request):
    template: str = 'driving'
    scene: SceneConfig | None = None


class ResetRequest(Request):
    seed: Annotated[int, Field(ge=0, le=2**32 - 1)] | None = None


class StepRequest(Request):
    action: list[float] | None = None
    frames: Annotated[int, Field(ge=1, le=100)] | None = None
    demo: bool = False

    @model_validator(mode='after')
    def control_source(self):
        if (self.action is None) == (not self.demo):
            raise ValueError('Provide either action or demo=true, never both')
        return self


class FluidStepRequest(Request):
    steps: Annotated[int, Field(ge=1, le=20)] = 1


@dataclass
class Session:
    simulation: Simulation | FluidSimulation
    lock: threading.RLock = field(default_factory=threading.RLock)


def create_app(data_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title='Kinetic RL Sim', version=__version__, description='Explicit, fixed-time-step physics. Units: SI; coordinates: z-up; quaternions: wxyz.')
    worlds: dict[str, Session] = {}
    fluids: dict[str, Session] = {}
    registry_lock = threading.RLock()
    storage = Path(data_dir) if data_dir is not None else ROOT / 'data' / 'scenes'

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, exc):
        # Never echo NaN/Infinity or exception objects into JSON error payloads.
        errors = [{key: error[key] for key in ('loc', 'msg', 'type')} for error in exc.errors()]
        return JSONResponse(status_code=422, content={'detail': errors})

    def lookup(registry, key):
        with registry_lock:
            value = registry.get(key)
        if value is None:
            raise HTTPException(404, 'Session not found; create or select a world again')
        return value

    def add(registry, simulation):
        with registry_lock:
            if len(registry) >= 64:
                raise HTTPException(409, 'Session limit (64) reached; delete unused sessions')
            key = uuid4().hex
            registry[key] = Session(simulation)
        return key

    def envelope(key, sim):
        return dict(id=key, scene=sim.scene.model_dump(mode='json'), description=sim.description(), state=sim.snapshot())

    @app.get('/api/v1/health')
    def health():
        return dict(status='ok', version=__version__, capabilities=dict(
            engine='MuJoCo', engine_version=mujoco.__version__, platform=platform.system(), architecture=platform.machine(),
            native_backend='cpu', studio=True, fluids='2d-incompressible-standalone',
            mjx_installed=importlib.util.find_spec('mujoco.mjx') is not None,
            gpu_note='GPU batching uses the optional MJX runner; HTTP worlds use native CPU physics.',
        ))

    @app.get('/api/v1/templates')
    def list_templates():
        return templates()

    @app.get('/api/v1/schema')
    def schema():
        return SceneConfig.model_json_schema()

    @app.post('/api/v1/worlds')
    def create_world(body: WorldRequest):
        try:
            scene = body.scene if body.scene is not None else get_template(body.template)
            sim = Simulation(scene)
        except (ValueError, KeyError) as exc:
            raise HTTPException(422, str(exc)) from exc
        key = add(worlds, sim)
        return envelope(key, sim)

    @app.get('/api/v1/worlds')
    def list_worlds():
        with registry_lock:
            entries = list(worlds.items())
        result = []
        for key, session in entries:
            with session.lock:
                sim = session.simulation
                result.append(dict(id=key, name=sim.scene.name, robot=sim.scene.robot.kind, time=float(sim.data.time)))
        return result

    @app.get('/api/v1/worlds/{key}')
    def get_world(key: str):
        session = lookup(worlds, key)
        with session.lock:
            return envelope(key, session.simulation)

    @app.get('/api/v1/worlds/{key}/state')
    def get_state(key: str):
        session = lookup(worlds, key)
        with session.lock:
            return session.simulation.snapshot()

    @app.put('/api/v1/worlds/{key}/scene')
    def replace_scene(key: str, body: SceneConfig):
        session = lookup(worlds, key)
        try:
            candidate = Simulation(body)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        with session.lock:
            session.simulation = candidate
            return envelope(key, candidate)

    @app.post('/api/v1/worlds/{key}/reset')
    def reset_world(key: str, body: ResetRequest):
        session = lookup(worlds, key)
        with session.lock:
            return session.simulation.reset(seed=body.seed)

    @app.post('/api/v1/worlds/{key}/step')
    def step_world(key: str, body: StepRequest):
        session = lookup(worlds, key)
        with session.lock:
            try:
                sim = session.simulation
                return sim.step(sim.demo_action() if body.demo else body.action, frames=body.frames)
            except (ValueError, RuntimeError) as exc:
                raise HTTPException(422, str(exc)) from exc

    @app.delete('/api/v1/worlds/{key}')
    def delete_world(key: str):
        with registry_lock:
            lookup(worlds, key)
            del worlds[key]
        return {'deleted': True}

    @app.post('/api/v1/scenes')
    def save_scene(body: SceneConfig):
        storage.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r'[^a-z0-9_-]+', '-', body.name.lower()).strip('-')[:60] or 'scene'
        filename = f'{slug}-{uuid4().hex[:8]}.json'
        target = storage / filename
        temporary = target.with_suffix('.tmp')
        temporary.write_text(body.model_dump_json(indent=2) + '\n')
        temporary.replace(target)
        return dict(name=body.name, filename=filename)

    @app.get('/api/v1/scenes')
    def list_scenes():
        result = []
        for file in sorted(storage.glob('*.json')):
            try:
                scene = SceneConfig.model_validate_json(file.read_text())
            except (ValueError, OSError):
                continue
            result.append(dict(name=scene.name, filename=file.name, scene=scene.model_dump(mode='json')))
        return result

    @app.get('/api/v1/fluid/schema')
    def fluid_schema():
        return FluidConfig.model_json_schema()

    @app.post('/api/v1/fluids')
    def create_fluid(body: FluidConfig):
        sim = FluidSimulation(body)
        key = add(fluids, sim)
        return dict(id=key, state=sim.snapshot())

    @app.post('/api/v1/fluids/{key}/step')
    def step_fluid(key: str, body: FluidStepRequest):
        session = lookup(fluids, key)
        with session.lock:
            session.simulation.step(body.steps)
            return session.simulation.snapshot()

    @app.post('/api/v1/fluids/{key}/reset')
    def reset_fluid(key: str):
        session = lookup(fluids, key)
        with session.lock:
            session.simulation.reset()
            return session.simulation.snapshot()

    @app.delete('/api/v1/fluids/{key}')
    def delete_fluid(key: str):
        with registry_lock:
            lookup(fluids, key)
            del fluids[key]
        return {'deleted': True}

    dist = ROOT / 'web' / 'dist'
    if (dist / 'assets').exists():
        app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')

    @app.get('/kinetic.svg', include_in_schema=False)
    def favicon():
        target = ROOT / 'web' / 'public' / 'kinetic.svg'
        if not target.exists():
            raise HTTPException(404)
        return FileResponse(target, media_type='image/svg+xml')

    @app.get('/', include_in_schema=False)
    def studio():
        if (dist / 'index.html').exists():
            return FileResponse(dist / 'index.html')
        return {'message': 'Build the studio: cd web && npm install && npm run build', 'api': '/docs'}

    return app


app = create_app()
