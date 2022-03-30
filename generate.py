#!/usr/bin/env python
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

import collections
import os
import sys
from deepmerge import always_merger
from ruamel.yaml import YAML

def main():

    yaml = YAML()
    yaml.allow_unicode = True
    yaml.explicit_start = False
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    # 读取所有配置
    with open('configs/common.yaml') as fp:
        cfg_common = yaml.load(fp)

    try:
        with open('configs/custom.yaml') as fp:
            cfg_custom = yaml.load(fp)
            if cfg_custom is None:
                raise FileNotFoundError
    except FileNotFoundError:
        print('未配置 configs/custom.yaml 文件！')
        sys.exit(1)

    # 读取所有规则
    rule_merged = {}
    for curDir, dirs, files in os.walk('rules/parts'):
        for file in files:
            if file.endswith('.yaml'):
                with open(os.path.join(curDir, file)) as fp:
                    always_merger.merge(rule_merged, yaml.load(fp))
    with open('rules/common.yaml') as fp:
        rule_common = yaml.load(fp)
    try:
        with open('rules/custom.yaml') as fp:
            rule_custom = yaml.load(fp)
    except FileNotFoundError:
        rule_custom = None
    with open('rules/suffix.yaml') as fp:
        rule_suffix = yaml.load(fp)

    # 合并所有规则
    rule_final = {}
    rule_array = [rule_common, rule_merged, rule_custom, rule_suffix]
    for rule in rule_array:
        always_merger.merge(rule_final, rule)

    # 检查重复项
    # print([item for item, count in collections.Counter(rule_final['rules']).items() if count > 1])

    # 生成最终配置
    cfg_final = cfg_common.copy()
    cfg_array = [cfg_common, rule_final, cfg_custom]
    for cfg in cfg_array:
        cfg_final.update(cfg)

    with open('configuration.yaml', 'w') as fp:
        yaml.dump(cfg_final, fp)


if __name__ == '__main__':
    main()