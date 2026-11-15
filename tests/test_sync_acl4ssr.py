from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

from scripts import sync_acl4ssr as sync


REVISION = "a" * 40


UPSTREAM = """[custom]
; Community comment
ruleset=DIRECT,https://example.com/direct.list
ruleset=🚀 节点选择,https://example.com/proxy.list
ruleset=Final,[]FINAL
custom_proxy_group=🚀 节点选择`select`[]Auto`[]DIRECT`.*
custom_proxy_group=💬 Ai平台`select`[]🚀 节点选择`[]DIRECT
custom_proxy_group=Auto`url-test`.*`https://example.com/check`300
custom_proxy_group=Final`select`[]🚀 节点选择`[]DIRECT
enable_rule_generator=true
overwrite_original_rules=true
"""


class RenderTests(unittest.TestCase):
    def test_personal_rules_precede_complete_upstream(self):
        entries = sync.parse_config(sync.render_config(UPSTREAM, REVISION))
        rules = [value for key, value in entries if key == "ruleset"]
        self.assertEqual(rules[:5], list(sync.personal_rulesets(REVISION)))
        self.assertIn(f"/{REVISION}/rules/proxy.list", rules[2])
        self.assertEqual(entries[5:], sync.parse_config(UPSTREAM))
        self.assertEqual(rules[-1], "Final,[]FINAL")

    def test_new_upstream_category_and_group_are_retained(self):
        upstream = UPSTREAM.replace(
            "ruleset=Final,[]FINAL",
            "ruleset=New,https://example.com/new.list\nruleset=Final,[]FINAL",
        ) + "custom_proxy_group=New`select`[]🚀 节点选择\n"
        rendered = sync.render_config(upstream, REVISION)
        self.assertIn("ruleset=New,https://example.com/new.list", rendered)
        self.assertIn("custom_proxy_group=New`select`[]🚀 节点选择", rendered)
        self.assertEqual(sync.parse_config(rendered)[5:], sync.parse_config(upstream))

    def test_apple_ai_precedes_broad_community_apple_rules(self):
        apple = "🍎 苹果服务,https://example.com/apple.list"
        upstream = UPSTREAM.replace(
            "ruleset=Final,[]FINAL", f"ruleset={apple}\nruleset=Final,[]FINAL",
        ) + "custom_proxy_group=🍎 苹果服务`select`[]DIRECT\n"
        entries = sync.parse_config(sync.render_config(upstream, REVISION))
        rules = [value for key, value in entries if key == "ruleset"]
        apple_ai = (
            f"💬 Ai平台,{sync.PERSONAL_BASE}/{REVISION}/rules/apple-ai.list"
        )
        self.assertLess(rules.index(apple_ai), rules.index(apple))
        self.assertEqual(rules[-1], "Final,[]FINAL")

    def test_runtime_templates_are_omitted(self):
        upstream = UPSTREAM + (
            "clash_rule_base=https://example.com/base.yaml\n"
            ";clash_rule_base=https://example.com/commented.yaml\n"
        )
        self.assertNotIn("clash_rule_base", sync.render_config(upstream, REVISION))

    def test_utf8_bom_is_supported(self):
        self.assertEqual(sync.render_config("\ufeff" + UPSTREAM, REVISION), sync.render_config(UPSTREAM, REVISION))

    def test_invalid_upstream_is_rejected(self):
        cases = {
            "empty response": "",
            "HTML error page": "<html>Error</html>",
            "unknown section": UPSTREAM + "[other]\n",
            "runtime option": UPSTREAM + "mixed-port=7890\n",
            "missing personal proxy target": UPSTREAM.replace("🚀 节点选择", "Renamed"),
            "missing AI target": UPSTREAM.replace("💬 Ai平台", "Renamed AI"),
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
                sync.render_config(upstream, REVISION)


class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Rule sync tests")
        self.git("config", "user.email", "tests@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        (self.root / "rules").mkdir()
        self.rules = self.root / "rules/proxy.list"
        self.rules.write_text("DOMAIN,first.test\n")
        self.first_revision = self.commit("Add personal rules")

    def git(self, *arguments):
        return subprocess.run(
            ["git", *arguments], cwd=self.root, check=True,
            capture_output=True, text=True,
        ).stdout.strip()

    def commit(self, message):
        self.git("add", ".")
        self.git("commit", "-qm", message)
        return self.git("rev-parse", "HEAD")

    def test_generated_config_and_community_changes_do_not_change_rules_version(self):
        original = sync.render_config(UPSTREAM, sync.personal_rules_revision(self.root))
        (self.root / "github.ini").write_text(original)
        self.commit("Generate config")
        revision = sync.personal_rules_revision(self.root)
        self.assertEqual(revision, self.first_revision)
        self.assertEqual(sync.render_config(UPSTREAM, revision), original)
        changed_community = UPSTREAM.replace("direct.list", "new-direct.list")
        updated = sync.render_config(changed_community, revision)
        rulesets = [value for key, value in sync.parse_config(updated) if key == "ruleset"]
        self.assertEqual(rulesets[:5], list(sync.personal_rulesets(self.first_revision)))

    def test_personal_rule_edit_changes_reference_urls(self):
        self.rules.write_text("DOMAIN,first.test\nDOMAIN,test.test\n")
        revision = self.commit("Update personal rules")
        self.assertNotEqual(revision, self.first_revision)
        self.assertEqual(sync.personal_rules_revision(self.root), revision)
        self.assertIn(
            f"/{revision}/rules/proxy.list",
            sync.render_config(UPSTREAM, revision),
        )

    def test_shallow_history_is_rejected(self):
        clone = self.root / "shallow"
        self.git("clone", "-q", "--depth=1", self.root.as_uri(), str(clone))
        with self.assertRaisesRegex(ValueError, "fetch-depth: 0"):
            sync.personal_rules_revision(clone)

    def test_missing_rules_history_is_rejected(self):
        # A separate repository with no rules commits must not fall back to HEAD.
        empty = self.root / "empty"
        empty.mkdir()
        subprocess.run(["git", "init", "-q", str(empty)], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(empty), "-c", "user.name=Rule sync tests",
             "-c", "user.email=tests@example.invalid", "-c", "commit.gpgsign=false",
             "commit", "--allow-empty", "-qm", "Initial commit"],
            check=True, capture_output=True,
        )
        with self.assertRaisesRegex(ValueError, "No committed personal rules"):
            sync.personal_rules_revision(empty)


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.output = self.root / "github.ini"
        self.output.write_text("last valid config\n")
        revision = patch.object(sync, "personal_rules_revision", return_value=REVISION)
        revision.start()
        self.addCleanup(revision.stop)

    def test_updates_only_output_and_is_idempotent(self):
        personal = self.root / "proxy.list"
        personal.write_text("DOMAIN-SUFFIX,personal.example\n")
        with patch.object(sync, "download_upstream", return_value=UPSTREAM):
            self.assertTrue(sync.sync_config(self.output))
            self.assertEqual(self.output.read_text(), sync.render_config(UPSTREAM, REVISION))
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
