#!/usr/bin/env python3
"""Sync the complete ACL4SSR config and prepend this repository's personal rules."""

from collections import Counter
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "config/github.ini"
UPSTREAM_URL = (
    "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/"
    "Clash/config/ACL4SSR_Online_Full.ini"
)
PERSONAL_BASE = "https://raw.githubusercontent.com/edison-cstrail/clash-rules"
PROXY_GROUP = "🚀 节点选择"
PERSONAL_FILES = (
    ("REJECT", "reject.list"),
    ("DIRECT", "direct.list"),
    (PROXY_GROUP, "proxy.list"),
    ("DIRECT", "lan.list"),
)
FLAGS = {"enable_rule_generator", "overwrite_original_rules"}
ALLOWED_KEYS = FLAGS | {"ruleset", "custom_proxy_group"}
BUILTINS = {"DIRECT", "REJECT", "REJECT-DROP", "PASS", "COMPATIBLE", "GLOBAL"}
MAX_CONFIG_BYTES = 1024 * 1024


def personal_rules_revision(root=ROOT):
    """Version by the last rules change, never by a generated-config commit."""
    def git(*arguments):
        try:
            return subprocess.run(
                ["git", *arguments], cwd=root, check=True,
                capture_output=True, text=True,
            ).stdout.strip()
        except subprocess.CalledProcessError as error:
            raise ValueError("Cannot read personal rules history from Git") from error

    if git("rev-parse", "--is-shallow-repository") != "false":
        raise ValueError("Full Git history is required; set checkout fetch-depth: 0")
    revision = git("log", "-1", "--format=%H", "--", "rules/")
    if not revision:
        raise ValueError("No committed personal rules found in rules/")
    return revision


def personal_rulesets(revision):
    return tuple(
        f"{policy},{PERSONAL_BASE}/{revision}/rules/{filename}"
        for policy, filename in PERSONAL_FILES
    )


def parse_config(text):
    """Keep repeated INI keys in order; reject unexpected config shapes."""
    entries = []
    in_custom = False
    for number, raw in enumerate(text.lstrip("\ufeff").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith((";", "#")):
            continue
        if line.startswith("["):
            if line != "[custom]" or in_custom:
                raise ValueError(f"Unexpected section on line {number}")
            in_custom = True
            continue
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not in_custom or not separator or not value:
            raise ValueError(f"Invalid config entry on line {number}")
        # Runtime templates belong to the conversion service, not this rules repo.
        if key.endswith("_rule_base"):
            continue
        if key not in ALLOWED_KEYS:
            raise ValueError(f"Unsupported config option: {key}")
        entries.append((key, value))
    if not in_custom:
        raise ValueError("Missing [custom] section")
    return entries


def validate_config(entries):
    groups = [value for key, value in entries if key == "custom_proxy_group"]
    rules = [value for key, value in entries if key == "ruleset"]
    names = [group.split("`", 1)[0] for group in groups]
    if not groups or not rules or any("`" not in group or not name for group, name in zip(groups, names)):
        raise ValueError("Community config must contain rules and proxy groups")
    if len(set(names)) != len(names):
        raise ValueError("Duplicate proxy group names")
    if PROXY_GROUP not in names:
        raise ValueError(f"Personal proxy target is missing: {PROXY_GROUP}")
    for flag in FLAGS:
        values = [value for key, value in entries if key == flag]
        if values != ["true"]:
            raise ValueError(f"Expected exactly one {flag}=true")

    known = set(names) | BUILTINS
    for group in groups:
        for member in group.split("`")[2:]:
            if member.startswith("[]") and member[2:] not in known:
                raise ValueError(f"Unknown proxy group reference: {member[2:]}")
    catchalls = []
    for index, rule in enumerate(rules):
        policy, separator, source = rule.partition(",")
        if not separator or not source or policy not in known:
            raise ValueError(f"Invalid ruleset policy or source: {rule}")
        if source in {"[]FINAL", "[]MATCH"}:
            catchalls.append(index)
    if catchalls != [len(rules) - 1]:
        raise ValueError("Exactly one final catch-all ruleset must come last")


def render_config(upstream, revision):
    upstream = upstream.lstrip("\ufeff")
    validate_config(parse_config(upstream))
    lines = [
        "; 自动生成，请在 rules/ 中维护个人规则。",
        f"; 社区来源：{UPSTREAM_URL}",
        "; 同步完整 ACL4SSR 分类和策略组，个人规则优先。",
    ]
    inserted = False
    for raw in upstream.splitlines():
        line = raw.strip()
        # Also omit commented template examples so they cannot be re-enabled here.
        key = line.lstrip(";# ").partition("=")[0].strip()
        if key.endswith("_rule_base"):
            continue
        if not inserted and line.partition("=")[0].strip() == "ruleset":
            lines.append("; 个人拦截 → 个人直连 → 个人代理 → 局域网 → 完整社区分流")
            lines.extend(f"ruleset={rule}" for rule in personal_rulesets(revision))
            lines.append("")
            inserted = True
        lines.append(raw)
    rendered = "\n".join(lines).rstrip() + "\n"
    validate_config(parse_config(rendered))
    return rendered


def download_upstream():
    request = Request(
        UPSTREAM_URL,
        headers={"User-Agent": "clash-rules-sync", "Cache-Control": "no-cache"},
    )
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                data = response.read(MAX_CONFIG_BYTES + 1)
            if len(data) > MAX_CONFIG_BYTES:
                raise ValueError("Community config exceeds 1 MiB")
            return data.decode("utf-8-sig")
        except (URLError, TimeoutError, OSError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def sync_config(output=OUTPUT):
    revision = personal_rules_revision()
    rendered = render_config(download_upstream(), revision)
    if output.exists() and output.read_text(encoding="utf-8") == rendered:
        return False

    # Validate before writing; an interrupted replacement preserves the old file.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output.parent,
            prefix=".github.ini.", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(rendered)
        temporary.chmod(0o644)
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return True


def main():
    try:
        changed = sync_config()
        counts = Counter(key for key, _ in parse_config(OUTPUT.read_text(encoding="utf-8")))
        print(
            f"{'Updated' if changed else 'Unchanged'}: "
            f"{counts['custom_proxy_group']} groups, {counts['ruleset']} rulesets"
        )
        return 0
    except (OSError, ValueError, UnicodeError) as error:
        print(f"Sync failed; previous config preserved: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
