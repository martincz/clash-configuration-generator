# Clash Configuration Generator

用于生成 Clash 配置文件的脚本工具。

## 环境准备

1. 安装 [Git](https://git-scm.com/)。
2. 安装 [Python](https://www.python.org/) 3.9 或更新版本。
3. 安装依赖：

```bash
pip install -r requirements.txt
```

4. 拉取仓库（含子模块）：

```bash
git clone --recurse-submodules https://github.com/martincz/clash-configuration-generator.git
```

## 快速开始

1. 准备 `preference.yaml`（可从示例文件复制）：

| 文件名 | 说明 |
| :--- | :--- |
| `preference.yaml` | 实际生效配置 |
| `preference.basic.yaml` | 基础示例 |
| `preference.merlinclash.yaml` | MerlinClash 示例 |
| `preference.advanced.yaml` | 进阶示例 |

2. 按需修改 `preference.yaml`。
3. 两个平台分别准备项目环境（虚拟环境不能跨 Windows/Linux 共用）：

```bash
# Linux
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

```powershell
# Windows PowerShell
python -m venv .venv-windows
.venv-windows\Scripts\python.exe -m pip install -r requirements.txt
```

4. 在仓库根目录执行。命令会优先使用当前平台的项目环境，避免误用全局旧依赖：

```bash
python generate
```

5. 将生成的 `config.yaml` 导入 Clash 客户端。

Magic Catling2 的 DNS 在应用内单独配置，默认生成结果不包含 `dns` 段属于正常用法。只有需要包含 DNS 的完整文件时才使用 `--dns`。sniffer 是否开启由实际使用需要决定。

## generate 参数与示例

命令格式：

```bash
python generate [--dns] [--stdout|--dry-run] [-o|--output <path>]
```

参数说明：

| 参数 | 说明 |
| :--- | :--- |
| `--dns` | 生成结果中包含 DNS 配置（默认不输出 DNS 段） |
| `--stdout` | 只输出到标准输出，不写入 `config.yaml` |
| `--dry-run` | 与 `--stdout` 等价 |
| `-o, --output <path>` | 输出到指定文件，不写入默认 `config.yaml` |

行为说明：

1. 默认行为是写入项目根目录 `config.yaml`。
2. 使用 `--stdout` 或 `--dry-run` 时，不会修改本地 `config.yaml`。
3. 使用 `--output` 时，会自动创建目标文件的父目录。
4. 不支持位置参数；未知选项或位置参数会返回错误码 `2` 并输出用法。

示例：

```bash
# 默认生成到 config.yaml
python generate

# 生成包含 DNS 配置的 config.yaml
python generate --dns

# 只预览，不落盘
python generate --stdout

# 生成到指定文件（推荐用于验证）
python generate --output config.preview.yaml

# 带 DNS 并输出到指定文件
python generate --dns --output config.preview.yaml
```

## 规则生成提示

1. 规则按 `rules-prefix` -> `rulesets-prefix` -> 普通 `rulesets` -> `rules-suffix` -> `rules/suffix.yaml` 的顺序合并。
2. `rulesets-prefix` 按配置中的规则集顺序保留分块，每块内部按精度排序；普通 `rulesets` 仍整体按精度排序，并结合 `rules-policy-priority` 决定同精度冲突优先级。
3. 相同 `TYPE+PATTERN` 的重复规则会在生成阶段去重，保留排序更靠前的一条。
4. 未知规则类型会被跳过，并输出到 `stderr`。
5. 偏好配置显式引用某个 ruleset 路径时，会替换默认清单中同路径的引用，避免 Facebook 等规则同时被默认组和自定义组接管。
6. 自定义清单内部仍存在同路径不同组时会告警：前置规则集按块顺序生效，普通规则集按 `rules-policy-priority` 决定同精度冲突。

### 业务前置规则集

需要固定出口的业务可以放进 `rulesets-prefix`，确保综合媒体库中的精确域名不会抢走业务流量。例：

```yaml
rulesets-prefix:
  - name: "Lan"
    group: "DIRECT"
    ruleset: "rules/blackmatrix7/Lan/Lan_No_Resolve.yaml"
  - name: "AI"
    group: "AI"
    ruleset: "rules/martincz/AI/AI.yaml"
  - name: "ChatGPTVoice"
    group: "AI"
    ruleset: "rules/martincz/AI/ChatGPTVoice.yaml"
  - name: "Payment"
    group: "Secure"
    ruleset: "rules/martincz/Payment/Payment.yaml"
  - name: "Media"
    group: "GlobalMedia"
    ruleset: "rules/martincz/Media/Media.yaml"
  - name: "MediaIP"
    group: "GlobalMedia"
    ruleset: "rules/martincz/Media/MediaIP.yaml"

rulesets:
  - name: "SharedServices"
    group: "Proxy"
    ruleset: "rules/martincz/SharedServices/SharedServices.yaml"
```

`AI` 代理组需要在 `preference.yaml` 中定义为 `select`，候选直接填写验证过的节点名。该规则集包括 OpenAI、Claude、Cursor、GitHub/Microsoft Copilot、Gemini 和 NotebookLM 等专属域名；共享平台域名由 `SharedServices` 分开处理，更具体的业务租户域名仍可覆盖它们。

`Media` 规则集补充 Bilibili、iQIYI、WeTV 国际版的专属入口，覆盖综合国内媒体清单中的冲突条目；国内站点和通用 API 仍保留直连。

`Payment` 单列 Stripe Checkout、付款链接、客户账单、支付 API、3D Secure 和 Link 入口；`Secure` 组需要由偏好配置定义为同城节点的手动选择组。通用 `js.stripe.com` SDK 仍按共享服务处理。PayPal 保留普通规则排序，使其中的通用关键词不会抢占其他站点更精确的域名规则。

`ChatGPTVoice` 是 OpenAI 官方语音地址的版本化快照，包含来源时间和 SHA-256。显式执行以下命令可刷新；下载或验证失败时保留原文件，普通 `generate` 不访问网络：

```bash
python update_voice_rules.py
```

`MediaIP` 恢复经 ARIN/RIPE 登记核实、且已在综合媒体库中的 Netflix、Hulu、YouTube 专属网段；每个网段记录了核验来源。共享云网段和未核实的地址仍保留通用代理策略。

### 综合规则集的 IP 出口

规则集可以用 `ip-group` 为 `IP-CIDR` / `IP-CIDR6` / `IP-ASN` 指定不同出口，显式规则补丁仍优先。默认 `GlobalMedia` 已采用这一设置：

```yaml
- name: "GlobalMedia"
  group: "GlobalMedia"
  ip-group: "Proxy"
  ruleset: "rules/blackmatrix7/GlobalMedia/GlobalMedia_Classical_No_Resolve.yaml"
```

媒体域名及前置 `MediaIP` 中的专属网段跟随 `GlobalMedia`；综合库中的其余 IP 使用通用 `Proxy`。Nintendo 的 `35.192.0.0/12` 属于共享 Google Cloud 网络，可在该规则集配置 `ip-group: "Proxy"`，保留其域名走 `Game`。

`IP-ASN` 按目标 IP 所属的自治系统编号匹配，例如 `IP-ASN,32934,Static,no-resolve`。Mihomo v1.19.28 支持该类型；生成器保留上游 Facebook、Telegram 的 ASN 规则，并在普通规则集中将其排在域名和明确的 CIDR 之后。`no-resolve` 选项保持不变，仍参与规则补丁、策略优先级和去重。

ASN 匹配依赖内核数据目录中的 `ASN.mmdb`；文件缺失时 Mihomo 会按 `geox-url.asn` 的配置或内核默认地址尝试下载。生成命令本身不下载数据库。路由器转发流量通常没有客户端进程信息，因此上游 `PROCESS-NAME` 规则仍会跳过并告警。

参考：[Mihomo 路由规则](https://wiki.metacubex.one/config/rules/)。

## 代理组选择

默认只保留 `Proxy`、`Apple`、`GlobalMedia`、`Speedtest`、`Hijacking` 五组。其他分组由偏好配置显式添加，同名组仍可覆盖默认组。

- AI、支付等需要稳定出口的业务使用 `select`，直接选择具体节点；支付备用节点应限定在可接受的同一城市。
- TikTok、Apple TV 和其他海外视频可统一使用 `GlobalMedia`，按实际播放/下载吞吐手选节点；国内媒体继续直连。
- 普通访问的地区组可以使用 `url-test`，例如显式设置 `tolerance: 50`、`interval: 300`、`lazy: true`，测试地址使用 HTTPS。
- `url-test` 比较延迟，`fallback` 按顺序选择可用节点，均不自动测量持续吞吐。媒体组不要仅凭 204 延迟认定最快节点。
- `select` 如果选择了一个自动组，其最终出口仍会随下层自动组切换。需要固定出口时应选择具体节点。
- `Speedtest` 用于手动切换出口，在不同测试站比较网速；各测试站保持跟随这个独立组，不绑定媒体组。

实际策略保存在 `preference.yaml` 和规则文件中；调整后执行 `python generate` 即可重建 `config.yaml`。`preference.yaml`、生成结果、`.venv/` 和 `.venv-windows/` 不纳入 Git。

### 常规入口下的业务分流

AI、支付、测速通过现有透明代理或普通代理入口使用规则分流，偏好配置保留实际使用的 SmartDNS SOCKS 监听。专属业务域名分别跟随各自的手动组；共享验证码、统计和 CDN 平台使用通用代理。共享域名无法仅凭域名规则判断发起业务，因此主站固定出口不等于所有第三方依赖都固定出口。

`SharedServices` 收录通用 AWS、CloudFront、Akamai 等共享域名。在偏好配置中对 `amazonaws.com`、`amazonaws.co.uk`、`cloudfront.net`、`akamaized.net` 使用 `Proxy` 覆盖补丁，避免综合媒体库将整个共享平台归入媒体。明确的媒体专属域名和前置业务例外仍优先。

### 普通分流下的跨站测速

默认测速规则包含上游清单及本地 `SpeedtestSupplement`，后者补充 nPerf、SpeedOf.Me、TestMy.net。可以将补充清单放入 `rulesets-prefix`，与上游测速清单一起优先处理，测试客户端继续使用现有入口。

FAST.com 使用 Netflix 服务器测量吞吐，其页面命中 `Speedtest`，Netflix CDN 数据可能命中 `GlobalMedia`。进行 FAST 测试时，将两个组选成同一个被测节点，测试后恢复媒体组。切换节点后重新开始测试，已建立的连接不会随组选择迁移。

其他测速站也可能使用清单未覆盖的动态服务器域名或共享 CDN。通过 Mihomo 连接记录确认实际测速连接命中的规则，再补充专属测试服务器域名；站点首页归组不能证明全部测速连接都使用同一出口。

参考：[FAST.com 官方说明](https://fast.com/en)。

### ruleset-rule-patches（本地规则补丁）

当上游 ruleset 中存在不符合你分流策略的条目时，可以在 `preference.yaml` 中使用 `ruleset-rule-patches` 做本地修正，无需修改 `rules/blackmatrix7` 目录文件。

支持能力：

1. `drop`：删除指定规则（按 `TYPE+PATTERN` 匹配）
2. `override`：改写指定规则的分组（按 `TYPE+PATTERN` 匹配）

作用范围：

1. `ruleset`：按 ruleset 路径匹配
2. `name`：按 ruleset 名称匹配（即 `rulesets` 里的 `name`）
3. 未设置 `ruleset`/`name` 时，视为全局补丁

示例（把 Copilot 中的 `challenges.cloudflare.com` 删除，并把 OpenAI 中同条目改到 `Proxy`）：

```yaml
ruleset-rule-patches:
  - ruleset: "rules/blackmatrix7/Copilot/Copilot_No_Resolve.yaml"
    drop:
      - "DOMAIN-SUFFIX,challenges.cloudflare.com"

  - name: "OpenAI"
    override:
      - match: "DOMAIN-SUFFIX,challenges.cloudflare.com"
        group: "Proxy"
```

## Windows 与 Linux 的文件格式

仓库文本统一使用 UTF-8（无 BOM）和 LF 换行：

- `.gitattributes` 固定 Git 索引和检出文件的文本换行规则，不依赖各机器的 `core.autocrlf` 设置；二进制文件保持原样。
- `.editorconfig` 约束支持它的编辑器，保存文件时使用 UTF-8、LF 和末尾换行。
- `generate` 以 UTF-8 文本读取所有 YAML，在解析前统一输入换行，兼容 UTF-8 BOM；再将配置统一渲染成无 BOM 的 UTF-8 / LF 字节。默认文件、`--output`、`--stdout` 和 `--dry-run` 使用同一份内容，YAML 字符串中的转义数据不变。
- 两个平台使用同一份输入和 `requirements.txt` 中固定的依赖版本，可得到一致的生成结果。

跨平台保存文件推荐直接指定输出路径，避开外部 Shell 重定向可能引入的重新编码：

```bash
python generate --output config.yaml
```

GitHub Actions 在 Windows 和 Linux 上运行相同测试，包括输出字节、CRLF 输入，以及 `core.autocrlf=true/input/false` 下的检出检查。

## 测试

项目内置 `unittest` 回归测试，覆盖规则排序/去重、CLI 参数行为、proxy-group 容错等场景。
业务策略测试还覆盖 AI/媒体/支付分类、共享云网段、前置规则集、默认规则集覆盖和设备端口逻辑规则去重。
测试前请激活对应平台的项目环境，或把下面的 `python` 替换为 `.venv/bin/python`（Linux）或 `.venv-windows\Scripts\python.exe`（Windows）。

```bash
# 运行全部测试
python -m unittest discover -s tests -v

# 仅运行规则逻辑测试
python -m unittest tests.test_rule_logic -v

# 仅运行 generate 参数测试
python -m unittest tests.test_generate_cli -v

# 仅运行 proxy-group 容错测试
python -m unittest tests.test_proxy_group -v

# 仅运行业务策略测试
python -m unittest discover -s tests -p test_rule_policy.py -v
```
