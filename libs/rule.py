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

from collections import Counter, defaultdict
from ruamel.yaml import YAML

import ipaddress
import os
import sys

ALLOWED_RULE_TYPES = ['DOMAIN', 'DOMAIN-KEYWORD', 'DOMAIN-SUFFIX', 'IP-CIDR', 'IP-CIDR6']


class Rule(object):

    def __init__(self):
        self.yaml_safe = YAML(typ='safe')
        self.top_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        self.yaml_file_cache = {}
        self.unknown_rule_type_counter = Counter()
        self.unknown_rule_type_examples = {}

    def getRules(self, preference):
        self.resetUnknownRuleTypeWarnings()

        default_rulesets = self.loadYamlFile('configs/rulesets.yaml')

        policy_priorities = self.buildPolicyPriority(preference.get('rules-policy-priority'))

        prefix_rules = self.ensureRuleList(preference.get('rules-prefix'))
        suffix_rules = self.ensureRuleList(preference.get('rules-suffix'))

        selected_rulesets = []
        selected_rulesets.extend(self.ensureRulesets(default_rulesets.get('prefix')))
        selected_rulesets.extend(self.ensureRulesets(preference.get('rulesets')))
        selected_rulesets.extend(self.ensureRulesets(default_rulesets.get('suffix')))

        self.emitDuplicatedRulesetWarnings(selected_rulesets, policy_priorities)
        rulesets_rules = self.getRulesFromRuleSets(selected_rulesets).get('rules')

        # Rulesets are updated from upstream frequently. Sort all ruleset-derived
        # rules together by specificity to reduce cross-ruleset shadowing.
        optimized_rulesets = self.optimizeRulesOrder(rulesets_rules, policy_priorities)

        suffix = self.loadYamlFile('rules/suffix.yaml')
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

        self.emitUnknownRuleTypeWarnings()
        return rules

    def loadYamlFile(self, relative_path):
        absolute_path = os.path.join(self.top_dir, relative_path)
        if absolute_path in self.yaml_file_cache:
            return self.yaml_file_cache[absolute_path]

        with open(absolute_path, 'rb') as fp:
            data = self.yaml_safe.load(fp) or {}

        self.yaml_file_cache[absolute_path] = data
        return data

    def resetUnknownRuleTypeWarnings(self):
        self.unknown_rule_type_counter = Counter()
        self.unknown_rule_type_examples = {}

    def trackUnknownRuleType(self, rule_type, ruleset, raw_line):
        normalized_type = str(rule_type).strip().upper() or '<EMPTY>'
        self.unknown_rule_type_counter[normalized_type] += 1
        if normalized_type not in self.unknown_rule_type_examples:
            example_line = str(raw_line).strip()
            if len(example_line) > 120:
                example_line = example_line[:117] + '...'
            self.unknown_rule_type_examples[normalized_type] = (ruleset, example_line)

    def emitUnknownRuleTypeWarnings(self):
        if len(self.unknown_rule_type_counter) == 0:
            return

        total = sum(self.unknown_rule_type_counter.values())
        print(
            '[WARN] Skipped %d rule lines with unknown rule types.' % total,
            file=sys.stderr
        )
        for rule_type, count in self.unknown_rule_type_counter.most_common():
            ruleset, example = self.unknown_rule_type_examples.get(rule_type, ('<unknown>', ''))
            print(
                '[WARN]   %s: %d (ruleset=%s, example=%s)' % (rule_type, count, ruleset, example),
                file=sys.stderr
            )

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

    def ensureRulesets(self, rulesets):
        if rulesets is None:
            return []
        return [item for item in rulesets if isinstance(item, dict)]

    def emitDuplicatedRulesetWarnings(self, rulesets, policy_priorities):
        by_ruleset = defaultdict(list)

        for index, policy in enumerate(self.ensureRulesets(rulesets)):
            ruleset = str(policy.get('ruleset') or '').strip()
            if ruleset == '':
                continue

            by_ruleset[ruleset].append({
                'index': index,
                'name': str(policy.get('name') or ruleset).strip(),
                'group': str(policy.get('group') or '').strip(),
            })

        conflict_entries = []
        for ruleset, entries in by_ruleset.items():
            groups = {item.get('group') for item in entries}
            if len(entries) < 2 or len(groups) <= 1:
                continue

            ordered = sorted(
                entries,
                key=lambda item: (policy_priorities.get(item.get('group'), 10_000), item.get('index'))
            )
            conflict_entries.append((ruleset, ordered))

        if len(conflict_entries) == 0:
            return

        print(
            '[WARN] Found %d duplicated ruleset paths with different groups.' % len(conflict_entries),
            file=sys.stderr
        )
        for ruleset, ordered in conflict_entries:
            winner = ordered[0]
            winner_rank = policy_priorities.get(winner.get('group'), 'NA')
            candidates = ', '.join([
                '%s(group=%s,priority=%s)' % (
                    item.get('name'),
                    item.get('group'),
                    policy_priorities.get(item.get('group'), 'NA')
                )
                for item in ordered
            ])
            print(
                '[WARN]   %s => winner=%s(group=%s,priority=%s); candidates=%s' % (
                    ruleset,
                    winner.get('name'),
                    winner.get('group'),
                    winner_rank,
                    candidates
                ),
                file=sys.stderr
            )

    def getRulesFromRuleSets(self, rulesets):
        rules = {'rules': []}
        if rulesets is None:
            return rules

        for policy in self.ensureRulesets(rulesets):
            group = str(policy.get('group') or '')
            ruleset = policy.get('ruleset')
            if ruleset is None:
                continue
            rulelines = self.loadYamlFile(ruleset)
            payload = rulelines.get('payload') or []

            for line in payload:
                if not isinstance(line, str):
                    continue

                info = [part.strip() for part in line.split(',')]
                if len(info) == 0:
                    continue

                rule_type = info[0].upper()
                if rule_type not in ALLOWED_RULE_TYPES:
                    self.trackUnknownRuleType(rule_type, ruleset, line)
                    continue

                if len(info) < 2:
                    continue

                if len(info) == 2:
                    rule = ','.join([rule_type, info[1], group])
                else:
                    rule = ','.join([rule_type, info[1], group] + info[2:])

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
