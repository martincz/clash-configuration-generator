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

from __future__ import print_function
from deepmerge import always_merger
from ruamel.yaml import YAML
from libs.dns import getDns
from libs.proxy_group import getProxyGroups
from libs.rule import Rule

import os
import sys

def getPreference():

    yaml = YAML()
    yaml.allow_unicode = True
    yaml.explicit_start = False
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    try:
        top_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        with open(os.path.join(top_dir, 'preference.yaml'), 'rb') as fp:
            orig_preference = yaml.load(fp)
            if orig_preference is None:
                raise FileNotFoundError
    except FileNotFoundError:
        print('未配置 preference.yaml 文件！')
        sys.exit(1)

    # DNS服务器
    dns = getDns()
    preference = always_merger.merge(dns, orig_preference)

    # 代理组策略
    proxy_groups = getProxyGroups(preference)
    preference.update(proxy_groups)

    # 分流规则
    rule = Rule()
    rules = rule.getRules(preference)
    always_merger.merge(preference, rules)

    # 检查重复项
    # print([item for item, count in collections.Counter(preference['rules']).items() if count > 1])
    return preference