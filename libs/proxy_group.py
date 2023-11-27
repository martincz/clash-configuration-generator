# MIT License

# Copyright (c) 2022-2023 Martincz Gao

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

from ruamel.yaml import YAML
from libs.proxy import getProxies

import os

def getProxyGroups(preference):

    yaml = YAML()
    yaml.allow_unicode = True
    yaml.explicit_start = False
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    # 获取预设代理组
    top_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    with open(os.path.join(top_dir, 'configs/proxy-groups.yaml'), 'rb') as fp:
        cur_groups = yaml.load(fp)
    # 获取偏好代理组
    pref_groups = preference.get('proxy-groups')

    # 获取所有代理节点名
    all_proxies = [proxy['name'] for proxy in getProxies(preference)]

    # 获取偏好代理组名
    pref_group_names = [proxy['name'] for proxy in pref_groups]

    proxy_groups = {'proxy-groups': []}
    # 预设代理组
    for group in cur_groups:
        name = group.get('name')
        if (name in pref_group_names): # 如果预设代理组在偏好代理组中存在，则使用偏好代理组的配置
            continue
        replaceProxies(group, all_proxies)
        proxy_groups['proxy-groups'].append(group)
    # 偏好代理组
    for group in pref_groups:
        replaceProxies(group, all_proxies)
        proxy_groups['proxy-groups'].append(group)

    return proxy_groups

def replaceProxies(group, proxies):
    def_proxies = group.get('proxies')
    if ('.*' in def_proxies):
        index = def_proxies.index('.*')
        def_proxies.remove('.*')
        for proxy in proxies:
            def_proxies.insert(index, proxy)
            index += 1