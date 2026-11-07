#!/usr/bin/env python
"""Refresh the checked-in ChatGPT Voice IP snapshot; generation stays offline."""

import argparse
import hashlib
import ipaddress
import json
import os
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
SOURCE_URL = 'https://openai.com/chatgpt-voice.json'
OUTPUT_PATH = Path('rules/martincz/AI/ChatGPTVoice.yaml')


def parse_voice_prefixes(data):
    if not isinstance(data, dict) or not isinstance(data.get('prefixes'), list):
        raise ValueError('Voice source must contain a prefixes list')
    networks = set()
    for record in data['prefixes']:
        if not isinstance(record, dict):
            raise ValueError('Voice prefix records must be objects')
        fields = [key for key in ('ipv4Prefix', 'ipv6Prefix') if key in record]
        if len(fields) != 1:
            raise ValueError('Each voice record must contain exactly one IP prefix')
        if not isinstance(record[fields[0]], str):
            raise ValueError('Voice prefixes must be strings')
        network = ipaddress.ip_network(record[fields[0]], strict=True)
        version = 4 if fields[0] == 'ipv4Prefix' else 6
        if (network.version != version or network.prefixlen == 0
                or not network.is_global or network.is_multicast or network.is_reserved):
            raise ValueError('Voice source contains an invalid or non-public prefix')
        networks.add(network)
    if not networks:
        raise ValueError('Voice source is empty; the existing snapshot is preserved')
    return sorted(networks, key=lambda item: (item.version, int(item.network_address), item.prefixlen))


def render_voice_rules(raw, updated_at=None):
    data = json.loads(raw)
    networks = parse_voice_prefixes(data)
    updated_at = updated_at or datetime.now(timezone.utc).isoformat(timespec='seconds')
    lines = [
        '# NAME: ChatGPTVoice',
        '# SOURCE: ' + SOURCE_URL,
        '# FETCHED: ' + updated_at,
        '# SOURCE-CREATED: ' + str(data.get('creationTime', 'unknown')),
        '# SOURCE-SHA256: ' + hashlib.sha256(raw).hexdigest(),
        '# PREFIXES: ' + str(len(networks)),
        '# OpenAI voice relay addresses; import as a front ruleset with group AI.',
        '# Refresh manually with python update_voice_rules.py. generate never downloads rules.',
        'payload:',
    ]
    for network in networks:
        kind = 'IP-CIDR' if network.version == 4 else 'IP-CIDR6'
        lines.append('  - ' + kind + ',' + str(network) + ',no-resolve')
    return ('\n'.join(lines) + '\n').encode('utf-8')


def fetch_voice_source():
    request = urllib.request.Request(SOURCE_URL, headers={'User-Agent': 'clash-configuration-generator'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def update_voice_rules(root=ROOT_DIR, fetch=None, updated_at=None):
    raw = (fetch or fetch_voice_source)()
    # Fetch and validate before touching the existing snapshot.
    content = render_voice_rules(raw, updated_at)
    target = Path(root) / OUTPUT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.voice-', delete=False) as output:
            temporary = Path(output.name)
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return len(parse_voice_prefixes(json.loads(raw)))


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(args)
    try:
        count = update_voice_rules()
    except (OSError, ValueError) as error:
        print('Voice update failed; existing rules were preserved: ' + str(error), file=sys.stderr)
        return 1
    print('Updated ' + str(OUTPUT_PATH) + ': ' + str(count) + ' prefixes')
    return 0


if __name__ == '__main__':
    from libs.runtime import use_project_python
    use_project_python(ROOT_DIR)
    raise SystemExit(main())
