# D1Env：交给 Codex 的研发包

> **2026-10-06 实施更新：Task 0–7 / M0–M2 已实现并验收。** 可运行中文 MOCK 向导、真实本机只读检查、持久化任务和去敏报告。启动方式见本文末尾；本轮结果见 [M2-summary.md](reports/M2-summary.md)。下方“尚无产品实现”和网页调研限制是原始交接基线，保留作历史记录。真实容器、厂商 SDK、真机和运动仍未实施。

## GitHub 使用与 Linux 就绪状态

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

## 现在怎样交给 Codex

将本目录解压到一个新的本地文件夹，在 Codex 中选择该文件夹。先阅读 [设计](docs/superpowers/specs/2026-10-06-d1env-design.md)，采用本方案后，复制 [第一轮提示词](docs/CODEX_PROMPTS.md) 中的“第一轮”。这表示授权该轮规定的软件实现，不表示授权连接或移动机器人。

第一轮只做到 M0–M2：源码证据整理、部署计划引擎、中文向导和明确标注的演示流程。第二轮才接入真实 Docker 和安装包；真机只读与导航是之后的独立阶段。不要把所有阶段一次丢给代理自由发挥。

## 文档入口

| 文件 | 用途 |
|---|---|
| [AGENTS.md](AGENTS.md) | 给 Codex 的项目规则与硬边界 |
| [源码调研](docs/research/SOURCE_AUDIT.md) | IOENV 实际结构、值得参考和不能照搬之处 |
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

## M2 当前开发演示启动

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

未知真实配置的 plan 返回阻塞项并退出 1。report 拒绝覆盖已有文件；凭据始终去敏，UI 可选择是否遮盖 IP/序列号（默认开启）。没有 arm、运动、任意执行或真实容器入口。

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
