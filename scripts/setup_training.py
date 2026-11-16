#!/usr/bin/env python3
"""Explicit, isolated training setup. Never changes the API environment."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=('cpu', 'cu128'), default='cpu')
    parser.add_argument('--python', help='Optional compatible Python interpreter')
    parser.add_argument('--wheelhouse', help='Optional directory containing previously downloaded wheels')
    parser.add_argument('--offline', action='store_true', help='Install only from --wheelhouse and local pip cache')
    args = parser.parse_args()
    if args.offline and not args.wheelhouse:
        parser.error('--offline requires --wheelhouse')
    interpreter = args.python or shutil.which('python3.13') or shutil.which('python3.12') or sys.executable
    environment = ROOT / '.venv-training'
    python = environment / 'bin/python'
    if not python.exists():
        subprocess.run([interpreter, '-m', 'venv', str(environment)], check=True)
    pip = [str(python), '-m', 'pip']
    cache = ['--find-links', args.wheelhouse] if args.wheelhouse else []
    # Resolve the entire wheel set before installing. Python/CUDA combinations
    # without binary support fail without changing the working API environment.
    torch_args = [f'torch==2.11.0+{args.profile}', '--index-url', f'https://download.pytorch.org/whl/{args.profile}'] + cache
    if args.wheelhouse:
        tag = subprocess.check_output([str(python), '-c', 'import sys;print(f"cp{sys.version_info.major}{sys.version_info.minor}")'], text=True).strip()
        wheels = sorted(Path(args.wheelhouse).glob(f'torch-2.11.0+{args.profile}-{tag}-{tag}-*.whl'))
        if wheels:
            torch_args[0] = str(wheels[0].resolve())
    requirements = ['-r', str(ROOT / 'backend/requirements-training.txt')] + cache
    if args.offline:
        torch_args += ['--no-index']
        requirements += ['--no-index']
    for spec in (torch_args, requirements):
        subprocess.run(pip + ['install', '--dry-run', '--only-binary=:all:'] + spec, check=True)
    for spec in (torch_args, requirements):
        subprocess.run(pip + ['install', '--only-binary=:all:'] + spec, check=True)
    subprocess.run(pip + ['check'], check=True)
    installed = json.loads(subprocess.check_output(pip + ['list', '--format=json'], text=True))
    lock = ''.join(f"{package['name']}=={package['version']}\n" for package in installed if package['name'] != 'pip')
    (environment / 'installed-requirements.txt').write_text(lock)
    (environment / 'studio-runtime.json').write_text(json.dumps({'profile': args.profile, 'torch': '2.11.0'}))
    print('Training environment ready. Run training-runtime checks in the Studio.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, subprocess.CalledProcessError):
        print('Training setup failed. Select a supported Python and CPU/CUDA wheel profile, then retry. The API environment is unchanged.', file=sys.stderr)
        sys.exit(1)
