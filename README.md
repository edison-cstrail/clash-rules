# GitHub 个人 Clash 分流规则

在 GitHub 维护个人规则，叠加完整 ACL4SSR 社区分流，通过现有的 subconverter 服务生成 Clash Verge 订阅。社区配置由 GitHub Actions 自动同步，个人规则优先。

## 第一次使用

1. 在你现在使用的订阅转换页面中，将“远程配置 / 自定义配置”地址填写为：

   ```text
   https://raw.githubusercontent.com/edison-cstrail/clash-rules/main/config/github.ini
   ```

2. 机场原始订阅继续填在原来的订阅地址输入框，转换目标选择 Clash，生成转换后的订阅链接。

3. 将转换后的订阅链接添加到 Clash Verge 的远程订阅，下载并启用，使用规则模式。

如果你直接修改已有的转换 URL，将其中 `config=` 参数的值替换为下面的 URL 编码，其他参数保留：

```text
config=https%3A%2F%2Fraw.githubusercontent.com%2Fedison-cstrail%2Fclash-rules%2Fmain%2Fconfig%2Fgithub.ini
```

## 以后怎样修改个人规则

登录 GitHub，打开下表对应的文件，编辑后提交；随后在 Clash Verge 更新订阅。

| 规则文件 | 行为 |
| --- | --- |
| [rules/direct.list](https://github.com/edison-cstrail/clash-rules/edit/main/rules/direct.list) | 强制直连 |
| [rules/proxy.list](https://github.com/edison-cstrail/clash-rules/edit/main/rules/proxy.list) | 强制走 🚀 节点选择 策略组 |
| [rules/reject.list](https://github.com/edison-cstrail/clash-rules/edit/main/rules/reject.list) | 阻止连接 |

例如，让 `example.com` 及其所有子域名走代理，在 `rules/proxy.list` 添加：

```text
DOMAIN-SUFFIX,example.com
```

只让一个具体主机名直连，在 `rules/direct.list` 添加：

```text
DOMAIN,intranet.example.com
```

每行写一条规则，以 `#` 开头的行是注释。`DOMAIN` 匹配具体主机名，`DOMAIN-SUFFIX` 匹配域名及其子域名。规则不填协议、URL 路径或末尾的策略名称。

更新可能受到你所用转换服务和 GitHub 的缓存影响；缓存时间由实际服务决定。可以在 Clash Verge 设置定时更新订阅。

## 配置与社区规则

社区来源是 [ACL4SSR 完整在线版](https://github.com/ACL4SSR/ACL4SSR/blob/master/Clash/config/ACL4SSR_Online_Full.ini)。保留上游全部分类、策略组和匹配顺序，包括广告、应用净化、AI、微软、苹果、电报、视频、游戏、地区分组等，新增分类和组定义也随上游同步。

`config/github.ini` 在完整社区配置之前加入本仓库的个人拦截、直连、代理和局域网规则。第一条命中的规则生效，社区兜底规则保持在最后。各分类的规则文件直接引用上游 URL，由转换服务在处理订阅更新时获取，遵循其缓存策略。

本配置沿用 `expand=true` 的完整订阅方式，规则在转换时写入输出配置，客户端通过更新订阅获取变更。

## 自动同步

[Sync ACL4SSR 工作流](https://github.com/edison-cstrail/clash-rules/actions/workflows/sync.yml) 每天北京时间 **10:17** 在 GitHub 上运行，也支持在该页面点击 **Run workflow** 手动触发。同步脚本、工作流、测试或个人规则文件变更时也会运行。无需部署服务或配置额外的访问令牌。

同步任务获取完整社区配置，检查策略组引用和兜底顺序，再前置个人规则；只有生成内容变化时才提交 `config/github.ini`。任务不会修改个人规则文件。下载、校验或推送失败时，现有线上配置会保留，可在 Actions 页面查看原因后重新运行。

`config/github.ini` 是自动生成的文件，日常只需编辑 `rules/` 中的个人规则。需要调整同步来源或个人代理目标时，修改 `scripts/sync_acl4ssr.py`，提交后由工作流重新生成。同步不会添加本地端口、控制接口或基础模板设置。

首次运行后检查 Actions 是否成功；若仓库策略禁止工作流写入，需要允许其提交配置。GitHub 定时任务可能延迟，公开仓库长期无活动时可能自动暂停，可在 Actions 页面重新启用并手动运行。

维护脚本可在本地运行，使用 Python 3 标准库：

```bash
python3 -B -m unittest discover -s tests -v
python3 -B scripts/sync_acl4ssr.py
```

参考：[subconverter 外部配置说明](https://github.com/tindy2013/subconverter/blob/master/README-cn.md#外部配置)、[社区规则来源](https://github.com/ACL4SSR/ACL4SSR)、[GitHub 定时任务说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。
