# MIT License

# Copyright (c) 2022 Martincz Gao

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

from deepmerge import always_merger
from ruamel.yaml import YAML

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

        rules = {'rules': []}

        # 前置偏好规则
        prefix_rules = {'rules': preference.get('prefix-rules')}
        always_merger.merge(rules, prefix_rules)

        # 偏好规则集
        pref_rulesets = preference.get('rulesets')
        always_merger.merge(rules, self.getRulesFromRuleSets(pref_rulesets))

        # 预设规则集
        with open(os.path.join(self.top_dir, 'configs/rulesets.yaml'), 'rb') as fp:
            def_rulesets = self.yaml.load(fp)
            always_merger.merge(rules, self.getRulesFromRuleSets(def_rulesets))

        # 后置偏好规则
        suffix_rules = {'rules': preference.get('suffix-rules')}
        always_merger.merge(rules, suffix_rules)

        # 结尾规则
        with open(os.path.join(self.top_dir, 'rules/suffix.yaml'), 'rb') as fp:
            suffix = self.yaml.load(fp)
            always_merger.merge(rules, suffix)

        del preference['rulesets']
        del preference['prefix-rules']
        del preference['suffix-rules']

        return rules

    def getRulesFromRuleSets(self, rulesets):
        rules = {'rules': []}
        for policy in rulesets:
            group = policy.get('group')
            ruleset = policy.get('ruleset')
            with open(os.path.join(self.top_dir, ruleset), 'rb') as fp:
                rulelines = self.yaml.load(fp)
                for line in rulelines.get('payload'):
                    info = line.split(',')
                    if (info[0] in ALLOWED_RULE_TYPES):
                        if (len(info) == 2):
                            rule = ','.join([info[0], info[1], group])
                        elif (len(info) == 3):
                            rule = ','.join([info[0], info[1], group, info[2]])
                        rules['rules'].append(rule)
        return rules