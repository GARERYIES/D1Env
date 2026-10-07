# D1Env：中文本地部署工具

> **2026-10-07 首次环境准备研发更新：** 新版完整 Mac 候选增加“准备运行环境”。它复用已有本机 Docker；缺失时按固定官方来源下载、核验并衔接安装，Docker 许可和系统授权仍由用户在官方/系统界面完成。完整包内含受信 ROS 数据归档，准备时自动复核和导入；Docker 安装器不随包分发。新机首次安装与授权尚未验收，不能据此称所有 Mac 或 Linux 开箱即用。冻结的 M3 0.2.0 交付保留如下。

## 新版完整 Mac 候选的准备流程

1. 本轮新版完整候选位于 `outputs/D1Env-M3-Setup/`，文件名为 `D1Env-0.3.0-macos-aarch64.tar.gz`。在 Apple Silicon Mac 解压后双击 `D1Env.command`，默认 MOCK、独立 Chrome 窗口；本机需已有 Chrome，无需安装 Node、uv、系统 Python、ROS 或编辑 YAML。
2. 切换“真实软件测试”，在“执行电脑”页点击“准备运行环境”。已有受信 Docker 和镜像会复用；缺失时显示真实下载/校验/安装/等待步骤，不覆盖既有 Docker 或设置。
3. 首次安装可能打开 Docker 官方许可与 macOS 授权界面；用户完成必要确认后，D1Env 继续核对本机 daemon 与固定镜像。不会自动接受许可、收集管理员密码或关闭安全检查。
4. 完整候选自带 ROS 数据归档，用户不再需要手选伴随镜像文件；旧的轻量包仍提供手动导入。准备完成只证明软件前置条件可用，之后仍需预览部署并验证真实 ROS 消息。D1 真机功能依旧禁用、遥测 UNKNOWN/null。

Docker Desktop 来源锁与实际只读下载/签名证据见 [DOCKER_DESKTOP_SOURCES.md](docs/build/DOCKER_DESKTOP_SOURCES.md)。此来源核验与产品首次新机安装、Docker/ROS 生命周期和真机验收分别记录；Docker 由官方按需下载，不捆绑或自动升级已有安装。

研发构建完整便携包时，在已有 `--portable` 构建参数后显式添加：

```sh
--ros-bundle outputs/D1Env-M3/d1env-ros-probe-m3-aarch64.tar
```

构建器按安装后 wheel 内的 `docs/build/ROS_PROBE_OFFLINE.json` 核对固定文件名、架构、来源、镜像 ID、摘要和实际大小，复制到 `_assets/bundles/`。输入或复制期间摘要不符、链接、异常权限和已有目标均拒绝；不将 Docker DMG 当作此输入。未添加此参数的包不含 ROS 数据归档。正式新候选文件、测试与未验证范围以本轮交付报告为准；原 `outputs/D1Env-M3` 不被覆盖。

> **2026-10-07 本地 M3 Mac 候选更新：** 已实现真实 ROS 软件环境的镜像导入、容器部署、通信检查、停止与重试。沿用 [IOENV 蓝图](docs/IOENV_BLUEPRINT.md) 的环境定义、容器生命周期、独立业务启动三层。软件通过不代表 D1 就绪；所有真实机器人配置仍禁用。本轮本地变更尚未推送 GitHub，GitHub 已发布版本仍为 M2。

## 当前 Mac 使用流程

Mac aarch64 候选自带 Python、固定依赖和已构建界面，用户无需安装 Node、uv 或系统 Python，无需编译 ROS 或编辑 YAML。当前真实软件测试需要本机已有可访问的 Docker Desktop/Compose 和 Chrome；原生 Ubuntu x86_64、Intel Mac、Mac 下载隔离/签名/公证尚未验证，不能称 Linux 开箱即用。

1. 取得 `outputs/D1Env-M3/D1Env-0.2.0-macos-aarch64.tar.gz`，解压后双击 `D1Env.command`；也可用包内 `./d1env.sh`。打开的独立 Chrome 窗口默认 MOCK。
2. 选择“真实软件测试”，使用独立的 ROS 软件通信配置；机器人型号均未支持。
3. 在执行电脑页选择伴随文件 `d1env-ros-probe-m3-aarch64.tar` 导入。服务器核对随发行包锁定的摘要、架构和镜像身份；这一步只准备镜像，不证明通信正常。
4. 预览受限容器、内部网络和 Docker 高权限边界，点击部署。实际启动发布者与订阅者，并检查作业 ID、递增消息和新鲜度。
5. 查看当前软件结果，使用“停止测试服务”或“清理本作业遗留服务”。历史任务可恢复；遗留资源或未知盘点会阻止新部署。报告始终区分软件与真机，断连或过期显示 UNKNOWN。

候选文件、真实命令/退出码、截图及未验证范围见 [M3-summary](reports/M3-summary.md)，独立审查见 [M3-review](reports/M3-review.md)。SDK、传感器、建图/导航、运动与硬件停止未实施；本轮没有连接机器人或改网卡/驱动/固件。

## M2 历史交付与原始交接

以下 M2 发布状态和原始设计文字保留为历史基线，不代表当前本地 M3 候选的全部实现范围。

> **2026-10-06 实施更新：Task 0–7 / M0–M2 已实现并验收。** 可运行中文 MOCK 向导、真实本机只读检查、持久化任务和去敏报告。启动方式见本文末尾；本轮结果见 [M2-summary.md](reports/M2-summary.md)。下方“尚无产品实现”和网页调研限制是原始交接基线，保留作历史记录。真实容器、厂商 SDK、真机和运动仍未实施。

## 已发布 M2 的 GitHub 使用与 Linux 就绪状态

**当前不是 Linux 开箱即用的安装包。** 已实测的平台是 macOS aarch64；全新 Linux/Ubuntu 的安装与桌面入口尚未验收。功能范围只有 M0–M2 的 MOCK 软件演示与本机只读诊断，所有真实机器人候选均禁用。

| 取得方式 | 首次运行条件 |
|---|---|
| Git clone / GitHub 自动生成的源码压缩 | 已有 uv、Node 24.x/npm、Chrome/Chromium 与桌面；先按本文构建前端并准备锁定 Python 环境 |
| Releases 中的 `D1Env-M0-M2.zip` | 含已构建前端，不需要用户安装 Node；仍需要 uv、Chrome/Chromium 与桌面，首次 Python/依赖下载需要网络 |
| 无桌面的 Linux 服务器 | CLI 可作为开发入口；当前未交付安全的远程首次登录或无桌面向导入口，不能只打开一个地址即用 |

启动脚本不会安装 uv、浏览器或系统依赖，不会创建真实容器。`--no-browser` 只抑制浏览器启动，不提供新的会话引导凭据，不能当作现成的远程安装方法。Web 仍仅监听 127.0.0.1，不能为了远程访问改为公网监听。

源码启动前先安装上述开发前置条件，再执行本文“M2 当前开发演示启动”中的准备命令。正式的 Ubuntu 安装包、免开发工具启动和全新系统验收属于 M3；真实 SDK/机器人只读属于 M4，均未在本次 GitHub 上传中实施。

GitHub 上传保留 M2 的原始报告与 MOCK 截图；报告中的“未推送”描述的是 M2 验收当时的状态。后续上传记录见 [GITHUB_PUBLISH.md](reports/GITHUB_PUBLISH.md)。

预构建前端的第三方版权/许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。本项目尚未选择整体开源许可证，厂商 SDK 不随包分发。

**编制日期：2026-10-06。交付状态：源码调研＋设计＋分阶段开发任务，尚无产品实现。**

这不是可执行安装包，不包含已经发布的 Docker 镜像、实机驱动或通过验证的机器人支持列表。本文档中的产品命令、目录和界面都是待实现的目标，不应当作当前可运行功能。

## 要做成什么

让实验室新成员通过中文界面完成：选择机器人配置 → 检查部署电脑 → 预览改动 → 下载并启动已验证的软件环境 → 看懂结果 → 出错时导出诊断包。现场操作人员负责物理接线、机器人身份/固件确认和任何运动授权。

参考 IOENV 的配置驱动和预制镜像思路，不照搬人形机器人关节控制器。对 D1 先使用厂商高层 SDK，保留原厂运动控制。

**2026-10-07 用户确认的蓝图：** 沿用 IOENV 的“环境定义 → 容器管理 → 独立业务启动”分层，独立实现 D1Env 部署引擎。成品要让用户通过 UI 部署已适配的软件环境、启动指定功能，并看到可信的分层检查结果。真实 Docker/ROS 探针是 M3 阶段基础，D1 的只读 SDK、传感器与建图/导航继续按后续阶段接入。具体上游机制、代码落点、必须改造的权限及成功判定见 [IOENV 分层蓝图](docs/IOENV_BLUEPRINT.md)。

## 现在怎样交给 Codex

将本目录解压到一个新的本地文件夹，在 Codex 中选择该文件夹。先阅读 [设计](docs/superpowers/specs/2026-10-06-d1env-design.md)，采用本方案后，复制 [第一轮提示词](docs/CODEX_PROMPTS.md) 中的“第一轮”。这表示授权该轮规定的软件实现，不表示授权连接或移动机器人。

第一轮只做到 M0–M2：源码证据整理、部署计划引擎、中文向导和明确标注的演示流程。第二轮才接入真实 Docker 和安装包；真机只读与导航是之后的独立阶段。不要把所有阶段一次丢给代理自由发挥。

## 文档入口

| 文件 | 用途 |
|---|---|
| [AGENTS.md](AGENTS.md) | 给 Codex 的项目规则与硬边界 |
| [源码调研](docs/research/SOURCE_AUDIT.md) | IOENV 实际结构、值得参考和不能照搬之处 |
| [采用的 IOENV 蓝图](docs/IOENV_BLUEPRINT.md) | 用户确认的三层职责、上游机制映射与后续实施约束 |
| [原始来源索引](docs/research/SOURCES.md) | 官方仓库、原始文件路径、核验边界 |
| [产品与架构设计](docs/superpowers/specs/2026-10-06-d1env-design.md) | 用户流程、模块契约、兼容性和安全要求 |
| [第一阶段实施计划](docs/superpowers/plans/2026-10-06-d1env-foundation.md) | 可以逐任务执行的 M0–M2 计划 |
| [后续路线](docs/ROADMAP.md) | Docker、SDK、SLAM、导航、实机验收各自的门槛 |
| [验收矩阵](docs/ACCEPTANCE.md) | 什么证据才允许声称某功能完成 |
| [真机接入清单](docs/ROBOT_INTEGRATION_CHECKLIST.md) | 现场需要取得的具体信息 |
| [Codex 分轮提示词](docs/CODEX_PROMPTS.md) | 开工、继续、审查和真机阶段的指令 |

## 当前证据边界

已通过公开网页阅读 IOENV 主脚本、环境配置、控制器 launch、硬件接口说明及 D1 官方 SDK 文档/部分头文件。未实际拉取运行 IOENV 镜像，未编译 D1 SDK，未连接机器人。当前容器的外网 DNS 请求失败，因此没有通过本地 git 固定提交；Codex 必须在 M0 记录可验证的完整 commit SHA。不能将这里引用的 `main` 当作生产锁定版本。

本包不含任何真实部署截图、执行日志或真机测试成绩。后续截图必须来自实际运行，演示截图必须显示 MOCK 标识。

## 源码开发启动（默认 MOCK）

当前目录已安装隔离的 Python 3.10.20 环境并构建前端，可直接运行：

```sh
./scripts/start-demo.sh
```

入口默认 `http://127.0.0.1:8765`，自动新开独立 Chrome 窗口。一次性会话引导后地址中的 fragment 立即清除。请从该窗口使用向导；单独手输地址不能建立新会话。终端按 Ctrl+C 停止。端口占用会明确报错，不停止其他程序；必要时显式使用 `./scripts/start-demo.sh --port 8766`。

从源码重新准备开发环境，需要预先可用的 uv 和 Node 24.x/npm（本轮实测 Node 24.19.0）：

```sh
UV_PYTHON_INSTALL_DIR="$PWD/work/python" UV_PROJECT_ENVIRONMENT="$PWD/work/venv310" uv sync --locked --python 3.10
cd frontend
npm ci
npm run build
cd ..
./scripts/start-demo.sh
```

交付压缩包含已构建前端，不含虚拟环境或 node_modules；已有 uv 和 Chrome/Chromium 时可用启动脚本准备 Python 3.10。此处是 M2 研发入口，全新 Ubuntu 上面向终端用户的安装包属于 M3，尚未交付/验证。

向导提供成功演示与明确标注的就绪故障注入。点足、轮足、MaxPro 和未知型号均为候选，真实执行禁用。机器人遥测为 UNKNOWN/null；本机 Docker 只读探针通过也不能成为真实部署成功的证据。作业、事件和本次演示资源默认保存在 `work/state/`；取消只处理本作业拥有的演示资源。清空浏览器存储不会删除后台任务。服务重启后旧活动任务会显示 INTERRUPTED，不自动执行。

CLI 与 UI 使用同一服务。下列入口只读或只解析计划：

```sh
work/venv310/bin/d1env doctor
work/venv310/bin/d1env plan --profile demo --mode mock
work/venv310/bin/d1env plan --profile unknown --mode real_readonly
work/venv310/bin/d1env status JOB_ID
work/venv310/bin/d1env report JOB_ID --output work/my-report.md
```

未知真实配置的 plan 返回阻塞项并退出 1。report 拒绝覆盖已有文件；凭据始终去敏，UI 可选择是否遮盖 IP/序列号（默认开启）。没有 arm、运动或任意执行入口。M3 本地源码可显式选择 `software_test` 与 `ros-probe`，执行受限软件容器；默认仍为 MOCK。

## M2 验证与证据

```sh
work/venv310/bin/python -m pytest -q
.venv/bin/ruff check src tests
.venv/bin/mypy src/d1env
cd frontend
npm run test -- --run
npm run build
```

真实 API 的 Playwright E2E 需要一份仅用于测试的一次性本地引导凭据，通过 `D1ENV_E2E_TOKEN_FILE` 指向权限 0600 的文件。测试不会输出凭据，关闭 trace/video/自动截图；显式截图只在 fragment 清除后拍摄。没有测试凭据时直接失败，不将未验证记作 PASS。可运行 `D1ENV_E2E_TOKEN_FILE=<private-file> npx playwright test`；本轮实际结果与失败修复记录见报告。

当前证据：[M0 来源审计](reports/M0-summary.md)、[M1 核心](reports/M1-summary.md)、[M2 最终验收](reports/M2-summary.md)、[独立审查](reports/M2-review.md)、[实际 MOCK 成功截图](reports/screenshots/m2-mock-success.png)、[实际故障注入截图](reports/screenshots/m2-mock-failure.png)。本轮保留分支 `d1env-foundation` 与小提交，未推送或发布，停止于 M2。
