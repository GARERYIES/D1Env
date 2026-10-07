# Start Here — D1Env 0.3.0

当前交付是 **Mac Apple Silicon 软件候选**。已有 Docker 环境下的运行准备、ROS 软件部署与检查已经实际验证；全新电脑安装、Linux 发行和 D1 真机仍待验收。

## 使用完整包

1. 打开 [0.3.0 Release](https://github.com/GARERYIES/D1Env/releases/tag/v0.3.0-software-candidate)，下载 `D1Env-0.3.0-macos-aarch64.tar.gz`、`SHA256SUMS.txt` 和 `START-HERE.md`。
2. 核对归档 SHA-256，解压后双击 `D1Env.command`。需要已安装 Google Chrome；不需要手装 Node/Python、编译 ROS 或编辑 YAML。
3. 默认 MOCK，可直接体验五步向导、模拟故障和报告导出。
4. 选择“真实软件测试”，在第三步点击“准备运行环境”。已有受信 Docker 会复用；缺少时提供官方下载安装引导，许可和系统权限由你在原生窗口确认。
5. 环境准备完成后预览并启动 ROS 软件测试，查看当前通信结果；使用停止、重试或报告导出处理本作业。

归档 SHA-256：`e2866d49ff3e795ede21f6350a8edca97987e37fc26320fb542fb8859daff6ad`。

软件检查通过不代表 D1 就绪。所有真实机器人配置禁用，遥测保持 `UNKNOWN` / `null`，运动未启用。发行包尚未完成签名/公证和全新 Mac 下载隔离验收；出现系统阻止时保留提示，不通过关闭安全检查解决。

## 源码开发

开发工具、构建顺序与命令见 [README / Development](README.md#development)。GitHub 自动源码压缩不包含运行时、前端产物或 ROS 工件。

完整证据见 [0.3.0 交付](reports/M3-setup-summary.md)、[独立审查](reports/M3-setup-review.md) 和 [发布记录](reports/GITHUB_UPDATE_0.3.0.md)。Linux 成品目标按 [原始设计](docs/superpowers/specs/2026-10-06-d1env-design.md) 的 Ubuntu 22.04 x86_64 验收；后续真机适配另按准确型号与厂商版本实施。
