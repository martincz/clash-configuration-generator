import unittest

import libs.proxy_group as proxy_group_module


class ProxyGroupTests(unittest.TestCase):

    def test_missing_proxy_groups_does_not_raise(self):
        original_get_proxies = proxy_group_module.getProxies
        try:
            proxy_group_module.getProxies = lambda preference: [{"name": "Node-A"}]
            result = proxy_group_module.getProxyGroups({"proxies": [{"name": "Node-A"}]})
        finally:
            proxy_group_module.getProxies = original_get_proxies

        self.assertIn("proxy-groups", result)
        self.assertGreater(len(result["proxy-groups"]), 0)

    def test_non_dict_proxy_groups_are_ignored(self):
        original_get_proxies = proxy_group_module.getProxies
        try:
            proxy_group_module.getProxies = lambda preference: [{"name": "Node-A"}, {"name": "Node-B"}]
            preference = {
                "proxies": [{"name": "Node-A"}, {"name": "Node-B"}],
                "proxy-groups": [
                    "invalid-entry",
                    {"name": "Custom", "type": "select", "proxies": [".*", "DIRECT"]},
                ],
            }
            result = proxy_group_module.getProxyGroups(preference)
        finally:
            proxy_group_module.getProxies = original_get_proxies

        custom = [group for group in result["proxy-groups"] if group.get("name") == "Custom"]
        self.assertEqual(len(custom), 1)
        self.assertIn("Node-A", custom[0].get("proxies"))
        self.assertIn("Node-B", custom[0].get("proxies"))


if __name__ == "__main__":
    unittest.main()
