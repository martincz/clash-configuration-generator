import copy
import io
import ipaddress
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from ruamel.yaml import YAML

from libs.rule import Rule


class RulePolicyTests(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.write('configs/rulesets.yaml', {'prefix': [], 'suffix': []})
        self.write('rules/suffix.yaml', {'rules': ['MATCH,Proxy']})
        self.rule = Rule()
        self.rule.top_dir = str(self.root)

    def write(self, path, data):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('w', encoding='utf-8') as output:
            YAML().dump(data, output)

    def test_business_prefix_wins_over_more_precise_aggregate_rule(self):
        self.write('ai.yaml', {'payload': ['DOMAIN-SUFFIX,githubcopilot.com']})
        self.write('media.yaml', {'payload': ['DOMAIN,api.githubcopilot.com']})
        preference = {
            'rulesets-prefix': [{'group': 'AI', 'ruleset': 'ai.yaml'}],
            'rulesets': [{'group': 'GlobalMedia', 'ruleset': 'media.yaml'}],
            'rules-policy-priority': ['GlobalMedia', 'AI'],
        }

        rules = self.rule.getRules(preference)['rules']

        self.assertLess(
            rules.index('DOMAIN-SUFFIX,githubcopilot.com,AI'),
            rules.index('DOMAIN,api.githubcopilot.com,GlobalMedia'),
        )
        self.assertNotIn('rulesets-prefix', preference)

    def test_explicit_ruleset_replaces_default_even_with_lower_policy_priority(self):
        self.write('facebook.yaml', {'payload': ['DOMAIN-SUFFIX,facebook.com']})
        self.write('configs/rulesets.yaml', {
            'prefix': [],
            'suffix': [{'name': 'Facebook', 'group': 'Proxy', 'ruleset': 'facebook.yaml'}],
        })
        preference = {
            'rulesets': [{'name': 'Facebook', 'group': 'Static', 'ruleset': './facebook.yaml'}],
            'rules-policy-priority': ['Proxy', 'Static'],
        }
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            rules = self.rule.getRules(preference)['rules']

        self.assertIn('DOMAIN-SUFFIX,facebook.com,Static', rules)
        self.assertNotIn('DOMAIN-SUFFIX,facebook.com,Proxy', rules)
        self.assertNotIn('duplicated ruleset paths', stderr.getvalue())

    def test_prefix_block_order_and_conflict_warning_agree(self):
        self.write('same.yaml', {'payload': ['DOMAIN-SUFFIX,example.com']})
        preference = {
            'rulesets-prefix': [
                {'name': 'First', 'group': 'Static', 'ruleset': 'same.yaml'},
                {'name': 'Second', 'group': 'AI', 'ruleset': 'same.yaml'},
            ],
            'rules-policy-priority': ['AI', 'Static'],
        }
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            rules = self.rule.getRules(preference)['rules']

        self.assertEqual(rules[0], 'DOMAIN-SUFFIX,example.com,Static')
        self.assertNotIn('DOMAIN-SUFFIX,example.com,AI', rules)
        self.assertIn('winner=First(group=Static', stderr.getvalue())

    def test_media_ip_group_preserves_domains_and_explicit_patch(self):
        self.write('media.yaml', {'payload': [
            'DOMAIN-SUFFIX,video.example.com',
            'IP-CIDR,34.208.0.0/12,no-resolve',
            'IP-CIDR6,2001:db8::/32,no-resolve',
        ]})
        rules = self.rule.getRules({
            'rulesets': [{
                'name': 'Media', 'group': 'GlobalMedia', 'ip-group': 'Proxy',
                'ruleset': 'media.yaml',
            }],
            'ruleset-rule-patches': [{
                'name': 'Media',
                'override': [{'match': 'IP-CIDR6,2001:db8::/32', 'group': 'Static'}],
            }],
        })['rules']

        self.assertIn('DOMAIN-SUFFIX,video.example.com,GlobalMedia', rules)
        self.assertIn('IP-CIDR,34.208.0.0/12,Proxy,no-resolve', rules)
        self.assertIn('IP-CIDR6,2001:db8::/32,Static,no-resolve', rules)

    def test_ip_asn_preserves_flags_ip_group_and_cidr_precedence(self):
        self.write('media.yaml', {'payload': [
            'IP-ASN,32934,no-resolve',
            'IP-ASN,62041,no-resolve',
            'IP-CIDR,203.0.113.0/24,no-resolve',
            'DOMAIN-SUFFIX,video.example.com',
            'PROCESS-NAME,example-player',
        ]})
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            rules = self.rule.getRules({
                'rulesets': [{
                    'name': 'Media', 'group': 'GlobalMedia', 'ip-group': 'Proxy',
                    'ruleset': 'media.yaml',
                }],
                'rules-policy-priority': ['Static', 'Proxy', 'GlobalMedia'],
                'ruleset-rule-patches': [{
                    'name': 'Media',
                    'override': [{'match': 'IP-ASN,32934', 'group': 'Static'}],
                }],
                'rules-suffix': ['SRC-IP-CIDR,192.168.0.2/32,DIRECT'],
            })['rules']

        self.assertIn('DOMAIN-SUFFIX,video.example.com,GlobalMedia', rules)
        self.assertIn('IP-ASN,62041,Proxy,no-resolve', rules)
        self.assertLess(
            rules.index('IP-CIDR,203.0.113.0/24,Proxy,no-resolve'),
            rules.index('IP-ASN,32934,Static,no-resolve'),
        )
        self.assertLess(
            rules.index('IP-ASN,62041,Proxy,no-resolve'),
            rules.index('SRC-IP-CIDR,192.168.0.2/32,DIRECT'),
        )
        self.assertIn('PROCESS-NAME', stderr.getvalue())
        self.assertNotIn('IP-ASN', stderr.getvalue())

    def test_ip_asn_drop_and_policy_priority_apply_before_deduplication(self):
        self.write('fixed.yaml', {'payload': [
            'IP-ASN,32934,no-resolve', 'IP-ASN,62041,no-resolve',
        ]})
        self.write('general.yaml', {'payload': ['IP-ASN,32934']})

        rules = self.rule.getRules({
            'rulesets': [
                {'group': 'Proxy', 'ruleset': 'general.yaml'},
                {'group': 'Static', 'ruleset': 'fixed.yaml'},
            ],
            'rules-policy-priority': ['Static', 'Proxy'],
            'ruleset-rule-patches': [{'drop': ['IP-ASN,62041']}],
        })['rules']

        self.assertEqual(
            [rule for rule in rules if rule.startswith('IP-ASN,')],
            ['IP-ASN,32934,Static,no-resolve'],
        )

    def test_device_port_exceptions_are_not_deduplicated_together(self):
        first = 'AND,((SRC-IP-CIDR,192.168.0.2/32),(SRC-PORT,51413)),DIRECT'
        second = 'AND,((SRC-IP-CIDR,192.168.0.2/32),(SRC-PORT,51414)),DIRECT'
        duplicate = 'AND,((SRC-IP-CIDR,192.168.0.2/32),(SRC-PORT,51413)),Proxy'

        rules = self.rule.getRules({'rules-prefix': [first, second, duplicate]})['rules']

        self.assertEqual(rules, [first, second, 'MATCH,Proxy'])


class BusinessRoutingTests(unittest.TestCase):
    """Check repository rule data with domain/IP metadata, without external DNS."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parent.parent
        rule = Rule()
        rule.top_dir = str(cls.root)
        preference = {
            'rulesets-prefix': [
                {'name': 'Lan', 'group': 'DIRECT', 'ruleset': 'rules/blackmatrix7/Lan/Lan_No_Resolve.yaml'},
                {'name': 'Speedtest', 'group': 'Speedtest', 'ruleset': 'rules/blackmatrix7/Speedtest/Speedtest_No_Resolve.yaml'},
                {'name': 'SpeedtestSupplement', 'group': 'Speedtest', 'ruleset': 'rules/martincz/Speedtest/Speedtest.yaml'},
                {'name': 'Payment', 'group': 'Secure', 'ruleset': 'rules/martincz/Payment/Payment.yaml'},
                {'name': 'AI', 'group': 'AI', 'ruleset': 'rules/martincz/AI/AI.yaml'},
                {'name': 'ChatGPTVoice', 'group': 'AI', 'ruleset': 'rules/martincz/AI/ChatGPTVoice.yaml'},
                {'name': 'Media', 'group': 'GlobalMedia', 'ruleset': 'rules/martincz/Media/Media.yaml'},
                {'name': 'MediaIP', 'group': 'GlobalMedia', 'ruleset': 'rules/martincz/Media/MediaIP.yaml'},
            ],
            'rulesets': [
                {'name': 'SharedServices', 'group': 'Proxy', 'ruleset': 'rules/martincz/SharedServices/SharedServices.yaml'},
                {'name': 'PayPal', 'group': 'Secure', 'ruleset': 'rules/blackmatrix7/PayPal/PayPal_No_Resolve.yaml'},
                {'name': 'GitHub', 'group': 'Proxy', 'ruleset': 'rules/blackmatrix7/GitHub/GitHub_No_Resolve.yaml'},
                {'name': 'TikTok', 'group': 'GlobalMedia', 'ruleset': 'rules/blackmatrix7/TikTok/TikTok_No_Resolve.yaml'},
                {'name': 'Facebook', 'group': 'Static', 'ruleset': 'rules/blackmatrix7/Facebook/Facebook_No_Resolve.yaml'},
                {'name': 'Nintendo', 'group': 'Game', 'ip-group': 'Proxy', 'ruleset': 'rules/blackmatrix7/Nintendo/Nintendo_No_Resolve.yaml'},
            ],
            'rules-policy-priority': ['Speedtest', 'Secure', 'AI', 'Static', 'DIRECT', 'GlobalMedia', 'Proxy', 'Apple', 'Hijacking'],
            'ruleset-rule-patches': [{
                'override': [
                    {'match': 'DOMAIN-SUFFIX,cloudfront.net', 'group': 'Proxy'},
                    {'match': 'DOMAIN-SUFFIX,akamaized.net', 'group': 'Proxy'},
                    {'match': 'DOMAIN-SUFFIX,amazonaws.com', 'group': 'Proxy'},
                    {'match': 'DOMAIN-SUFFIX,amazonaws.co.uk', 'group': 'Proxy'},
                ],
            }],
        }
        with redirect_stderr(io.StringIO()):
            cls.rules = rule.getRules(copy.deepcopy(preference))['rules']

    def domain_policy(self, domain):
        for rule in self.rules:
            parts = rule.split(',')
            kind, matcher = parts[:2]
            matcher = matcher.lower().removeprefix('+.').removeprefix('.')
            if ((kind == 'DOMAIN' and domain == matcher)
                    or (kind == 'DOMAIN-SUFFIX' and (domain == matcher or domain.endswith('.' + matcher)))
                    or (kind == 'DOMAIN-KEYWORD' and matcher in domain)):
                return parts[2]
            if kind == 'MATCH':
                return parts[1]
        self.fail('No matching rule for ' + domain)

    def test_ai_services_keep_business_policy(self):
        domains = [
            'auth.openai.com', 'chatgpt.com', 'oaistatsig.com',
            'claude.ai', 'claude.com', 'bridge.claudeusercontent.com', 'claude.sites',
            'widget.claudemcpcontent.com',
            'api2.cursor.sh', 'marketplace.cursorapi.com', 'cursor-cdn.com',
            'agent.region.cursorvm.com', 'accounts.spacexsi.com',
            'auth.grokusercontent.com', 'auth.grokipedia.com',
            'api.githubcopilot.com', 'api.individual.githubcopilot.com',
            'api.business.githubcopilot.com', 'api.enterprise.githubcopilot.com',
            'copilot-proxy.githubusercontent.com', 'copilot.microsoft.com',
            'gemini.google.com', 'aistudio.google.com', 'notebooklm.google.com',
            'generativelanguage.googleapis.com', 'perplexity.ai', 'grok.com',
            'www.bing.com', 'api.groq.com', 'console.groq.com',
            'api.together.ai', 'us-api.together.ai', 'api.together.xyz',
        ]
        for domain in domains:
            with self.subTest(domain=domain):
                self.assertEqual(self.domain_policy(domain), 'AI')

    def test_media_payment_and_shared_services_stay_separate(self):
        expected = {
            'paypal.com': 'Secure', 'paypalobjects.com': 'Secure',
            'paypal.github.io': 'Proxy',
            'checkout.stripe.com': 'Secure', 'billing.stripe.com': 'Secure', 'buy.stripe.com': 'Secure',
            'api.stripe.com': 'Secure', 'hooks.stripe.com': 'Secure',
            'link.com': 'Secure', 'checkout.link.com': 'Secure',
            'tiktok.com': 'GlobalMedia', 'capcutapi.com': 'GlobalMedia',
            'youtube.com': 'GlobalMedia', 'googlevideo.com': 'GlobalMedia',
            'netflix.com': 'GlobalMedia', 'tv.apple.com': 'GlobalMedia',
            'www.bilibili.tv': 'GlobalMedia', 'biliintl.com': 'GlobalMedia',
            'www.iq.com': 'GlobalMedia', 'intl.iqiyi.com': 'GlobalMedia',
            'intl-subscription.iqiyi.com': 'GlobalMedia',
            'wetv.vip': 'GlobalMedia', 'static.wetvinfo.com': 'GlobalMedia',
            'upos-bstar-mirrorakam.akamaized.net': 'GlobalMedia',
            'www.bilibili.com': 'DIRECT', 'www.iqiyi.com': 'DIRECT',
            'v.qq.com': 'DIRECT',
            'p16-tiktokcdn-com.akamaized.net': 'GlobalMedia',
            'facebook.com': 'Static', 'instagram.com': 'Static',
            'auth0.com': 'Proxy', 'stripe.com': 'Proxy', 'sentry.io': 'Proxy',
            'js.stripe.com': 'Proxy',
            'setup.workos.com': 'Proxy', 'generic.cloudfront.net': 'Proxy',
            's3.amazonaws.com': 'Proxy', 'sts.amazonaws.com': 'Proxy',
            'checkip.amazonaws.com': 'Proxy', 'generic.amazonaws.co.uk': 'Proxy',
            'primevideo.com': 'GlobalMedia', 'amazonvideo.com': 'GlobalMedia',
            'o207216.ingest.sentry.io': 'AI',
            'disney.my.sentry.io': 'GlobalMedia',
            'upos-hz-mirrorakam.akamaized.net': 'DIRECT',
        }
        for domain, policy in expected.items():
            with self.subTest(domain=domain):
                self.assertEqual(self.domain_policy(domain), policy)

    def test_speedtests_use_their_group_and_keep_shared_media_cdn_separate(self):
        expected = {
            'fast.com': 'Speedtest', 'speedtest.net': 'Speedtest',
            'speed.cloudflare.com': 'Speedtest', 'nperf.com': 'Speedtest',
            'api.nperf.com': 'Speedtest', 'speedof.me': 'Speedtest',
            'cdn3.speedof.me': 'Speedtest', 'testmy.net': 'Speedtest',
            'download.testmy.net': 'Speedtest',
            'nflxvideo.net': 'GlobalMedia',
        }
        for domain, policy in expected.items():
            with self.subTest(domain=domain):
                self.assertEqual(self.domain_policy(domain), policy)

    def test_repository_asn_rules_keep_their_business_groups(self):
        expected = {'IP-ASN,32934,Static,no-resolve'}
        expected.update(
            f'IP-ASN,{asn},Proxy,no-resolve'
            for asn in ('211157', '44907', '59930', '62014', '62041')
        )
        self.assertEqual(
            {rule for rule in self.rules if rule.startswith('IP-ASN,')},
            expected,
        )

    def test_shared_cloud_and_media_owned_ips_have_distinct_policies(self):
        expected = {
            '34.208.0.1': 'Proxy', '35.160.0.1': 'Proxy', '35.192.0.1': 'Proxy',
            '45.57.0.1': 'GlobalMedia', '23.246.0.1': 'GlobalMedia',
            '192.168.0.1': 'DIRECT',
        }
        for address, policy in expected.items():
            with self.subTest(address=address):
                target = ipaddress.ip_address(address)
                for rule in self.rules:
                    parts = rule.split(',')
                    if parts[0] not in ['IP-CIDR', 'IP-CIDR6']:
                        continue
                    network = ipaddress.ip_network(parts[1], strict=False)
                    if network.version == target.version and target in network:
                        self.assertEqual(parts[2], policy)
                        break
                else:
                    self.fail('No explicit IP rule for ' + address)

    def test_all_snapshotted_voice_addresses_keep_ai_policy(self):
        payload = YAML(typ='safe').load(
            (self.root / 'rules/martincz/AI/ChatGPTVoice.yaml').read_text(encoding='utf-8')
        )['payload']
        self.assertTrue(payload)
        for raw in payload:
            prefix = ipaddress.ip_network(raw.split(',')[1])
            target = prefix.network_address
            with self.subTest(prefix=str(prefix)):
                for rule in self.rules:
                    parts = rule.split(',')
                    if parts[0] not in ['IP-CIDR', 'IP-CIDR6']:
                        continue
                    network = ipaddress.ip_network(parts[1], strict=False)
                    if network.version == target.version and target in network:
                        self.assertEqual(parts[2], 'AI')
                        break
                else:
                    self.fail('Voice address has no explicit policy: ' + str(target))


if __name__ == '__main__':
    unittest.main()
