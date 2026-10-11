"""Small local CLI; outputs always target the project unless explicitly chosen."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(prog='rl-sim', description='Kinetic physics studio and RL toolkit')
    commands = parser.add_subparsers(dest='command', required=True)
    serve = commands.add_parser('serve', help='Start API and built studio')
    serve.add_argument('--host', default='127.0.0.1')
    serve.add_argument('--port', type=int, default=8000)
    commands.add_parser('templates', help='List built-in scenes')
    export = commands.add_parser('export', help='Export a template as editable JSON')
    export.add_argument('template')
    export.add_argument('--output', type=Path)
    validate = commands.add_parser('validate', help='Validate and compile a scene, without advancing time')
    validate.add_argument('scene', type=Path)
    args = parser.parse_args()
    if args.command == 'serve':
        import uvicorn
        uvicorn.run('rl_sim.server:app', host=args.host, port=args.port)
    elif args.command == 'templates':
        from .scenes import templates
        for template in templates():
            print(f"{template['id']:12s} {template['name']} — {template['description']}")
    elif args.command == 'export':
        from .scenes import get_template
        text = get_template(args.template).model_dump_json(indent=2) + '\n'
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text)
            print(args.output)
        else:
            print(text, end='')
    elif args.command == 'validate':
        from .engine import Simulation
        from .schema import SceneConfig
        sim = Simulation(SceneConfig.model_validate_json(args.scene.read_text()))
        print(json.dumps({'valid': True, **sim.description()}, indent=2))


if __name__ == '__main__':
    main()
