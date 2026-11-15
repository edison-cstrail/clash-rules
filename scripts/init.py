#!/usr/bin/env python3
"""Create private subconverter settings without putting upstream URLs in shell history."""

import argparse
import getpass
import os
from pathlib import Path
import re
import secrets
from urllib.parse import urlencode, urlsplit


ROOT = Path(__file__).resolve().parents[1]


def write_private(path, text):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", default="localhost", help="订阅服务域名，不含 https://")
    parser.add_argument("--rules-config-url", help="自己仓库中外部配置的 Raw HTTPS 地址")
    parser.add_argument("--demo", action="store_true", help="使用虚构节点验证配置，不能用于代理")
    args = parser.parse_args()
    domain = args.domain
    if len(domain) > 253 or not re.fullmatch(
        r"[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)*",
        domain,
    ):
        parser.error("--domain 必须是主机名，例如 sub.example.com，不含协议、路径或端口")
    rules_config = args.rules_config_url or "config/custom/custom.ini"
    if args.rules_config_url:
        parsed = urlsplit(rules_config)
        if parsed.scheme != "https" or not parsed.netloc or any(c.isspace() for c in rules_config):
            parser.error("--rules-config-url 必须是完整的、无空格的 HTTPS URL")

    private = ROOT / "private"
    destinations = [ROOT / ".env", private / "pref.ini", private / "profile.ini"]
    if any(path.exists() for path in destinations):
        parser.error("已有私密配置，未覆盖。请直接编辑 .env 或 private/ 下的文件。")

    if args.demo:
        subscription = "ss://YWVzLTEyOC1nY206ZGVtby1vbmx5@192.0.2.1:8388#Demo"
    else:
        subscription = getpass.getpass("机场订阅 URL（不会显示；多个订阅用 | 分隔）: ").strip()
        if not subscription or any(char in subscription for char in "\r\n\x00"):
            parser.error("请输入非空、单行的订阅 URL")
        for url in subscription.split("|"):
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or any(c.isspace() for c in url):
                parser.error("每个机场订阅都必须是完整的 HTTP/HTTPS URL")

    token = secrets.token_hex(24)
    admin_token = secrets.token_hex(32)
    preference = (ROOT / "config/pref.example.ini").read_text(encoding="utf-8")
    preference = preference.replace("@@ADMIN_TOKEN@@", admin_token)
    profile = (
        "[Profile]\n"
        f"profile_token={token}\n"
        f"url={subscription}\n"
        "target=clash\n"
        f"config={rules_config}\n"
        "emoji=true\n"
        "list=false\n"
        "scv=false\n"
        "fdn=false\n"
        "expand=true\n"
        "sort=false\n"
        "new_name=true\n"
    )
    private.mkdir(mode=0o700, exist_ok=True)
    private.chmod(0o700)
    write_private(private / "pref.ini", preference)
    write_private(private / "profile.ini", profile)
    write_private(ROOT / ".env", f"DOMAIN={domain}\nSUB_TOKEN={token}\n")

    query = urlencode({"name": "private/profile.ini", "token": token})
    print("配置已生成。运行 docker compose up -d 后，本机订阅地址：")
    print(f"http://127.0.0.1:25500/getprofile?{query}")
    if domain != "localhost":
        print("域名解析完成后，运行 docker compose --profile https up -d，远程订阅地址：")
        print(f"https://{domain}/{token}/clash.yaml")
    if args.demo:
        print("当前是演示订阅。正式使用前请编辑 private/profile.ini 的 url=。")


if __name__ == "__main__":
    main()
