# GitHub 个人 Clash 分流规则

在 GitHub 维护个人规则，通过现有的 subconverter 订阅转换服务生成 Clash Verge 订阅。个人规则优先于社区规则。

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
| [rules/proxy.list](https://github.com/edison-cstrail/clash-rules/edit/main/rules/proxy.list) | 强制走 Proxy 策略组 |
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

`config/github.ini` 同时引用本仓库的个人规则和 `dler-io/Rules` 的 Apple、Proxy、Domestic 分类规则。转换服务处理订阅更新请求时读取这些 URL，遵循其缓存策略。社区规则直接跟随上游分支，个人规则由你自己维护。

个人规则排在社区规则之前，第一条命中的规则生效。默认顺序为：个人拦截 → 个人直连 → 个人代理 → 局域网 → Apple → 社区代理 → 国内域名 → 国内 IP → Final 兜底。

本配置沿用 `expand=true` 的完整订阅方式，规则在转换时写入输出配置，客户端通过更新订阅获取变更。

修改策略组、规则顺序或社区规则来源时，直接编辑 [config/github.ini](https://github.com/edison-cstrail/clash-rules/edit/main/config/github.ini) 并提交。

参考：[subconverter 外部配置说明](https://github.com/tindy2013/subconverter/blob/master/README-cn.md#外部配置)、[社区规则来源](https://github.com/dler-io/Rules/tree/main/Clash/Provider)。
