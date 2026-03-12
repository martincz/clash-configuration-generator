# Clash Configuration Generator

适用于 Clash 的自定义配置生成脚本

## 前提条件

* 安装 [Git](https://git-scm.com/) 分布式版本控制系统。

* 安装 [Python](https://www.python.org/) 运行环境。

* 安装必要的 Python 软件包：

    ```bash
    pip install deepmerge
    pip install ruamel.yaml
    ```

* 使用以下命令同步仓库到本地：

    ```bash
    git clone --recurse-submodules https://github.com/martincz/clash-configuration-generator.git
    ```

## 简易用法

1. 拷贝配置示例的副本并更名为 preference.yaml。

    | 文件名 | 解释 |
    | :--- | :--- |
    | preference.yaml | 实际生效的配置 |
    | preference.basic.yaml | 用于参考的标准配置示例 |
    | preference.merlinclash.yaml | 用于参考的 MerlinClash 配置示例 |
    | preference.advanced.yaml | 用于参考的进阶配置示例 |

2. 按需修改 preference.yaml 中的默认参数。

3. 在仓库根目录运行以下命令：

    ```bash
    python generate
    ```

4. 导入生成的 config.yaml 配置文件到 Clash。

## 可选参数

    --dns
        生成带有 DNS 服务器相关配置的文件。（Clash 内置了 DNS 服务器，默认未启用）

    --stdout
        将生成结果输出到标准输出，不写入 config.yaml。

    --dry-run
        等价于 --stdout，用于只检查生成结果、不落盘。

    -o, --output <path>
        将生成结果写入指定文件路径，不写入默认的 config.yaml。

## generate 用法示例

```bash
# 默认行为：写入项目根目录 config.yaml
python generate

# 生成包含 DNS 配置的默认 config.yaml
python generate --dns

# 只输出到终端，不改动本地 config.yaml
python generate --stdout

# 输出到指定文件（推荐用于验证）
python generate --output config.preview.yaml

# 组合使用：带 DNS + 输出到指定文件
python generate --dns --output config.preview.yaml
```

## 测试用法

项目已内置基于 `unittest` 的回归测试，覆盖：

* rules-prefix / rules-suffix 的位置语义
* rulesets 排序与去重
* rules-policy-priority 决策
* generate 参数行为（`--stdout` / `--output`）

在项目根目录运行：

```bash
# 运行全部测试
python -m unittest discover -s tests -v

# 只运行规则逻辑测试
python -m unittest tests.test_rule_logic -v

# 只运行 generate 参数测试
python -m unittest tests.test_generate_cli -v

# 只运行 proxy-group 容错测试
python -m unittest tests.test_proxy_group -v
```

## CLI Notes (Updated)

`generate` no longer accepts positional arguments. Use options only:

```bash
python generate [--dns] [--stdout|--dry-run] [-o|--output <path>]
```

Behavior details:

* `--stdout` / `--dry-run`: print result only, do not write `config.yaml`.
* `--output <path>`: write to target file and automatically create parent directories.
* Unknown options or positional args now return an error code (`2`) with usage text.

Rule generation warnings:

* Unknown rule types are skipped and reported to `stderr`.
* Duplicated ruleset paths with different groups are reported to `stderr`, with the effective winner decided by `rules-policy-priority`.
