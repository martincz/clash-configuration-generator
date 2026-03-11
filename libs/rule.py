# MIT License
#
# Copyright (c) 2022 Martincz Gao
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

from ruamel.yaml import YAML

import ipaddress
import os

ALLOWED_RULE_TYPES = ['DOMAIN', 'DOMAIN-KEYWORD', 'DOMAIN-SUFFIX', 'IP-CIDR', 'IP-CIDR6']


class Rule(object):

    def __init__(self):
        self.yaml = YAML()
        self.yaml.allow_unicode = True
        self.yaml.explicit_start = False
        self.yaml.preserve_quotes = True
        self.yaml.indent(mapping=2, sequence=4, offset=2)
        self.top_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

    def getRules(self, preference):

        with open(os.path.join(self.top_dir, 'configs/rulesets.yaml'), 'rb') as fp:
            default_rulesets = self.yaml.load(fp) or {}

        policy_priorities = self.buildPolicyPriority(preference.get('rules-policy-priority'))

        prefix_rules = self.ensureRuleList(preference.get('rules-prefix'))
        suffix_rules = self.ensureRuleList(preference.get('rules-suffix'))

        rulesets_rules = []
        rulesets_rules.extend(self.getRulesFromRuleSets(default_rulesets.get('prefix')).get('rules'))
        rulesets_rules.extend(self.getRulesFromRuleSets(preference.get('rulesets')).get('rules'))
        rulesets_rules.extend(self.getRulesFromRuleSets(default_rulesets.get('suffix')).get('rules'))

        # Rulesets are updated from upstream frequently. Sort all ruleset-derived
        # rules together by specificity to reduce cross-ruleset shadowing.
        optimized_rulesets = self.optimizeRulesOrder(rulesets_rules, policy_priorities)

        with open(os.path.join(self.top_dir, 'rules/suffix.yaml'), 'rb') as fp:
            suffix = self.yaml.load(fp) or {}
            final_suffix_rules = self.ensureRuleList(suffix.get('rules'))

        merged_rules = []
        merged_rules.extend(prefix_rules)
        merged_rules.extend(optimized_rulesets)
        merged_rules.extend(suffix_rules)
        merged_rules.extend(final_suffix_rules)

        rules = {'rules': self.deduplicateRules(merged_rules)}

        for key in ['rulesets', 'rules-prefix', 'rules-suffix', 'rules-policy-priority']:
            if key in preference:
                del preference[key]

        return rules

    def buildPolicyPriority(self, priority_config):
        policy_priorities = {}

        if isinstance(priority_config, list):
            for index, name in enumerate(priority_config):
                if name is None:
                    continue
                policy_priorities[str(name).strip()] = index
            return policy_priorities

        if isinstance(priority_config, dict):
            for name, priority in priority_config.items():
                if name is None:
                    continue
                try:
                    policy_priorities[str(name).strip()] = int(priority)
                except (TypeError, ValueError):
                    continue

        return policy_priorities

    def getRulesFromRuleSets(self, rulesets):
        rules = {'rules': []}
        if rulesets is None:
            return rules

        for policy in rulesets:
            group = policy.get('group')
            ruleset = policy.get('ruleset')
            with open(os.path.join(self.top_dir, ruleset), 'rb') as fp:
                rulelines = self.yaml.load(fp) or {}
                payload = rulelines.get('payload') or []

                for line in payload:
                    if not isinstance(line, str):
                        continue

                    info = [part.strip() for part in line.split(',')]
                    if info[0] not in ALLOWED_RULE_TYPES:
                        continue

                    if len(info) == 2:
                        rule = ','.join([info[0], info[1], group])
                    else:
                        rule = ','.join([info[0], info[1], group] + info[2:])

                    rules['rules'].append(rule)

        return rules

    def ensureRuleList(self, rules):
        if rules is None:
            return []
        return [rule for rule in rules if rule is not None]

    def optimizeRulesOrder(self, rules, policy_priorities=None):
        if policy_priorities is None:
            policy_priorities = {}

        indexed_rules = list(enumerate(self.ensureRuleList(rules)))
        indexed_rules.sort(key=lambda item: self.getRuleSortKey(item[1], item[0], policy_priorities))
        return [item[1] for item in indexed_rules]

    def getRuleSortKey(self, rule, index, policy_priorities):
        if not isinstance(rule, str):
            return (99, 0, 10_000, index)

        info = [item.strip() for item in rule.split(',')]
        if len(info) < 2:
            return (98, 0, 10_000, index)

        rule_type = info[0].upper()
        matcher = self.normalizeRuleMatcher(rule_type, info[1])
        rule_family = self.getRuleFamilyPriority(rule_type)
        rule_specificity = self.getRuleSpecificity(rule_type, matcher)
        rule_policy = info[2] if len(info) >= 3 else ''
        policy_rank = policy_priorities.get(rule_policy, 10_000)

        # Lower family value comes first; higher specificity comes first.
        return (rule_family, -rule_specificity, policy_rank, index)

    def getRuleFamilyPriority(self, rule_type):
        if rule_type == 'DOMAIN':
            return 0
        if rule_type == 'DOMAIN-SUFFIX':
            return 1
        if rule_type == 'DOMAIN-KEYWORD':
            return 2
        if rule_type in ['IP-CIDR', 'IP-CIDR6']:
            return 3
        return 10

    def getRuleSpecificity(self, rule_type, matcher):
        if matcher is None:
            return 0

        if rule_type == 'DOMAIN':
            return len(matcher)

        if rule_type == 'DOMAIN-SUFFIX':
            labels = len([part for part in matcher.split('.') if part])
            return labels * 1000 + len(matcher)

        if rule_type == 'DOMAIN-KEYWORD':
            return len(matcher)

        if rule_type in ['IP-CIDR', 'IP-CIDR6']:
            try:
                network = ipaddress.ip_network(matcher, strict=False)
                return network.prefixlen
            except ValueError:
                return 0

        return 0

    def normalizeRuleMatcher(self, rule_type, matcher):
        value = str(matcher).strip()

        if rule_type in ['DOMAIN', 'DOMAIN-SUFFIX', 'DOMAIN-KEYWORD']:
            value = value.lower()

        if rule_type == 'DOMAIN-SUFFIX':
            if value.startswith('+.'):
                value = value[2:]
            elif value.startswith('.'):
                value = value[1:]

        if rule_type in ['IP-CIDR', 'IP-CIDR6']:
            try:
                value = str(ipaddress.ip_network(value, strict=False))
            except ValueError:
                pass

        return value

    def deduplicateRules(self, rules):
        if rules is None:
            return []

        deduplicated_rules = []
        seen_rule_keys = set()

        for rule in rules:
            key = self.getRuleMatchKey(rule)
            if key in seen_rule_keys:
                continue

            seen_rule_keys.add(key)
            deduplicated_rules.append(rule)

        return deduplicated_rules

    def getRuleMatchKey(self, rule):
        if not isinstance(rule, str):
            return str(rule)

        info = [item.strip() for item in rule.split(',')]
        if len(info) == 0:
            return rule

        rule_type = info[0].upper()

        # Clash rules are usually TYPE,PATTERN,POLICY[,OPTION].
        # Matching behavior is determined by TYPE + PATTERN.
        if len(info) >= 3:
            matcher = self.normalizeRuleMatcher(rule_type, info[1])
            return ','.join([rule_type, matcher])

        # MATCH has no pattern, so only keep the first one.
        if len(info) == 2 and rule_type == 'MATCH':
            return 'MATCH'

        if len(info) == 2:
            matcher = self.normalizeRuleMatcher(rule_type, info[1])
            return ','.join([rule_type, matcher])

        return ','.join([rule_type] + info[1:])
