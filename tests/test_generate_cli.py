import importlib.util
import io
import os
import tempfile
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import patch

from ruamel.yaml import YAML

import libs.dns as dns_module
import libs.preference as preference_module
import libs.proxy_group as proxy_group_module
import libs.rule as rule_module


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

    def test_lf_and_crlf_inputs_generate_identical_utf8_files(self):
        temp_dir = self._prepare_temp_root()
        self.addCleanup(temp_dir.cleanup)
        self.generate.ROOT_DIR = temp_dir.name
        base = '# 基础配置\nport: 7890\nrules: []\n'
        preference = (
            'proxies:\n'
            '  - name: "节点" # 节点注释\n'
            '    type: socks5\n'
            '    server: 127.0.0.1\n'
            '    port: 1080\n'
            'message: "first\\rsecond"\n'
            'dns:\n'
            '  enable: true\n'
            'rules:\n'
            '  - MATCH,Proxy\n'
        )
        for dns_args in [[], ['--dns']]:
            outputs = []
            for line_ending in ['\n', '\r\n']:
                for output_mode in ['default', 'custom']:
                    with self.subTest(dns=dns_args, ending=repr(line_ending), output=output_mode):
                        Path(temp_dir.name, 'configs', 'basic.yaml').write_bytes(
                            base.replace('\n', line_ending).encode('utf-8')
                        )
                        parsed = YAML().load(preference.replace('\n', line_ending).encode('utf-8'))
                        self.generate.getPreference = lambda: parsed
                        target = Path(temp_dir.name, 'config.yaml' if output_mode == 'default' else 'custom.yaml')
                        args = dns_args if output_mode == 'default' else dns_args + ['--output', str(target)]

                        self.assertEqual(self.generate.main(args), 0)

                        content = target.read_bytes()
                        self.assertNotIn(b'\r', content)
                        self.assertFalse(content.startswith(b'\xef\xbb\xbf'))
                        self.assertIn('节点'.encode('utf-8'), content)
                        data = YAML(typ='safe').load(content)
                        self.assertEqual(data['message'], 'first\rsecond')
                        self.assertEqual('dns' in data, bool(dns_args))
                        outputs.append(content)
            self.assertTrue(all(content == outputs[0] for content in outputs))

    def test_output_matches_platform_independent_bytes(self):
        temp_dir = self._prepare_temp_root()
        self.addCleanup(temp_dir.cleanup)
        self.generate.ROOT_DIR = temp_dir.name
        self.generate.getPreference = lambda: {}
        source = '# 基础配置\nport: 7890\nnote: "中文"\ndns:\n  enable: true\nrules:\n  - MATCH,Proxy\n'
        Path(temp_dir.name, 'configs', 'basic.yaml').write_bytes(
            source.replace('\n', '\r\n').encode('utf-8')
        )

        self.assertEqual(self.generate.main(['--dns']), 0)

        self.assertEqual(Path(temp_dir.name, 'config.yaml').read_bytes(), source.encode('utf-8'))

    def test_full_input_pipeline_preserves_blank_lines_across_line_endings(self):
        temp_dir = self._prepare_temp_root()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        self.generate.ROOT_DIR = str(root)
        files = {
            'configs/basic.yaml': '# 基础配置\nport: 7890\n\nrules: []\n',
            'configs/dns.yaml': 'dns:\n  enable: true\n',
            'configs/proxy-groups.yaml': (
                '- name: Proxy\n  type: select\n  proxies: [".*"]\n\n'
                '- name: Other\n  type: select\n  proxies: [".*"]\n'
            ),
            'configs/rulesets.yaml': 'prefix: []\nsuffix: []\n',
            'rules/suffix.yaml': 'rules: ["MATCH,Proxy"]\n',
            'preference.yaml': (
                'proxies:\n'
                '  - {name: "节点一", type: socks5, server: 127.0.0.1, port: 1080}\n\n'
                '  - {name: "节点二", type: socks5, server: 127.0.0.1, port: 1081}\n\n'
                'proxy-groups:\n'
                '  - name: Custom\n    type: select\n    proxies: [".*"]\n\n'
                'rules-prefix: []\n'
            ),
        }
        outputs = []
        for ending, bom in [('\n', b''), ('\r\n', b''), ('\r\n', b'\xef\xbb\xbf')]:
            with self.subTest(ending=repr(ending), bom=bool(bom)):
                for name, text in files.items():
                    target = root / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(bom + text.replace('\n', ending).encode('utf-8'))
                with ExitStack() as stack:
                    for module, name in [
                        (dns_module, 'dns.py'), (preference_module, 'preference.py'),
                        (proxy_group_module, 'proxy_group.py'), (rule_module, 'rule.py'),
                    ]:
                        stack.enter_context(patch.object(module, '__file__', str(root / 'libs' / name)))
                    self.assertEqual(self.generate.main(['--dns']), 0)
                content = (root / 'config.yaml').read_bytes()
                self.assertNotIn(b'\r', content)
                self.assertFalse(content.startswith(b'\xef\xbb\xbf'))
                outputs.append(content)
        self.assertTrue(all(content == outputs[0] for content in outputs))

    def test_stdout_bytes_match_file_under_windows_text_stream_settings(self):
        temp_dir = self._prepare_temp_root()
        self.addCleanup(temp_dir.cleanup)
        self.generate.ROOT_DIR = temp_dir.name
        target = Path(temp_dir.name, 'preview.yaml')
        for option in ['--stdout', '--dry-run']:
            for encoding, newline in [('utf-8', '\n'), ('utf-8', '\r\n'), ('cp1252', '\r\n')]:
                with self.subTest(option=option, encoding=encoding, newline=repr(newline)):
                    self.generate.getPreference = lambda: {'note': '中文', 'rules': ['MATCH,Proxy']}
                    raw = io.BytesIO()
                    stdout = io.TextIOWrapper(raw, encoding=encoding, newline=newline)
                    try:
                        with redirect_stdout(stdout):
                            rc = self.generate.main([option, '--output', str(target)])
                        stdout.flush()
                        content = raw.getvalue()
                    finally:
                        stdout.detach()

                    self.assertEqual(rc, 0)
                    self.assertEqual(content, target.read_bytes())
                    self.assertNotIn(b'\r', content)
                    self.assertIn('中文'.encode('utf-8'), content)

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
