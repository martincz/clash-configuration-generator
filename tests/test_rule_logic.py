import copy
import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr

from ruamel.yaml import YAML

from libs.rule import Rule


def _write_yaml(path, data):
    yaml = YAML()
    yaml.allow_unicode = True
    yaml.explicit_start = False
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    with open(path, "w", encoding="utf-8") as fp:
        yaml.dump(data, fp)


class RuleLogicTests(unittest.TestCase):

    def _build_rule(self, top_dir):
        rule = Rule()
        rule.top_dir = top_dir
        return rule

    def test_prefix_and_suffix_keep_position_semantics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, "configs"), exist_ok=True)
            os.makedirs(os.path.join(temp_dir, "rules"), exist_ok=True)
            os.makedirs(os.path.join(temp_dir, "rulesets"), exist_ok=True)

            _write_yaml(
                os.path.join(temp_dir, "configs", "rulesets.yaml"),
                {
                    "prefix": [{"name": "Prefix", "group": "Proxy", "ruleset": "rulesets/prefix.yaml"}],
                    "suffix": [{"name": "Suffix", "group": "GlobalMedia", "ruleset": "rulesets/suffix.yaml"}],
                },
            )
            _write_yaml(
                os.path.join(temp_dir, "rules", "suffix.yaml"),
                {"rules": ["MATCH,Proxy"]},
            )
            _write_yaml(
                os.path.join(temp_dir, "rulesets", "prefix.yaml"),
                {"payload": ["DOMAIN-SUFFIX,shared.com", "DOMAIN-SUFFIX,a.example.com"]},
            )
            _write_yaml(
                os.path.join(temp_dir, "rulesets", "pref.yaml"),
                {"payload": ["DOMAIN-SUFFIX,shared.com", "DOMAIN-SUFFIX,b.example.com"]},
            )
            _write_yaml(
                os.path.join(temp_dir, "rulesets", "suffix.yaml"),
                {"payload": ["DOMAIN-SUFFIX,shared.com", "DOMAIN-SUFFIX,c.example.com"]},
            )

            preference = {
                "rules-prefix": [
                    "DOMAIN-SUFFIX,shared.com,PrefixKeep",
                    "DOMAIN-SUFFIX,prefix-only.com,PrefixKeep",
                ],
                "rules-suffix": ["DOMAIN-SUFFIX,tail-only.com,TailKeep"],
                "rulesets": [{"name": "Pref", "group": "AI", "ruleset": "rulesets/pref.yaml"}],
            }

            rule = self._build_rule(temp_dir)
            generated = rule.getRules(copy.deepcopy(preference))["rules"]

            self.assertEqual(generated[0], "DOMAIN-SUFFIX,shared.com,PrefixKeep")

            shared = [line for line in generated if line.startswith("DOMAIN-SUFFIX,shared.com,")]
            self.assertEqual(len(shared), 1)
            self.assertEqual(shared[0], "DOMAIN-SUFFIX,shared.com,PrefixKeep")

            self.assertLess(
                generated.index("DOMAIN-SUFFIX,tail-only.com,TailKeep"),
                generated.index("MATCH,Proxy"),
            )

    def test_policy_priority_breaks_equal_specificity_conflicts(self):
        rule = Rule()
        rules = [
            "DOMAIN-SUFFIX,amazon.com,Proxy",
            "DOMAIN-SUFFIX,amazon.com,GlobalMedia",
        ]
        priorities = {"GlobalMedia": 0, "Proxy": 10}

        ordered = rule.optimizeRulesOrder(rules, priorities)
        deduplicated = rule.deduplicateRules(ordered)

        self.assertEqual(deduplicated, ["DOMAIN-SUFFIX,amazon.com,GlobalMedia"])

    def test_unknown_rule_types_emit_warning_and_are_skipped(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, "configs"), exist_ok=True)
            os.makedirs(os.path.join(temp_dir, "rules"), exist_ok=True)
            os.makedirs(os.path.join(temp_dir, "rulesets"), exist_ok=True)

            _write_yaml(
                os.path.join(temp_dir, "configs", "rulesets.yaml"),
                {
                    "prefix": [{"name": "Prefix", "group": "Proxy", "ruleset": "rulesets/prefix.yaml"}],
                    "suffix": [],
                },
            )
            _write_yaml(
                os.path.join(temp_dir, "rules", "suffix.yaml"),
                {"rules": ["MATCH,Proxy"]},
            )
            _write_yaml(
                os.path.join(temp_dir, "rulesets", "prefix.yaml"),
                {"payload": ["PROCESS-NAME,foo.bar", "DOMAIN-SUFFIX,ok.example.com"]},
            )

            preference = {
                "rules-prefix": [],
                "rules-suffix": [],
                "rulesets": [],
            }

            rule = self._build_rule(temp_dir)
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                generated = rule.getRules(copy.deepcopy(preference))["rules"]

            warning_text = stderr.getvalue()
            self.assertIn("Skipped", warning_text)
            self.assertIn("PROCESS-NAME", warning_text)
            self.assertTrue(any("ok.example.com" in line for line in generated))
            self.assertFalse(any("PROCESS-NAME" in line for line in generated))

    def test_duplicated_ruleset_paths_emit_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, "configs"), exist_ok=True)
            os.makedirs(os.path.join(temp_dir, "rules"), exist_ok=True)
            os.makedirs(os.path.join(temp_dir, "rulesets"), exist_ok=True)

            _write_yaml(
                os.path.join(temp_dir, "configs", "rulesets.yaml"),
                {
                    "prefix": [{"name": "FB-Proxy", "group": "Proxy", "ruleset": "rulesets/fb.yaml"}],
                    "suffix": [{"name": "FB-Static", "group": "Static", "ruleset": "rulesets/fb.yaml"}],
                },
            )
            _write_yaml(
                os.path.join(temp_dir, "rules", "suffix.yaml"),
                {"rules": ["MATCH,Proxy"]},
            )
            _write_yaml(
                os.path.join(temp_dir, "rulesets", "fb.yaml"),
                {"payload": ["DOMAIN-SUFFIX,facebook.com"]},
            )

            preference = {
                "rules-prefix": [],
                "rules-suffix": [],
                "rules-policy-priority": ["Static", "Proxy"],
                "rulesets": [],
            }

            rule = self._build_rule(temp_dir)
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                generated = rule.getRules(copy.deepcopy(preference))["rules"]

            warning_text = stderr.getvalue()
            self.assertIn("duplicated ruleset paths", warning_text)
            self.assertTrue(any(line == "DOMAIN-SUFFIX,facebook.com,Static" for line in generated))

    def test_match_key_normalization_deduplicates_plus_prefix(self):
        rule = Rule()
        rules = [
            "DOMAIN-SUFFIX,+.example.com,Proxy",
            "DOMAIN-SUFFIX,example.com,AI",
        ]

        deduplicated = rule.deduplicateRules(rules)
        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(deduplicated[0], "DOMAIN-SUFFIX,+.example.com,Proxy")


if __name__ == "__main__":
    unittest.main()
