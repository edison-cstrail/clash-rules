from pathlib import Path
import tempfile
import unittest

from scripts import ini_to_3xui as conv

try:
    import yaml
except ImportError:  # GitHub runners have no PyYAML; the round-trip test is optional.
    yaml = None


SAMPLE = """[custom]
ruleset=REJECT,https://raw.githubusercontent.com/acme/rules/main/rules/reject.list
ruleset=🚀 节点选择,[]GEOIP,CN
ruleset=🐟 漏网之鱼,[]FINAL
custom_proxy_group=🚀 节点选择`select`[]♻️ 自动选择`[]DIRECT
custom_proxy_group=♻️ 自动选择`url-test`.*`http://www.gstatic.com/generate_204`300,,50
custom_proxy_group=🇭🇰 香港节点`url-test`(港|HK)`http://www.gstatic.com/generate_204`300,,50
custom_proxy_group=🎶 网易音乐`select`[]DIRECT`[]🚀 节点选择`(网易|音乐|解锁|Music|NetEase)
custom_proxy_group=🐟 漏网之鱼`select`[]🚀 节点选择`[]DIRECT
enable_rule_generator=true
"""


def convert_text(text: str) -> dict:
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "github.ini"
        source.write_text(text, encoding="utf-8")
        return conv.convert(source)


class ConvertTests(unittest.TestCase):
    def test_document_shape(self):
        document = convert_text(SAMPLE)
        self.assertEqual(list(document), ["proxy-groups", "rule-providers", "rules"])
        self.assertNotIn("proxies", document)
        self.assertNotIn("proxy-providers", document)

    def test_groups_follow_acl4ssr_semantics(self):
        groups = {group["name"]: group for group in convert_text(SAMPLE)["proxy-groups"]}

        self.assertEqual(groups["🚀 节点选择"]["proxies"], ["♻️ 自动选择", "DIRECT"])

        auto = groups["♻️ 自动选择"]
        self.assertTrue(auto["include-all"])
        self.assertEqual(auto["url"], "http://www.gstatic.com/generate_204")
        self.assertEqual(auto["interval"], 300)
        self.assertEqual(auto["tolerance"], 50)

        self.assertEqual(groups["🇭🇰 香港节点"]["filter"], "港|HK")
        self.assertEqual(groups["🎶 网易音乐"]["proxies"], ["DIRECT", "🚀 节点选择"])
        self.assertEqual(groups["🎶 网易音乐"]["filter"], "网易|音乐|解锁|Music|NetEase")

    def test_rules_and_providers(self):
        document = convert_text(SAMPLE)
        self.assertEqual(document["rules"][-1], "MATCH,🐟 漏网之鱼")
        self.assertIn("GEOIP,CN,🚀 节点选择", document["rules"])

        self.assertEqual(list(document["rule-providers"]), ["reject"])
        provider = document["rule-providers"]["reject"]
        self.assertEqual(
            provider["url"],
            "https://cdn.jsdelivr.net/gh/acme/rules@main/rules/reject.list",
        )
        self.assertEqual(provider["behavior"], "classical")
        self.assertEqual(provider["format"], "text")
        self.assertEqual(document["rules"][0], "RULE-SET,reject,REJECT")

    def test_rejects_unknown_group_reference(self):
        with self.assertRaises(ValueError):
            convert_text(SAMPLE.replace("[]DIRECT", "[]不存在的组"))

    def test_rejects_unknown_rule_target(self):
        with self.assertRaises(ValueError):
            convert_text(SAMPLE.replace("🐟 漏网之鱼,[]FINAL", "不存在的组,[]FINAL"))

    def test_jsdelivr_rewrite(self):
        self.assertEqual(
            conv.to_jsdelivr(
                "https://raw.githubusercontent.com/edison-cstrail/clash-rules/abc123/rules/proxy.list"
            ),
            "https://cdn.jsdelivr.net/gh/edison-cstrail/clash-rules@abc123/rules/proxy.list",
        )
        self.assertEqual(conv.to_jsdelivr("https://example.com/a.list"), "https://example.com/a.list")

    @unittest.skipIf(yaml is None, "PyYAML not installed")
    def test_rendered_yaml_round_trips(self):
        text = conv.render(convert_text(SAMPLE))
        document = yaml.safe_load(text)
        self.assertEqual(list(document), ["proxy-groups", "rule-providers", "rules"])
        self.assertEqual(document["rules"][-1], "MATCH,🐟 漏网之鱼")

    def test_rendered_yaml_has_no_node_references(self):
        text = conv.render(convert_text(SAMPLE))
        self.assertIn('  - name: "🚀 节点选择"', text)
        self.assertIn("    include-all: true", text)
        self.assertNotIn("proxies: []", text)


if __name__ == "__main__":
    unittest.main()
