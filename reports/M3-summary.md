# M3 Mac 软件部署候选交付

日期：2026-10-07，Asia/Shanghai。分支：`codex/m3-mac-product`；项目版本：`0.2.0`。本轮按用户确认的 IOENV 蓝图推进 Mac 可开发、可运行的软件部分，未把完整 M3 或 D1 成品标为完成。

**已实际完成：中文 UI 导入受信 ROS 镜像、部署本作业容器、检查真实消息、刷新恢复、故障显示、停止/清理和去敏报告；同时生成自带 Python 的 Mac Apple Silicon 便携候选。** 默认仍是 MOCK。Docker/ROS 软件通过只证明软件通信；D1 型号仍禁用，真实电量/姿态为 UNKNOWN/null，SDK、传感器、建图/导航和运动未实施。

## 蓝图落实与源码差异

| IOENV 实际机制 | D1Env 当前模块 | 改造理由与本轮证据 |
|---|---|---|
| `env.d`、环境解析，定义镜像/运行参数 | 严格 Profile、`models.py`、`planner.py`、`profiles/ros-probe.yaml` | 配置只能是数据；可信本地工件、架构和固定操作进入确定性计划。拒绝自由镜像、shell、挂载和未知字段；同输入计划 ID 稳定 |
| pull/create/reuse/start/stop/remove | `docker/client.py`、`executor.py`、`offline.py` 与持久 JobEngine | 固定 argv/Compose，资源身份和作业标签核验；重复与遗留资源阻止第二套部署。实际容器生命周期、同名外部对象/附着对象保护和导入已验证 |
| `run` 最后进入容器 Bash；业务由独立 launch 启动 | 固定 ROS publisher/subscriber、`containers/ros-probe/` 与 readiness 检查 | 容器 running 不算业务正常。必须收到本作业、递增、有限且新鲜的时间戳消息；无发布者、过期、错误来源均失败 |
| 开发环境中的 host 网络、设备目录、特权等便利参数 | 受限内部 bridge、non-root、只读根、tmpfs、cap_drop ALL、no-new-privileges、资源限制 | 不照搬为网页能力。没有主机卷、公开端口、host 网络、privileged 或设备授权；Docker daemon 操作权仍属于高权限信任边界 |
| 原脚本主要同步操作 | SQLite、目标 lease、历史计划/任务/API/CLI/UI | 中断显示 INTERRUPTED，不自动重启；盘点未知/遗留资源明确阻止新任务。CLI 等待终态，不再提前退出 |

保留原设计与 M0–M2 交付；本轮源码为独立部署引擎。来源基线见 `docs/research/SOURCE_AUDIT.md`、`UPSTREAM_LOCK.json`，采用关系见 `docs/IOENV_BLUEPRINT.md`。没有执行上游安装器、IOENV 镜像或厂商业务 demo。

## 当前启动与五步使用

本地交付目录为 `outputs/D1Env-M3/`，同目录 `START-HERE.md` 提供用户入口；便携包是 `D1Env-0.2.0-macos-aarch64.tar.gz`，配套镜像为 `d1env-ros-probe-m3-aarch64.tar`。

1. 在 Apple Silicon Mac 解压便携包，使用包内 `D1Env.command` 或 `./d1env.sh`。本机须已有 Chrome；默认新开独立窗口、MOCK 模式。用户不用安装 Node、uv、系统 Python，不用编译 ROS 或编辑 YAML。
2. 五步向导选择“真实软件测试”与 ROS 通信配置。该模式需要已有且可访问的 Docker/Compose；工具不会安装 Docker、启动 daemon 或修改权限。
3. 在执行电脑页选择配套 ROS 文件导入；固定发行摘要、大小、架构、OCI blob、来源和镜像身份由服务器验证。镜像准备通过后仍须另做业务检查。
4. 预览实际容器、内部网络、权限和软件范围，点击部署；查看发布者/订阅者与当前消息检查。界面另外提供清楚标注的无发布者故障注入。
5. 使用“停止测试服务”或“清理本作业遗留服务”，从历史入口恢复原计划，按原计划显式重试或导出报告。关闭网页/停止 Web 进程不会冒充容器清理；软件 Stop 也不是硬件急停。

CLI/API 共用同一服务；CLI 先用 `plan --mode software_test --profile ros-probe` 保存预览计划，再用 `deploy PLAN_ID --request-key REQUEST_KEY` 执行并等待终态，失败返回非零。API 保持仅 `127.0.0.1`、会话、Host/Origin/CSRF 校验；镜像导入为专项接口，客户端不能提供期待 image ID/摘要或任意 Compose。安装资源与当前用户私有状态目录分开，Mac 状态默认 `~/Library/Application Support/D1Env`。

## 工件与来源锁

| 工件 | 实际大小 | SHA-256 |
|---|---:|---|
| Mac 便携候选 `D1Env-0.2.0-macos-aarch64.tar.gz` | 27,787,744 bytes | `d5befe4ba377dd4cf4708e1f1297aa5d23624b14d82f1e57588795f0f2ce84f4` |
| 配套 ROS 数据归档 `d1env-ros-probe-m3-aarch64.tar` | 140,574,720 bytes | `8da67f547b7885be741f8fbf0b2fd06f989cec0e2b7ed41d4a24c2adaf2414df` |
| 构建输入 wheel `d1env-0.2.0-py3-none-any.whl` | 研发输入，位于 `work/m3-dist/` | `efc0464d4bd7bbaa28281ec37d6ce4f1e1a2eee4de0b46914ce7b82c72a0bb5d` |

Mac 包自带 Python 3.10.20、固定且核对 hash 的运行依赖、前端与 Profile/来源锁。实际搬迁到包含中文/空格的新目录，以空 PATH 执行 help、`.command --help`、doctor 和回环 HTTP/JS；未认证 API 401，非法 Host 403。包内 2,347 个文件/链接的路径、类型、大小、权限与摘要均核对通过，当前项目源/资产逐字匹配；SHA sidecar 一致。`.command` 已提供，Finder 双击、网络下载隔离与签名/公证尚未验收。

Python 的原始官方 release 归档实际取得并核对大小/SHA，记录于 `docs/build/PYTHON_RUNTIME_LOCK.json`。`python-build-standalone` tag `20260610` 实际提交为 `f1d7b92301235781d4de2493578773aaa413c0a5`；这是构建工具提交，**CPython 源码提交仍为 null**。构建先核对原归档、来源锁与完整运行时树，再执行解释器。原未知来源运行时未用于最终候选。原始 Python LICENSE 保留，附带动态库的完整许可核对为 blocked；未验证 release 签名。

ROS 来源记录为 `docs/build/ROS_PROBE_LOCK.json`、`ROS_PROBE_PACKAGES.json`、`ROS_PROBE_OFFLINE.json` 和 `ROS_PROBE_SOURCES.md`：

- 官方 Humble `ros-core` Linux arm64/v8 基础平台 digest 为 `sha256:5d8bdefcfb553802cca2fff87233f0c0adfbbd50e87e7c64c9af9a098250e6b1`，Dockerfile 固定该不可变值。
- 实际 OSRF Dockerfile/许可证来源提交为 `58af41813ba67f611943c35c551387d652fcdbde`。基础与最终镜像的 389 个 dpkg 包、147 个 ROS package.xml 一致；没有新增 apt/pip 包。
- 实际最终 image ID 为 `sha256:52f259d5fa38acb3fd2018e1601593fc0f6ad1a85c8a968032695f9c15771a2c`，是本地 Docker 返回的 OCI index ID；不是已发布的 registry 生产镜像。对应平台 manifest 为 `sha256:de539eab9fcd31710ad7c0767d63657d1c5a4698fa15a08e0a131bcd27e8c8a5`。
- 初始真实候选 running 但无消息，未记 PASS；改为受限 UDP 与固定服务 DNS 单播发现后，收到实际 4 个样本、序号 4。原故障原因没有被未经证明地写成“只因 SHM”。

全项目正式许可证选择、完整发行许可审查仍待完成；不随包分发 SDK。本轮未发布镜像或推送 GitHub，现有 GitHub 发布版本仍是 M2。

## 实际环境、命令与退出码

测试主机：macOS 26.6.2（25G83）、aarch64；Docker Desktop 4.80.0，Engine 29.6.1，daemon Linux arm64，Compose 5.3.0。Python 3.10.20 / 3.12.0，Node 24.19.0；独立 headless Chromium 用于本地浏览器验证。上述 Mac Docker 内部 Linux 不等于原生 Ubuntu 桌面安装。

下表日志的去敏副本位于 `reports/evidence/m3/`，命令中的 `<…>` 是私有路径占位，实际值没有交付。总套件已通过后没有因整理文档重复跑功能测试。

| 实际命令/操作 | 退出码 | 通过/失败/跳过与范围 | 证据 |
|---|---:|---|---|
| `work/venv310/bin/python -m pytest --tb=short -q` | 0 | 297 / 0 / 0，58.76s；软件单元/集成边界替身 | `m3-final-python310.log` |
| `.venv/bin/python -m pytest --tb=short -q` | 0 | 297 / 0 / 0，59.38s；同一套件在 Python 3.12，不累加为 594 个不同测试 | `m3-final-python312.log` |
| `.venv/bin/ruff check src/d1env tests scripts/build-release.py` | 0 | 静态检查通过 | `m3-final-ruff.log` |
| `.venv/bin/mypy src/d1env scripts/build-release.py` | 0 | 24 source files，无错误 | `m3-final-mypy.log` |
| `npm test -- --run`，在 `frontend/` | 0 | 29 / 0 / 0 | `m3-ui-p1-green.log` |
| `npm run build`，在 `frontend/` | 0 | TypeScript/Vite 通过，27 modules | `m3-ui-build.log` |
| `D1ENV_E2E_SOFTWARE=1 D1ENV_E2E_ROS_BUNDLE_FILE=<配套包绝对路径> D1ENV_E2E_TOKEN_FILE=<私有0600文件> D1ENV_E2E_URL=http://127.0.0.1:18765 npx playwright test` | 0 | 2 / 0 / 0；真实 API、MOCK 与 Docker 软件流程，约 1.2m | `m3-ui-e2e-software.log` |
| 首次 MOCK 浏览器轮次（未启用软件 E2E） | 0 | 1 / 0 / 1；该 skipped 当时计软件 NOT_RUN | `m3-ui-e2e-mock.log` |
| 首次完整软件 E2E | 1 | 0 / 2 / 0；定位重复错误文本及 worker 重启后单次会话已消费，未记通过 | `m3-ui-e2e-software-first-failure.log` |
| `.venv/bin/python -m pytest tests/test_docker_executor.py tests/test_docker_offline.py tests/test_ros_probe.py -q` | 0 | 104 / 0 / 0；其中 62 Docker/导入、42 ROS。属于最终 297 的子集 | `m3-docker-probe-root-green.log` |
| `.venv/bin/python work/evidence/m3-image-integration.py` | 0 | 真实 ROS 新鲜消息、停止发布者后 stale、idle 无样本，3 个场景通过 | `m3-image-integration.json` 与命令 JSONL |
| `.venv/bin/python work/evidence/m3-docker-real-lifecycle.py` | 0 | 真实 preflight/acquire/configure/start/verify；成功、无发布者故障、重复资源及拥有资源清理符合预期 | `m3-docker-real-lifecycle-final.log`、两份 `actual-lifecycle.json` |
| `.venv/bin/python work/evidence/m3-docker-real-import.py` | 0 | 实际 Docker load exit 0，之后 reused 不再 load；12 个已有镜像绑定保留、私有暂存清理 | `m3-docker-real-import.json` |
| `.venv/bin/python work/evidence/m3-docker-real-ownership.py` | 0 | 同名外部容器保留；外部对象附着网络时保留该对象/网络，盘点反映剩余而非假报清理完成 | `m3-docker-real-ownership.json` |
| 最终便携包构建与 `.venv/bin/python work/evidence/m3-package-final-smoke.py` | 0 | 真实搬迁/空 PATH/HTTP/401/403/2,347 payload 核对通过 | `m3-package-final-build.log`、`m3-package-final-smoke.json` |
| `.venv/bin/python work/evidence/m3-store-aux-fixed-green.py` | 0 | 130,475 次实际 SQLite/MOCK 调用，0 错误；128 次辅助文件瞬态重读。无 Docker/SDK | `m3-store-aux-fixed-green.json`、`m3-store-aux-diagnosis.json` |
| 独立审查 `.venv/bin/python -m pytest -q` | 0 | 297 / 0 / 0，60.98s；同一软件套件的独立复核 | `M3-review.md`；原输出保留私有工作目录 |
| 独立工件审查 `.venv/bin/python work/m3-artifact-audit.py` | 0 | 当前源码/资产匹配，0 结构问题、0 真实凭据/本机私人路径发现；ROS 归档纯文件验证，Docker 调用为 0 | `m3-artifact-audit.json`、`M3-review.md` |

真实浏览器还覆盖：导入后预览、双击单提交、当前通信、刷新同作业、网络读取故障注入后 UNKNOWN、恢复、停止、无发布者失败、历史原计划恢复、下载 JSON/Markdown、显式重试和清理。界面每 3s 读取当前健康；读取失败立即 UNKNOWN，超过 5s 无新观测也降级。历史 SUCCEEDED 不代表当前正常。事件读取不重复执行健康探针。

这些场景验证与 pytest/Vitest 数量分别记录。最后 297 Python、29 UI、2 E2E 均无失败/跳过；它们不包含 Ubuntu VM、空 daemon 或 D1 真机测试。

实际发行构建命令（研发环境，三个步骤均 exit 0；`uv` 指向本机已有构建工具）：

```sh
uv build --offline --wheel --out-dir work/m3-dist
.venv/bin/python scripts/build-release.py --portable \
  --runtime work/python/official-20260610/python \
  --runtime-source-archive work/python/cpython-3.10.20-20260610-official.tar.gz \
  --runtime-provenance-json docs/build/PYTHON_RUNTIME_LOCK.json \
  --wheel work/m3-dist/d1env-0.2.0-py3-none-any.whl \
  --requirements work/m3-runtime-requirements.txt \
  --platform macos --architecture aarch64 \
  --output outputs/D1Env-M3/D1Env-0.2.0-macos-aarch64.tar.gz
.venv/bin/python work/evidence/m3-package-final-smoke.py
```

未传 `--allow-downloads` 或替代缓存参数；依赖从已有 uv 缓存取出，实际安装使用 offline/hash/no-deps/binary-only，本项目 wheel 使用 no-index/hash。这是研发构建条件，uv 不进入用户运行依赖。获取原始 Python 官方归档是另外的 HTTPS 来源取得步骤，未被写成“整个开发过程完全离线”。

## TDD、真实失败与修复记录

每项先观察失败测试，再最小实现并回归。选定 RED/GREEN 日志随证据目录保留，包括软件契约/计划、导入/来源、当前健康、遗留资源阻塞、CLI 独立进程、发行来源和 SQLite 防护。`INDEX.json` 分别保存原始私有日志 SHA 与去敏副本 SHA；来源锁中的 raw evidence hash 不被去敏副本替换。

独立审查发现五项：可信资产可同组改写、旧任务遗留资源允许重复部署、CLI 提前退出、断连后保留旧绿色结果、SQLite WAL/SHM 删除瞬态误拒绝。均修复并独立复核，详情见 `M3-review.md`。其中全套软件回归曾真实为 **289 passed / 3 failed、exit 1**；保留失败记录，最终才记 297 passed。SQLite 初始压力探针首阶段 42,435 次/114 错误；后续阶段意外保留连接的准备问题明确排除，最终无持久锚连接的 130,475 次才用于验证修复。

Docker 日志配置、初始 ROS 发现、离线构建/归属测试准备和早期便携构建也出现过失败；没有用外层记录脚本 exit 0 代替产品断言退出码。最终真实无发布者场景返回 `ROS_PROBE_NOT_READY`，作为故障注入预期而通过测试，不能写成业务就绪。

最终工件广谱扫描初次发现 44 个需要分类的匹配；独立核对为上游公开 Python/Tcl 构建元数据、SBOM 和文档例子，保留原材料/许可，没有把它们误报成真实密钥，也没有声称包内不存在任何绝对路径。启发式扫描不等于对所有未知凭据的形式证明。

提交前 `git diff --cached --check` exit 2 的条目仅为保存的 pytest RED 原始输出中的行尾空白/末尾空行；为保持已审证据摘要，没有修改这些日志。对日志之外的源码/文档执行 `git diff --cached --check -- . ':(exclude)reports/evidence/m3/*.log'` 实际 exit 0。该格式检查不替代上表的软件测试。

## A13–A17 验收与未验证范围

| 验收 | 本轮状态 | 实际证据/限制 |
|---|---|---|
| A13 真实 Docker 生命周期 | PASS，Mac/Linux aarch64 daemon 软件范围 | 创建、启动、消息验证、停止拥有容器/网络，真实镜像保留；非 D1 功能验收 |
| A14 容器活着但业务异常 | PASS，软件范围 | 无发布者、0 样本、过期/未来/错误来源校验；浏览器断连或无新观测 UNKNOWN。硬件遥测仍缺失 |
| A15 摘要/路径/离线导入 | PARTIAL | 摘要、OCI、路径/链接/大小、真实 load/reuse、已有绑定保护 PASS；远端下载断点续传未实现，空 daemon 导入 NOT_RUN |
| A16 全新 Ubuntu VM 安装 | NOT_RUN | 没有目标 Ubuntu 22.04 x86_64 运行时工件/全新桌面 VM 证据；Mac 或 Docker Linux 不能替代 |
| A17 已有系统与 Docker | PARTIAL | 当前 Mac 搬迁、已有 Docker 镜像/其他项目保护、重复部署通过；原生 Linux 既有安装/升级/回滚 NOT_RUN |

其他明确未验证/阻塞：

- 带存活 Docker 服务的 Web/API 进程硬中断后原生恢复验收 NOT_RUN；目前恢复盘点、INTERRUPTED 与不自动执行经实际 SQLite/线程/锁和 Docker 边界替身测试，实际浏览器刷新恢复另有证据。
- Intel Mac、旧 Mac 版本、Finder 双击完整流程、下载隔离/Gatekeeper、签名/公证、正式安装升级/卸载、自动安装 Docker 均 NOT_RUN/未实现。
- Python 附带库及整体发行许可完整性 blocked，项目正式开源许可证未选择；没有 release 签名通过证据。
- 生产 registry 发布、远端镜像下载恢复、Linux 自包含包和空 daemon 离线首次安装未交付。配套镜像只锁定 aarch64；不假称 x86_64 支持。
- 精确 D1 型号＋SDK 实际版本＋固件兼容性＋控制权限、遥测单位/时钟/失联行为仍 blocked。已有二进制静态记录没有被当作 SDK 运行版本；未知提交/版本保留 null。
- 厂商 SDK、机器人连接、传感器、建图/导航、arm/运动、网卡/驱动/固件写入、现场安全/本体侧失联停止全部 NOT_RUN。软件 Stop 不能证明硬件停止。

## 实际截图、报告与清理

截图来自本轮实际运行的中文前端与本地 API：独立 Playwright Chromium、回环地址 `127.0.0.1:18765`、1440×1040 viewport，Asia/Shanghai 2026-10-07。不是生成图片；前端产物与最终包资产逐字一致，截图并不冒充 Finder/Gatekeeper 的发行安装验证。会话 fragment 已清除后才截图；trace/video/自动失败截图关闭，凭据不进入交付。

| 场景 | 实际截图 |
|---|---|
| MOCK 成功、故障注入，保留 MOCK 标识 | `screenshots/m3-ui-mock-success-viewport.png`、`screenshots/m3-ui-mock-failure-viewport.png` |
| 受信 ROS 镜像导入 | `screenshots/m3-ui-software-import.png` |
| 真实软件消息通过，D1 未实施 | `screenshots/m3-ui-software-success-viewport.png` |
| 真实无发布者故障注入 | `screenshots/m3-ui-software-failure-viewport.png` |
| 浏览器网络读取故障，历史成功/当前 UNKNOWN | `screenshots/m3-ui-software-network-fault-injection.png` |
| 去敏软件报告 | `screenshots/m3-ui-software-report.png` |

全页原图也保留，合计 11 PNG。`m3-ui-software-report.json` / `.md` 来自真实浏览器下载，mode 为 `software_test`、verified_scope 为 `software`，事件来源为 docker；源审计中历史“未运行 Docker”的说明保留其自身 M0 语境。

浏览器 finally 清理本次创建的软件任务；根代理补清首次失败轮次拥有的作业，并逐项复核。最后 `docker --context default ps -a --filter label=io.d1env.project=d1env` 与同标签 `network ls` 实际 exit 0、结果为空；原有项目/镜像保留。测试 Web 服务已关闭，临时私有引导文件已移除。没有 Docker prune、删除用户镜像/地图、运行 SDK 或机器人操作。

## 下一轮入口与发布状态

按采用的蓝图继续完成 M3 的 Linux 发行闭环：目标 x86_64 的可信运行时/ROS 工件、完整许可记录、Ubuntu 干净 VM 与已有环境验收、真实进程中断恢复、安装/升级/卸载与下载恢复。满足 A13–A17 完整证据后再称 Linux 可安装产品。

随后 M4 才确认一个精确的 D1 型号/SDK/固件组合并实现只读业务启动及可信遥测；M5 传感器、建图/导航和 M6 运动继续另轮授权。不得以本轮 CPU ROS 通过提升 D1 支持等级。

本轮保留小型本地提交，未自动推送、发布镜像或覆盖已冻结 M2 发行。现有 GitHub 发布仍为 M2；本地 M3 工件、报告、证据和截图是本轮交付。停在上述 Mac 软件候选范围。
