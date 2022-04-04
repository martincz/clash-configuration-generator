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
    | preference.default.yaml | 用于参考的标准配置示例
    | preference.merlinclash.yaml | 用于参考的 MerlinClash 配置示例 |

2. 按需修改 preference.yaml 中的默认参数。

3. 在仓库根目录运行以下命令：

    ```bash
    python generate
    ```

4. 导入生成的 configuration.yaml 配置文件到 Clash。