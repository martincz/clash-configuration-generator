"""Use the platform's project environment for command-line entry points."""

import os
import subprocess
import sys
from pathlib import Path


def use_project_python(root):
    root = Path(root)
    if sys.platform == 'win32':
        environment = root / '.venv-windows'
        executable = environment / 'Scripts' / 'python.exe'
    else:
        environment = root / '.venv'
        executable = environment / 'bin' / 'python'

    if not executable.is_file():
        return
    try:
        if os.path.samefile(sys.prefix, environment):
            return
    except OSError:
        pass

    args = [str(executable)]
    if sys.dont_write_bytecode:
        args.append('-B')
    args += sys.argv
    if sys.platform == 'win32':
        # subprocess quotes Windows arguments, including output paths with spaces.
        raise SystemExit(subprocess.call(args))
    os.execv(str(executable), args)
