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

ALLOWED_RULE_TYPES = ['DOMAIN', 'DOMAIN-KEYWORD', 'DOMAIN-SUFFIX', 'IP-CIDR', 'IP-CIDR6']

def getRules():

    yaml = YAML()
    yaml.allow_unicode = True
    yaml.explicit_start = False
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    with open('configs/rulesets.yaml') as fp:
        rulesets = yaml.load(fp)

    rules = {'rules': []}

    # 自定义规则
    try:
        with open('rules/custom.yaml') as fp:
            custom = yaml.load(fp)
            always_merger.merge(rules, custom);
    except FileNotFoundError:
        pass

    # 合并规则集
    for policy in rulesets:
        group = policy.get('group')
        ruleset = policy.get('ruleset')
        with open(ruleset) as fp:
            rulelines = yaml.load(fp)
            for line in rulelines.get('payload'):
                info = line.split(',')
                if (info[0] in ALLOWED_RULE_TYPES):
                    if (len(info) == 2):
                        rule = ','.join([info[0], info[1], group])
                    elif (len(info) == 3):
                        rule = ','.join([info[0], info[1], group, info[2]])
                    rules['rules'].append(rule)

    # 结尾规则
    with open('rules/suffix.yaml') as fp:
        suffix = yaml.load(fp)
        always_merger.merge(rules, suffix);

    return rules