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

import numpy as np
import sys
from ruamel.yaml import YAML

def main():

    yaml = YAML()
    yaml.allow_unicode = True
    yaml.explicit_start = False
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    with open('configs/common.yaml') as fp:
        cfg_common = yaml.load(fp)

    with open('configs/proxy.yaml') as fp:
        cfg_proxy = yaml.load(fp)

    with open('configs/dns.yaml') as fp:
        cfg_dns = yaml.load(fp)

    with open('configs/custom.yaml') as fp:
        cfg_custom = yaml.load(fp)

    # 合并所有规则
    with open('rules/common.yaml') as fp:
        rules_common = yaml.load(fp)

    with open('rules/custom.yaml') as fp:
        rules_custom = yaml.load(fp)

    with open('rules/suffix.yaml') as fp:
        rules_suffix = yaml.load(fp)

    rules_final = rules_common.copy()
    rules_final['rules'] = rules_common['rules'] + rules_custom['rules'] + rules_suffix['rules']

    # 整合最终配置
    cfg_final = cfg_common.copy()
    cfg_arrays = [cfg_proxy, rules_final, cfg_dns, cfg_custom]
    for cfg in cfg_arrays:
        cfg_final.update(cfg)
    with open('configuration.yaml', 'w') as fp:
        yaml.dump(cfg_final, fp)


if __name__ == '__main__':
    main()