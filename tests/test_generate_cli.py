import importlib.util
import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from importlib.machinery import SourceFileLoader


def _load_generate_module(repo_root):
    path = os.path.join(repo_root, "generate")
    loader = SourceFileLoader("generate_module_for_tests", path)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class GenerateCliTests(unittest.TestCase):

    def setUp(self):
        self.repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.generate = _load_generate_module(self.repo_root)

    def _prepare_temp_root(self):
        temp_dir = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(temp_dir.name, "configs"), exist_ok=True)
        with open(os.path.join(temp_dir.name, "configs", "basic.yaml"), "w", encoding="utf-8") as fp:
            fp.write("port: 7890\nrules: []\n")
        return temp_dir

    def test_stdout_mode_does_not_write_default_config(self):
        temp_dir = self._prepare_temp_root()
        self.addCleanup(temp_dir.cleanup)

        self.generate.ROOT_DIR = temp_dir.name
        self.generate.getPreference = lambda: {"rules": ["MATCH,Proxy"], "dns": {"enable": True}}

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = self.generate.main(["--stdout"])

        self.assertEqual(rc, 0)
        self.assertIn("MATCH,Proxy", stdout.getvalue())
        self.assertFalse(os.path.exists(os.path.join(temp_dir.name, "config.yaml")))

    def test_output_mode_writes_target_file_only(self):
        temp_dir = self._prepare_temp_root()
        self.addCleanup(temp_dir.cleanup)

        output_path = os.path.join(temp_dir.name, "custom-output.yaml")
        self.generate.ROOT_DIR = temp_dir.name
        self.generate.getPreference = lambda: {"rules": ["MATCH,Proxy"]}

        rc = self.generate.main(["--output", output_path])

        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(output_path))
        self.assertFalse(os.path.exists(os.path.join(temp_dir.name, "config.yaml")))

    def test_output_mode_creates_parent_directories(self):
        temp_dir = self._prepare_temp_root()
        self.addCleanup(temp_dir.cleanup)

        output_path = os.path.join(temp_dir.name, "nested", "dir", "custom-output.yaml")
        self.generate.ROOT_DIR = temp_dir.name
        self.generate.getPreference = lambda: {"rules": ["MATCH,Proxy"]}

        rc = self.generate.main(["--output", output_path])

        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(output_path))

    def test_unknown_option_returns_error_code(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            rc = self.generate.main(["--unknown"])

        self.assertEqual(rc, 2)
        self.assertIn("Unknown option", stderr.getvalue())

    def test_positional_argument_returns_error_code(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            rc = self.generate.main(["build"])

        self.assertEqual(rc, 2)
        self.assertIn("Unexpected argument", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
