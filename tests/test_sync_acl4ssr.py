from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

from scripts import sync_acl4ssr as sync


UPSTREAM = """[custom]
; Community comment
ruleset=DIRECT,https://example.com/direct.list
ruleset=🚀 节点选择,https://example.com/proxy.list
ruleset=Final,[]FINAL
custom_proxy_group=🚀 节点选择`select`[]Auto`[]DIRECT`.*
custom_proxy_group=Auto`url-test`.*`https://example.com/check`300
custom_proxy_group=Final`select`[]🚀 节点选择`[]DIRECT
enable_rule_generator=true
overwrite_original_rules=true
"""


class RenderTests(unittest.TestCase):
    def test_personal_rules_precede_complete_upstream(self):
        entries = sync.parse_config(sync.render_config(UPSTREAM))
        rules = [value for key, value in entries if key == "ruleset"]
        self.assertEqual(rules[:4], list(sync.PERSONAL_RULESETS))
        self.assertEqual(entries[4:], sync.parse_config(UPSTREAM))
        self.assertEqual(rules[-1], "Final,[]FINAL")

    def test_new_upstream_category_and_group_are_retained(self):
        upstream = UPSTREAM.replace(
            "ruleset=Final,[]FINAL",
            "ruleset=New,https://example.com/new.list\nruleset=Final,[]FINAL",
        ) + "custom_proxy_group=New`select`[]🚀 节点选择\n"
        rendered = sync.render_config(upstream)
        self.assertIn("ruleset=New,https://example.com/new.list", rendered)
        self.assertIn("custom_proxy_group=New`select`[]🚀 节点选择", rendered)
        self.assertEqual(sync.parse_config(rendered)[4:], sync.parse_config(upstream))

    def test_runtime_templates_are_omitted(self):
        upstream = UPSTREAM + (
            "clash_rule_base=https://example.com/base.yaml\n"
            ";clash_rule_base=https://example.com/commented.yaml\n"
        )
        self.assertNotIn("clash_rule_base", sync.render_config(upstream))

    def test_utf8_bom_is_supported(self):
        self.assertEqual(sync.render_config("\ufeff" + UPSTREAM), sync.render_config(UPSTREAM))

    def test_invalid_upstream_is_rejected(self):
        cases = {
            "empty response": "",
            "HTML error page": "<html>Error</html>",
            "unknown section": UPSTREAM + "[other]\n",
            "runtime option": UPSTREAM + "mixed-port=7890\n",
            "missing personal proxy target": UPSTREAM.replace("🚀 节点选择", "Renamed"),
            "dangling group reference": UPSTREAM.replace("[]Auto", "[]Missing"),
            "dangling policy": UPSTREAM.replace("ruleset=DIRECT,", "ruleset=Missing,"),
            "duplicate group": UPSTREAM + "custom_proxy_group=Auto`select`.*\n",
            "disabled generator": UPSTREAM.replace("enable_rule_generator=true", "enable_rule_generator=false"),
            "duplicate flag": UPSTREAM + "enable_rule_generator=true\n",
            "no fallback": UPSTREAM.replace("ruleset=Final,[]FINAL\n", ""),
            "early fallback": UPSTREAM + "ruleset=DIRECT,https://example.com/late.list\n",
        }
        for name, upstream in cases.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                sync.render_config(upstream)


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.output = self.root / "github.ini"
        self.output.write_text("last valid config\n")

    def test_updates_only_output_and_is_idempotent(self):
        personal = self.root / "proxy.list"
        personal.write_text("DOMAIN-SUFFIX,personal.example\n")
        with patch.object(sync, "download_upstream", return_value=UPSTREAM):
            self.assertTrue(sync.sync_config(self.output))
            self.assertEqual(self.output.read_text(), sync.render_config(UPSTREAM))
            modified = self.output.stat().st_mtime_ns
            self.assertFalse(sync.sync_config(self.output))
            self.assertEqual(self.output.stat().st_mtime_ns, modified)
        self.assertEqual(personal.read_text(), "DOMAIN-SUFFIX,personal.example\n")

    def test_network_failure_preserves_previous_config(self):
        with patch.object(sync, "download_upstream", side_effect=URLError("offline")):
            with self.assertRaises(URLError):
                sync.sync_config(self.output)
        self.assertEqual(self.output.read_text(), "last valid config\n")

    def test_validation_failure_preserves_previous_config(self):
        with patch.object(sync, "download_upstream", return_value="<html>Error</html>"):
            with self.assertRaises(ValueError):
                sync.sync_config(self.output)
        self.assertEqual(self.output.read_text(), "last valid config\n")

    def test_failed_replace_preserves_config_and_removes_temporary_file(self):
        with patch.object(sync, "download_upstream", return_value=UPSTREAM):
            with patch.object(sync.os, "replace", side_effect=OSError("write failed")):
                with self.assertRaises(OSError):
                    sync.sync_config(self.output)
        self.assertEqual(self.output.read_text(), "last valid config\n")
        self.assertEqual(list(self.root.iterdir()), [self.output])


class DownloadTests(unittest.TestCase):
    def test_transient_network_error_is_retried(self):
        with patch.object(sync, "urlopen", side_effect=[URLError("offline"), unittest.mock.DEFAULT]) as fetch:
            fetch.return_value.__enter__.return_value.read.return_value = UPSTREAM.encode()
            with patch.object(sync.time, "sleep"):
                self.assertEqual(sync.download_upstream(), UPSTREAM)
            self.assertEqual(fetch.call_count, 2)

    def test_oversized_response_is_rejected(self):
        with patch.object(sync, "urlopen") as fetch:
            fetch.return_value.__enter__.return_value.read.return_value = b"x" * (sync.MAX_CONFIG_BYTES + 1)
            with self.assertRaises(ValueError):
                sync.download_upstream()


if __name__ == "__main__":
    unittest.main()
