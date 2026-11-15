# 可选：自建订阅转换服务

本文适用于希望自己运行 subconverter 和 HTTPS 入口的情况。使用已有订阅转换服务时，请按 [README](../README.md) 直接引用 GitHub 配置。本文中的命令均在项目根目录执行。

使用自己的 subconverter，把机场节点和自己维护的分流规则合成为完整的 Clash 配置。Clash Verge 等客户端导入同一个订阅地址；以后修改服务端规则，客户端更新订阅即可生效。

## 首次使用

本仓库的远程规则配置：[config/github.ini](https://raw.githubusercontent.com/edison-cstrail/clash-rules/main/config/github.ini)。它供转换服务读取；Clash Verge 使用服务生成的完整订阅地址。

在已安装 Python 3、Docker 和 Docker Compose v2 的 Linux 服务器上执行：

```bash
git clone git@github.com:edison-cstrail/clash-rules.git
cd clash-rules
python3 scripts/init.py --domain sub.example.com \
  --rules-config-url https://raw.githubusercontent.com/edison-cstrail/clash-rules/main/config/github.ini
docker compose --profile https up -d
```

将 `sub.example.com` 换成自己的域名，事先解析到服务器 IP，并开放 TCP 80、443。初始化时粘贴机场原始订阅地址，再将程序打印的 `https://你的域名/随机令牌/clash.yaml` 添加到 Clash Verge 的远程订阅。

以后在 GitHub 网页编辑 `rules/direct.list`、`rules/proxy.list` 或 `rules/reject.list` 并提交，缓存过期后在客户端更新订阅即可。例如，让某个域名及子域名走代理，在 `rules/proxy.list` 添加 `DOMAIN-SUFFIX,example.com`。

```text
机场订阅 + config/custom.ini + rules/*.list
                    ↓
               subconverter
                    ↓
         Caddy HTTPS 订阅入口（可选）
                    ↓
          Clash Verge / Clash 客户端
```

## 原配置的问题

`config=` 是 subconverter 的「外部配置」，包含策略组、规则集引用等。`Clash/Rule-Provider/Apple.yaml` 这样的文件是某一分类的规则集，不能直接代替完整外部配置。你提供的 `lhie1/Rules/master/Clash/Rule-Provider/Apple.yaml` 地址在本次检查时还返回了 HTTP 404。

原仓库页面目前显示已被 GitHub 停用。本项目使用 `config/custom.ini` 定义完整配置，默认引用目前可读取的 `dler-io/Rules` 的 Apple、Proxy 和 Domestic 分类规则，并允许个人规则优先覆盖。这里不假定两个仓库之间的维护关系。无需修改 subconverter 源码。

## 推荐：自己的仓库管理个人规则，直接订阅社区规则

自己的 GitHub 仓库保存个人规则、策略组和上游 URL；社区规则直接引用原作者的分支地址。**无需 fork、拷贝或定时合并上游规则**。服务器收到订阅更新请求时会拉取所引用的文件，遵循缓存时间，再生成完整 Clash 订阅。

```text
社区仓库的分类规则 ─────────┐
                           ├─ subconverter ─ Clash Verge
自己的仓库：个人规则、策略组 ┘
```

本仓库已包含面向 `edison-cstrail/clash-rules` 的远程配置。修改 `config/custom.ini` 后，用以下命令重新生成：

```bash
python3 scripts/github_config.py --repo edison-cstrail/clash-rules --branch main
```

它生成 `config/github.ini`，自动将个人规则和基础模板路径转换成本仓库的 Raw URL，上游 URL 保持原样。将生成的配置和模板改动一起提交、推送。复用到其他仓库时，按实际仓库名和分支修改参数。

随后按下面的部署步骤初始化，额外指定这份远程配置：

```bash
python3 scripts/init.py --domain sub.example.com \
  --rules-config-url https://raw.githubusercontent.com/edison-cstrail/clash-rules/main/config/github.ini
```

以后直接在 GitHub 网页编辑 `rules/direct.list`、`rules/proxy.list`、`rules/reject.list` 并提交即可，服务器无需 `git pull`。修改策略组或上游来源时，编辑 `config/custom.ini`、重新生成 `config/github.ini`，一起提交。规则文件内容变化无需重新生成。

远程模式下：自己的总配置缓存约 5 分钟，个人规则和社区规则缓存约 1 小时，GitHub/CDN 也可能有缓存。缓存过期后，下次客户端更新订阅会获取更新；**这不是后台定时同步，也不会主动推送**。可以在 `private/pref.ini` 调短缓存时间、按下文重新创建后端，并在客户端设置自动更新订阅。本地模式则只引用本地个人规则，需要另行将仓库变更同步到服务器。

上述 Raw URL 方式适用于公开仓库。个人规则可能透露自己的域名偏好；机场订阅和令牌只保存在服务器的 `.env`、`private/`，不提交到规则仓库。私有仓库建议通过服务器的 Git/SSH 拉取后使用本地模式，当前脚本没有实现私有 GitHub Raw 鉴权。

可选规则源：

| 来源 | 适合的内容 | 本方案的格式 |
| --- | --- | --- |
| `dler-io/Rules` | Apple、代理、国内、流媒体等分类 | `Clash/Provider/*.yaml` 使用 `clash-classic:` |
| `blackmatrix7/ios_rule_script` | 更细的应用、服务分类 | 检查具体文件，完整规则的 YAML 使用 `clash-classic:` |
| `Loyalsoldier/clash-rules` | 通用直连、代理、拦截等集合 | `release/direct.txt` 等域名集合使用 `clash-domain:` |

一个分类选一个来源即可；组合多个来源时由 `ruleset` 顺序决定冲突结果。`.mrs` 是 Mihomo 原生格式，不能直接放入本方案的 subconverter 规则源。

## 部署

服务器需要 Docker、Docker Compose v2 和 Python 3。先把本项目放到服务器，进入项目目录。

1. 初始化配置，交互输入机场订阅；输入不会显示，也不会进入 shell 历史。

   ```bash
   python3 scripts/init.py --domain sub.example.com
   ```

   把 `sub.example.com` 换成自己的域名。多个机场订阅用 `|` 分隔。没有域名时可以省略 `--domain`，先验证本机服务。只想试运行可以加 `--demo`，演示节点不能用于代理。

2. 启动转换后端并检查。

   ```bash
   docker compose up -d
   curl -f http://127.0.0.1:25500/version
   ```

   初始化脚本会打印本机订阅 URL，可在服务器本机下载验证。后端仅绑定服务器的 `127.0.0.1:25500`；其他电脑上的 `127.0.0.1` 不会指向这台服务器。

3. 提供远程 HTTPS 订阅。

   将域名的 A 记录指向服务器 IPv4 地址；如有 AAAA 记录，也要确保对应 IPv6 可访问。开放 TCP 80、443，保证没有其他服务占用这两个端口，然后运行：

   ```bash
   docker compose --profile https up -d
   ```

   Caddy 会申请证书。把初始化时打印的 `https://你的域名/随机令牌/clash.yaml` 导入 Clash Verge 的远程订阅，并使用规则模式。该链接能读取你的节点配置，应作为私密订阅保存。

已经使用 Nginx/Caddy 管理域名时，可以只启动后端，在现有反向代理中实现与本项目 `Caddyfile` 相同的固定路径转发：只转发到指定的 `/getprofile?name=private/profile.ini&token=...`，并替换用户传入的查询参数。

## 自定义分流

修改这些文件，一行一条规则，**不写最后的策略名称**：

| 文件 | 对应行为 |
| --- | --- |
| `rules/direct.list` | 强制直连 |
| `rules/proxy.list` | 强制使用 Proxy 策略组 |
| `rules/reject.list` | 阻止连接 |
| `config/custom.ini` | 规则顺序、社区规则来源、策略组 |
| `config/clash-base.yaml` | 输出配置的基础选项 |

例如，在 `rules/direct.list` 添加：

```text
DOMAIN-SUFFIX,example.cn
DOMAIN,intranet.example.com
IP-CIDR,203.0.113.0/24,no-resolve
```

在 `rules/proxy.list` 添加：

```text
DOMAIN-SUFFIX,example.com
DOMAIN,api.example.net
```

`DOMAIN` 只匹配具体主机名；`DOMAIN-SUFFIX` 匹配该域名及其所有子域名。不包含协议、端口或 URL 路径。

默认匹配顺序是：自定义拦截 → 自定义直连 → 自定义代理 → 局域网 → Apple → 社区代理规则 → 国内域名 → 国内 IP → Final 兜底。**第一条命中的规则生效**；重复域名出现在多个文件时也遵循这个顺序。兜底规则必须放最后。

Apple 策略组默认直连，可以在客户端把整个组切到 Proxy。只想让某个 Apple 域名走代理时，将该域名加入 `rules/proxy.list` 即可覆盖 Apple 通用规则。

本地模式下，修改服务器上的 `.list` 或 `custom.ini` 后，客户端手动更新一次订阅即可，无需重启服务器。GitHub 远程模式下，提交变更后还需等待上述缓存过期。服务端不会主动把配置推送给客户端；可以在客户端设置定时更新。原始机场订阅可能缓存 60 秒。

新增策略组时，同时添加组定义和规则引用，例如：

```ini
custom_proxy_group=Work`select`[]Proxy`[]DIRECT
ruleset=Work,rules/custom/work.list
```

创建 `rules/work.list`，并将这条 `ruleset` 放在需要覆盖的规则之前，尤其是 `GEOIP` 和 `FINAL` 之前。

引用 Clash YAML 规则集时，按实际内容选择格式。`payload` 内包含 `DOMAIN-SUFFIX,...` 等完整规则的使用：

```ini
ruleset=Apple,clash-classic:https://你的规则地址/apple.yaml
```

只有域名的集合使用 `clash-domain:`，只有 IP 段的使用 `clash-ipcidr:`。普通 `.list`（例如本项目的规则）直接写路径或 URL。配置与规则文件都在自己控制下，可以随时替换社区规则来源。

## 维护与适用范围

- 机场订阅保存在 `private/profile.ini` 的 `url=`，直接编辑即可；多个订阅用 `|` 分隔。`.env`、`private/` 已被 Git 忽略，初始化生成的文件权限为 `600`。
- `private/pref.ini` 是后端启动配置，修改后运行 `docker compose up -d --force-recreate subconverter`。修改域名或访问令牌时，要同步 `.env` 和 `private/profile.ini` 中的 `profile_token`，再运行 `docker compose --profile https up -d --force-recreate`。
- 查看状态：`docker compose --profile https ps`。查看日志：`docker compose --profile https logs --tail=50`。停止：`docker compose --profile https down`，证书卷会保留。
- `compose.yaml` 固定了本次验证的官方 subconverter 镜像摘要。需要升级时，在 `.env` 增加 `SUBCONVERTER_IMAGE=你确认过的镜像版本或摘要`，再拉取并重新创建服务。
- 保留了你原来的多数转换选项，但使用 `scv=false`，即正常验证代理节点的 TLS 证书。确有自签名节点时可以按实际情况修改 `private/profile.ini`，它与分流规则无关。
- 此方案只生成订阅，实际代理流量在客户端与机场节点之间传输。服务器需要能够访问机场订阅和引用的 GitHub 原始规则地址；远程规则请求失败时应检查输出，subconverter 可能跳过未能读取的规则集。
- 节点协议能否转换取决于 subconverter，Clash Verge 支持某协议并不代表转换器也支持。如果出现节点丢失，尤其是较新的协议，应优先评估使用机场提供的 Mihomo YAML，通过原生 `proxy-providers` 加自定义规则配置，避免转换造成信息丢失。本项目未增加新的节点协议支持。
- 这是文件配置方案，没有网页规则编辑器。无需网页编辑器就能集中维护多台客户端的规则；后续可在此基础上添加管理界面。

参考：[subconverter 外部配置](https://github.com/tindy2013/subconverter/blob/master/README-cn.md#外部配置)、[官方 Docker 部署](https://github.com/tindy2013/subconverter/blob/master/README-docker.md)、[dler-io 分类规则](https://github.com/dler-io/Rules/tree/main/Clash/Provider)、[blackmatrix7 规则](https://github.com/blackmatrix7/ios_rule_script)、[Loyalsoldier 规则](https://github.com/Loyalsoldier/clash-rules)、[Caddy 自动 HTTPS](https://caddyserver.com/docs/automatic-https)、[Mihomo 代理集合](https://wiki.metacubex.one/config/proxy-providers/)。
