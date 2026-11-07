import hashlib
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from ruamel.yaml import YAML

import update_voice_rules as updater


class VoiceSnapshotTests(unittest.TestCase):

    def source(self):
        return json.dumps({
            'creationTime': '2026-11-07T00:00:00Z',
            'prefixes': [
                {'ipv4Prefix': '8.8.8.8/32'},
                {'ipv4Prefix': '1.1.1.1/32'},
                {'ipv4Prefix': '8.8.8.8/32'},
                {'ipv6Prefix': '2607:fb10::1/128'},
            ],
        }).encode('utf-8')

    def test_snapshot_is_deterministic_and_records_source_digest(self):
        raw = self.source()
        content = updater.render_voice_rules(raw, '2026-11-08T00:00:00Z')
        self.assertNotIn(b'\r', content)
        self.assertIn(hashlib.sha256(raw).hexdigest().encode('ascii'), content)
        payload = YAML(typ='safe').load(content)['payload']
        self.assertEqual(payload, [
            'IP-CIDR,1.1.1.1/32,no-resolve',
            'IP-CIDR,8.8.8.8/32,no-resolve',
            'IP-CIDR6,2607:fb10::1/128,no-resolve',
        ])

    def test_failed_download_preserves_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / updater.OUTPUT_PATH
            target.parent.mkdir(parents=True)
            target.write_bytes(b'previous snapshot\n')
            def failed_fetch():
                raise urllib.error.URLError('fixture unavailable')
            with self.assertRaises(urllib.error.URLError):
                updater.update_voice_rules(root, fetch=failed_fetch)
            self.assertEqual(target.read_bytes(), b'previous snapshot\n')

    def test_invalid_sources_preserve_previous_snapshot(self):
        sources = [
            {}, {'prefixes': []}, {'prefixes': ['1.1.1.1/32']},
            {'prefixes': [{'ipv4Prefix': '0.0.0.0/0'}]},
            {'prefixes': [{'ipv4Prefix': '192.168.0.1/32'}]},
            {'prefixes': [{'ipv4Prefix': '224.0.0.1/32'}]},
            {'prefixes': [{'ipv4Prefix': 'not-a-network'}]},
            {'prefixes': [{'ipv4Prefix': ['1.1.1.1/32']}]},
        ]
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / updater.OUTPUT_PATH
            target.parent.mkdir(parents=True)
            target.write_bytes(b'previous snapshot\n')
            for data in sources:
                with self.subTest(data=data), self.assertRaises(ValueError):
                    updater.update_voice_rules(root, fetch=lambda: json.dumps(data).encode('utf-8'))
                self.assertEqual(target.read_bytes(), b'previous snapshot\n')

    def test_failed_replace_preserves_snapshot_and_removes_temporary_file(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / updater.OUTPUT_PATH
            target.parent.mkdir(parents=True)
            target.write_bytes(b'previous snapshot\n')
            with patch('update_voice_rules.os.replace', side_effect=OSError('fixture write failure')):
                with self.assertRaises(OSError):
                    updater.update_voice_rules(root, fetch=self.source)
            self.assertEqual(target.read_bytes(), b'previous snapshot\n')
            self.assertEqual(list(target.parent.glob('.voice-*')), [])

    def test_valid_source_replaces_snapshot(self):
        with tempfile.TemporaryDirectory() as root:
            count = updater.update_voice_rules(root, fetch=self.source, updated_at='2026-11-08T00:00:00Z')
            target = Path(root) / updater.OUTPUT_PATH
            self.assertEqual(count, 3)
            self.assertEqual(target.read_bytes(), updater.render_voice_rules(self.source(), '2026-11-08T00:00:00Z'))


if __name__ == '__main__':
    unittest.main()
