#
# Copyright (C) 2022 Martincz Gao
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
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