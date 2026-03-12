# Clash Configuration Generator

用于生成 Clash 配置文件的脚本工具。

## 环境准备

1. 安装 [Git](https://git-scm.com/)。
2. 安装 [Python](https://www.python.org/)。
3. 安装依赖：

```bash
pip install deepmerge
pip install ruamel.yaml
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
3. 在仓库根目录执行：

```bash
python generate
```

4. 将生成的 `config.yaml` 导入 Clash 客户端。

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

1. 规则按 `rules-prefix` -> `rulesets` -> `rules-suffix` -> `rules/suffix.yaml` 的顺序合并。
2. `rulesets` 部分会按规则精度排序，并结合 `rules-policy-priority` 决定同精度冲突优先级。
3. 相同 `TYPE+PATTERN` 的重复规则会在生成阶段去重，保留排序更靠前的一条。
4. 未知规则类型会被跳过，并输出到 `stderr`。
5. 同一路径 ruleset 被配置到不同分组时，会输出告警，最终生效分组由 `rules-policy-priority` 决定。

## 测试

项目内置 `unittest` 回归测试，覆盖规则排序/去重、CLI 参数行为、proxy-group 容错等场景。

```bash
# 运行全部测试
python -m unittest discover -s tests -v

# 仅运行规则逻辑测试
python -m unittest tests.test_rule_logic -v

# 仅运行 generate 参数测试
python -m unittest tests.test_generate_cli -v

# 仅运行 proxy-group 容错测试
python -m unittest tests.test_proxy_group -v
```
