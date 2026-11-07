import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which('git'), 'Git is required for checkout normalization tests')
class GitLineEndingTests(unittest.TestCase):

    def test_legacy_text_and_checkout_use_lf_for_all_autocrlf_settings(self):
        attributes = (Path(__file__).resolve().parent.parent / '.gitattributes').read_bytes()
        expected = '# 中文\nvalue: example\n'.encode('utf-8')
        binary = b'\x00binary\r\nunchanged\x00'

        for setting in ['true', 'input', 'false']:
            with self.subTest(autocrlf=setting), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)

                def git(*args):
                    return subprocess.run(
                        ['git', '-C', str(root), *args],
                        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    ).stdout

                git('init', '--quiet')
                git('config', 'core.autocrlf', 'false')
                git('config', 'core.safecrlf', 'false')
                names = ['legacy.yaml', 'example.py', 'rules.list', 'README.md', 'generate']
                for name in names:
                    (root / name).write_bytes(expected.replace(b'\n', b'\r\n'))
                (root / 'example.bin').write_bytes(binary)
                git('add', '--', *names, 'example.bin')
                self.assertIn(b'\r\n', git('show', ':legacy.yaml'))

                (root / '.gitattributes').write_bytes(attributes)
                git('config', 'core.autocrlf', setting)
                git('add', '--', '.gitattributes', *names, 'example.bin')
                for name in names:
                    self.assertEqual(git('show', ':' + name), expected)
                    (root / name).unlink()
                (root / 'example.bin').unlink()
                git('checkout-index', '--all', '--force')

                for name in names:
                    self.assertEqual((root / name).read_bytes(), expected)
                self.assertEqual((root / 'example.bin').read_bytes(), binary)


if __name__ == '__main__':
    unittest.main()
