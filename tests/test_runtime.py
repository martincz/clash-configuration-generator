import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from libs.runtime import use_project_python


class ProjectRuntimeTests(unittest.TestCase):

    def test_missing_project_environment_keeps_current_interpreter(self):
        with tempfile.TemporaryDirectory() as root:
            with patch('libs.runtime.os.execv') as execute, patch('libs.runtime.subprocess.call') as spawn:
                use_project_python(root)
        execute.assert_not_called()
        spawn.assert_not_called()

    def test_directory_alias_does_not_relaunch_project_interpreter(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = root / ('.venv-windows' if sys.platform == 'win32' else '.venv')
            executable = environment / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
            executable.parent.mkdir(parents=True)
            executable.touch()
            with patch('libs.runtime.sys.prefix', str(environment) + '/.'):
                with patch('libs.runtime.os.execv') as execute, patch('libs.runtime.subprocess.call') as spawn:
                    use_project_python(root)
        execute.assert_not_called()
        spawn.assert_not_called()

    def test_windows_relaunch_preserves_output_paths_and_exit_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / '.venv-windows/Scripts/python.exe'
            executable.parent.mkdir(parents=True)
            executable.touch()
            arguments = ['generate', '--output', 'folder with spaces/config.yaml']
            with patch('libs.runtime.sys.platform', 'win32'), patch('libs.runtime.sys.prefix', str(root)):
                with patch('libs.runtime.sys.argv', arguments), patch('libs.runtime.sys.dont_write_bytecode', True):
                    with patch('libs.runtime.subprocess.call', return_value=2) as spawn:
                        with self.assertRaises(SystemExit) as result:
                            use_project_python(root)
            self.assertEqual(result.exception.code, 2)
            spawn.assert_called_once_with([str(executable), '-B', *arguments])


if __name__ == '__main__':
    unittest.main()
