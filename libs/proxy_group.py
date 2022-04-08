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

from ruamel.yaml import YAML
from libs.proxy import getProxies

import os

def getProxyGroups(preference):

    yaml = YAML()
    yaml.allow_unicode = True
    yaml.explicit_start = False
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    ext_proxies = []
    proxies = getProxies(preference)
    for proxy in proxies:
        ext_proxies.append(proxy.get('name'))

    top_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    with open(os.path.join(top_dir, 'configs/proxy-groups.yaml'), 'rb') as fp:
        groups = yaml.load(fp)

    proxy_groups = {'proxy-groups': []}
    ext_proxy_groups = [o['name'] for o in preference.get('proxy-groups')]
    for group in groups:
        name = group.get('name')
        if (name in ext_proxy_groups):
            continue
        def_proxies = group.get('proxies')
        if ('.*' in def_proxies):
            def_proxies.remove('.*')
            def_proxies.extend(ext_proxies)
        proxy_groups['proxy-groups'].append(group)
    return proxy_groups