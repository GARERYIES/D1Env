# 原始来源索引

查阅日期：2026-10-06。以下均为作者/厂商/产品官方来源。`main` 是查阅入口，不是已锁定发布版本；本包不声称取得了这些仓库的当前 commit SHA。

| ID | 来源和精确入口 | 本次阅读范围 |
|---|---|---|
| S01 | `https://github.com/ioai-tech/ioenv_cli` | 仓库结构、README、许可证标识 |
| S02 | `https://raw.githubusercontent.com/ioai-tech/ioenv_cli/main/bin/ioenv` | 主 CLI 脚本：环境解析、镜像拉取、容器/卷、终端、SSH |
| S03 | `https://raw.githubusercontent.com/ioai-tech/ioenv_cli/main/ioenv.sh` | PATH 和 shell 补全入口 |
| S04 | `https://raw.githubusercontent.com/ioai-tech/ioenv_cli/main/env.d/isaaclab.env` | IsaacLab 镜像引用、GPU/X11 和工作目录配置 |
| S05 | `https://raw.githubusercontent.com/ioai-tech/ioenv_cli/main/env.d/mujocosim.env` | MuJoCo 仿真环境配置 |
| S06 | `https://raw.githubusercontent.com/ioai-tech/ioenv_cli/main/env.d/onboard.env` | 机载环境与实时调度权限配置 |
| S07 | `https://raw.githubusercontent.com/ioai-tech/ioenv_cli/main/conf.d/mirrors.env` | 镜像站配置 |
| S08 | `https://io-ai.tech/iocreed/en/docs/locomotion_00/` | 官方训练、仿真、真机部署教程；不代表实际运行验证 |
| S09 | `https://github.com/ioai-tech/humanoid_controller` | 控制器包职责、机器人支持表 |
| S10 | `https://raw.githubusercontent.com/ioai-tech/humanoid_controller/main/launch/mujoco.launch.py` | 仿真 launch、配置选择、controller spawner |
| S11 | `https://raw.githubusercontent.com/ioai-tech/humanoid_controller/main/launch/real.launch.py` | 真机 launch、配置选择、控制器初始激活状态 |
| S12 | `https://github.com/ioai-tech/robot_hardware_interface` | 硬件插件、平台 SDK/消息依赖；未审计所有 C++ 实现 |
| S13 | `https://github.com/AgibotTech/agibot_D1_Edu-Ultra` | SDK 入口、基本平台要求 |
| S14 | `https://raw.githubusercontent.com/AgibotTech/agibot_D1_Edu-Ultra/main/docs/deploy.md` | 型号/版本、网络、机器人侧配置和部署步骤 |
| S15 | `https://raw.githubusercontent.com/AgibotTech/agibot_D1_Edu-Ultra/main/include/zsl-1/highlevel.h` | 点足高层类公开签名；未见 .so 内部行为 |
| S16 | `https://raw.githubusercontent.com/AgibotTech/agibot_D1_Edu-Ultra/main/include/zsl-1w/highlevel.h` | 轮足高层类公开签名；未见 .so 内部行为 |
| S17 | `https://raw.githubusercontent.com/AgibotTech/agibot_D1_Edu-Ultra/main/demo/zsl-1w/cpp/CMakeLists.txt` | x86_64/aarch64 分支与链接命名 |
| S18 | `https://github.com/AgibotTech/Agibot_D1_MaxPro` | 高/低层依赖区别、网络、固件注意事项和目录结构 |
| S19 | `https://docs.docker.com/engine/security/` | daemon 权限边界、Web 服务控制 Docker 的风险 |
| S20 | `https://docs.docker.com/engine/network/drivers/host/` | host 网络行为与平台条件 |
| S21 | `https://raw.githubusercontent.com/SteveMacenski/slam_toolbox/humble/README.md` | 后续 SLAM 候选的官方说明，未完成本项目集成 |
| S22 | `https://developers.openai.com/codex/guides/agents-md/` | Codex 项目级 AGENTS.md；查阅时重定向至官方 ChatGPT Learn 文档 |
| S23 | `https://raw.githubusercontent.com/AgibotTech/agibot_D1_Edu-Ultra/main/LICENSE` | SDK 仓库许可证文本，仍需逐项清点依赖/二进制来源 |

## M0 必须补齐的证据

在可联网开发机上取得源代码的完整 commit SHA、实际文件路径及哈希；枚举所需 SDK 二进制架构、动态依赖和明确版本；检查相应标签/发行包是否存在。对下载的可信厂商二进制先做静态元数据检查，不能把运行未知二进制当作只读调研。

要输出 `docs/research/UPSTREAM_LOCK.json`，每个记录至少有 repository、commit_sha、observed_at、paths、file_hashes、license_path、retrieval_status。无法取得的字段为 null，并写具体阻塞原因；任何 null 不能进入生产安装解析结果。

本次未取得 IOENV 预制镜像的构建来源全链、SBOM 和可复现构建证明；后续须自行提供 D1Env 的 Dockerfile、依赖锁与 CI 证据，不把 CLI 可读等同于镜像可重建。
