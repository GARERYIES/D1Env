# M2 最终实施与验收报告 · MOCK

日期：2026-10-06（Asia/Shanghai）。执行范围：Foundation **Task 0–7 / M0–M2**。结果：严格配置、只读检查、确定性计划、持久化作业、CLI/API、中文五步向导、成功/故障 MOCK 演示、去敏 JSON/Markdown 报告已交付。**没有真实部署或机器人验证结论；停止于 M2。**

## 工作区、架构与来源差异

开工时指定目录只有生成的 work/outputs，没有交接文件；从先前 D1Env 设计对话取得实际 11 文件压缩包，核对下载完成后安全解压，未覆盖已有文件。完整阅读 AGENTS、SOURCE_AUDIT/SOURCES、design、foundation 与 ACCEPTANCE；将原始交接文字保留为历史基线。当前独立 Git 分支为 `d1env-foundation`，已分任务小提交，未推送、未创建 PR、未发布。

实际代码结构：React/TypeScript 五步 UI 与 Typer CLI → 共享 ApplicationService → Profile Catalog、只读 Doctor、Plan Resolver → SQLite Store/Job Engine → 唯一 MockExecutor。Web 负责 localhost 会话与 CSRF；Report 只消费结构化数据并去敏。合同来源统一为 models.py 和 contracts.schema.json，前端类型与之对齐。

| 任务 | 本轮结果 |
|---|---|
| 0 / M0 | 6 仓真实提交、83 文件哈希、10 ELF 静态元数据、锁/schema/差异与 blocked 原因 |
| 1 / M1 | 严格类型/YAML；demo 与硬件候选隔离；缺失遥测 UNKNOWN/null |
| 2 / M1 | 默认本地只读探针、5 秒超时、输出限制、不同失败分类；实际本机运行 |
| 3 / M1 | 不可变规范化计划/ID；真实候选明确阻塞；禁止隐式降级 |
| 4 / M1 | SQLite 任务/事件/幂等；实际双进程锁；取消归属；重启 INTERRUPTED/盘点 |
| 5 / M2 | 共用 CLI/API；127.0.0.1；一次性 bootstrap、会话、Host/Origin/CSRF；无运动/任意执行 API |
| 6 / M2 | 中文五步、并排证据、未支持禁用、UNKNOWN、成功与故障页、刷新/重试、实际截图 |
| 7 / M2 | 凭据强制去敏、IP/序列号可选遮盖、实际导出、最终测试及独立审查 |

核到的上游差异：IOENV `bin/ioenv:285` 执行 shell 配置、`:385` 使用 xhost+、`:395/399` host 网络与 /dev、`:564–567` root/password SSH，onboard.env:21 为 privileged，均未复制为执行能力。现有控制器/硬件插件为 G1/X2/PM01，没有现成 D1。Edu 文档 CMake 3.8 与实际示例 3.16 不同；型号拼写及版本绑定需厂商确认。完整 API 文档补充部分单位/顺序，但时间、新鲜度、异常与失联语义仍不足。MaxPro 高层 SDK 不要求 ROS1，底层才需要；目录后缀不能替代确切 SDK 版本。具体提交与行证据见 [M0](M0-summary.md) 和 [SOURCE_AUDIT 第 7 节](../docs/research/SOURCE_AUDIT.md)。未编造任何提交号或版本。

## 实际环境与最终命令

开发机 Darwin 26.6.2 / aarch64；隔离 CPython 3.10.20 和本机 Python 3.12.0；Node 24.19.0 / npm 11.17.0。uv.lock：FastAPI 0.142.2、Pydantic 2.13.5、PyYAML 6.0.3、Typer 0.27.2、Uvicorn 0.54.0；pytest 9.1.1、Ruff 0.16.10、mypy 2.4.0。npm lock：React 19.1.1、TypeScript 5.9.3、Vite 8.3.3、Vitest 5.0.3、Playwright 1.63.0。浏览器 E2E 使用独立 headless Chromium 153.0.8010.12，revision 1243，与用户浏览器分开。

以下均为实际运行结果，日志副本在 reports/evidence/；不是预期结果。

| 实际命令（未注目录者在项目根） | 退出码 | PASS / FAIL / SKIP | 日志 |
|---|---:|---|---|
| `python3 work/evidence/task0_validate.py` | 0 | 6 仓锁/schema、83 哈希重算；8 负向均拒绝 | m0-final-validation.log |
| `work/venv310/bin/python -m pytest -q` | 0 | 90 / 0 / 0，10.25s | final-python310.log |
| `.venv/bin/python -m pytest -q` | 0 | 90 / 0 / 0，10.23s | final-python312.log |
| `.venv/bin/ruff check src tests` | 0 | 全部检查通过 | final-ruff.log |
| `.venv/bin/mypy src/d1env` | 0 | 17 源文件无问题 | final-mypy.log |
| `npm ci`（frontend） | 0 | 112 packages installed / 113 audited；0 vulnerabilities | final-npm-ci.log |
| `npm run test -- --run`（frontend） | 0 | 12 / 0 / 0，2.32s | final-frontend-unit.log |
| `npm run build`（frontend） | 0 | TypeScript＋Vite build 完成 | final-frontend-build.log |
| `npm audit`（frontend） | 0 | 0 reported vulnerabilities | final-frontend-audit.log |
| `D1ENV_E2E_TOKEN_FILE=<private-file> D1ENV_E2E_URL=http://127.0.0.1:8765 npx playwright test`（frontend） | 0 | 1 / 0 / 0，7.1s | task6-e2e.log |
| `.venv/bin/d1env doctor` | 0 | 真实本机检查；3 PASS、1 WARN、2 SKIPPED、1 UNKNOWN | doctor-local.json |
| `.venv/bin/d1env plan --profile unknown --mode real_readonly` | 1 | 正确拒绝真实未知配置；不是部署失败被隐藏 | cli-real-blocked.json |
| `./scripts/start-demo.sh` | 启动后手动中断为 130 | 启动冒烟 PASS：独立 Chrome、标题就绪、fragment 清除、根路径 HTTP200、未认证 catalog HTTP401 | demo-launch.log |

90 是独立 Python 用例数，在两个解释器重复运行，不将它写成 180 个独立测试。Vitest、E2E 和来源锁负向用例分别计数。pytest/Vitest/E2E 没有 skipped；主机的 GPU/NETWORK 两项 SKIPPED 是检查状态。A13–A24 共 12 个后续场景为 NOT_RUN，不能计入本轮 PASS。最后源码/静态检查通过后仅编辑文档与整理交付。

npm ci 实际还记录了 whatwg-encoding 弃用和 fsevents 安装脚本未批准的警告；未绕过脚本审批，测试/build 在该状态下通过。初期四个开发工具安全公告通过升级至实际可用锁定版本处理，最终 audit 为 0；不把 audit 等同于完整安全证明。

CLI 已实际读取最后一个 FAILED MOCK 作业，并写出 [JSON](m2-mock-diagnostic.json) / [Markdown](m2-mock-diagnostic.md)。报告生成时重新执行本机只读检查，各检查保留自己的观测时间；这是失败作业的诊断快照，不是截图时刻的机器人数据。

## TDD 失败与修复记录

Task 1/2/3/4/5/7 初始测试实际因未实现模块失败（退出 2），然后逐项实现并通过；M1 当时 27 项合同/检查/计划和 21 项作业/恢复通过。Task 6 空 App 初始 7 项失败（退出 1）；另外出现过夹具类型 build 失败、重复文字定位失败、npm ERESOLVE、取消入口缺失和过期预览覆盖。实际失败未删，阶段细节见 [M1](M1-summary.md) 与 [UI 执行记录](evidence/task6-summary.md)。

真实 E2E 前两次退出 1：第一次已运行成功但标题与事件文字重名；第二次已完成成功/刷新/故障但同一故障消息有两条事件。修正精确定位，保留独立不执行脚本断言，最终真实 E2E 通过。最终再加入刷新失败作业、保留原 plan_id/新 key 的重试断言。失败日志 `task6-e2e-attempt1.log`、`task6-e2e-attempt2.log` 保留，不伪称首次运行通过。

独立审查真实复现并关闭 5 项 P2：自身 cookie/header 去敏遗漏、非 ASCII 认证输入产生 500、空/非有限遥测可标 PASS、中断恢复后重试换成默认计划、自由文本 IPv6 遮盖遗漏。IPv6 无空格标签的残余也先 RED 后修复。另补 literal-true readiness 四个 RED 回归，以及 UTF-8 和超时标记输出长度 RED 回归。详见 [独立审查](M2-review.md)；审查者独立最终 Python 90/90、UI 12/12、Ruff/mypy 均退出 0。

## A01–A12 验收

下表 PASS 限定静态来源、软件或 MOCK，不升级为真实 Docker/SDK/硬件验证。

| ID | 结果 | 实际证据与边界 |
|---|---|---|
| A01 | PASS · static | 真实 SHA/83 哈希/schema；缺失许可/版本明确 blocked |
| A02 | PASS · software | unknown/真实候选阻塞；真实模式按钮禁用；额外权限字段拒绝 |
| A03 | PASS · software | CPU MOCK/diagnostics 无 GPU 不阻塞；GPU 状态 SKIPPED |
| A04 | PASS · injected cases + local probe | 缺可执行文件/daemon/permission/timeout 分别测试；实际本机 info/version 只读；未提权 |
| A05 | PASS · software | 未知字段、执行型 YAML、重复键、路径/主机/argv/工件输入拒绝；shell=False |
| A06 | PASS · MOCK/process/browser | 稳定 ID、SQLite＋POSIX 锁、实际双进程竞争、浏览器双击只提交一次 |
| A07 | PASS · MOCK/recovery | 旧 STARTING/VERIFYING 转 INTERRUPTED＋盘点；不自动成功/重试 |
| A08 | PASS · MOCK ownership | 取消检查 device/inode、保存 maps/bags/其他任务；取消 UI 单元测试 |
| A09 | PASS · API/browser | 无会话、异常 Host/Origin、跨站、CSRF、bootstrap 重放、SSE 均拒绝；实际同源闭环通过 |
| A10 | PASS · software | 无值/旧/未来/非有限数据不得正常；UI 电量/姿态 null/UNKNOWN |
| A11 | PASS · actual MOCK UI | 实际成功与故障截图，所有页有 MOCK；Docker/真机未验证；运动禁用 |
| A12 | PASS · MOCK integration | 成功/失败刷新、原计划重试、故障证据与纯文本日志、真实 JSON/Markdown 下载、可选标识去敏 |

## 实际截图来源

截图来自本次本地 API＋生产构建页面的 Playwright 浏览器，viewport 1440×1040，loopback 地址 `http://127.0.0.1:8765/`。在一次性 fragment 清除后拍摄，trace/video/自动失败截图关闭；未使用生成图或绘图代替证据。根代理与审查者均实际查看两张 viewport 图。

| 图 | 拍摄时间（Asia/Shanghai） | 说明 |
|---|---|---|
| [成功 viewport](screenshots/m2-mock-success.png) / [full page](screenshots/m2-mock-success-full.png) | 2026-10-06 15:03:59 | SUCCEEDED、MOCK/mock、未部署真机、UNKNOWN/null；按规定复用本轮先前成功的同一计划作业，保留原作业观测时间 |
| [故障 viewport](screenshots/m2-mock-failure.png) / [full page](screenshots/m2-mock-failure-full.png) | 2026-10-06 15:04:02 | 当前 verify_failure 故障注入，FAILED/MOCK_READINESS_FAILED；不是实际厂商/容器故障 |

MOCK 成功只证明预设软件流程和 mock_ready=true；没有真实下载字节、容器部署或机器人就绪证明。故障页面日志中的 `<script>` 保持纯文本，浏览器断言该属性没有执行。

## 审查、决定与阻塞

误报成功、注入、权限和重复任务审查已完成。Literal true、mock scope、严格遥测和中断状态防止软件误报；注册 local/白名单 argv/无自由执行字段限制输入；localhost Host/Origin/CSRF/会话限制浏览器请求；SQLite/POSIX 锁和持久幂等规则限制重复任务。没有剩余可操作发现，结论限于本轮审查范围。

实施决定及代价：

1. 当前新目录已与现有仓库隔离，直接建立 d1env-foundation 分支；不再次搬到 worktree。若位置选择不合适，代价仅迁移目录。
2. 原始设计/README 保留并增加注明日期的实施入口，避免抹去交接基线；代价是同时可见历史状态，顶端已明确更新。
3. 严格请求增加 demo_scenario=success/verify_failure，仅用于 MOCK 故障注入；代价是一个新增合同字段，不可选择命令/硬件。
4. 计划保存不可变原始请求以便启动重新解析，UI 重试使用原 plan_id＋新 key；代价是计划持久化增加该数据字段。
5. 用户明确要求交付后停在 M2，保留本地分支/提交，不开展 M3 或合并/发布流程。研发演示不是最终 Ubuntu 安装包。

| 未取得或未验证内容 | 状态/具体原因 |
|---|---|
| Edu/MaxPro SDK 确切语义版本与固件绑定 | blocked；tags/releases/目录不能证明二进制版本；字段 null＋原因 |
| MaxPro 仓库级 SDK 再分发许可 | blocked；未见 LICENSE/COPYING，第三方 JSON 许可不足 |
| Edu 文档子仓 | blocked/unretrieved；gitlink 未初始化，不能声称已审 |
| 真实生产镜像 digest、固件/工件清单、完整 SBOM | blocked/not_provided；本轮不拉取镜像或安装 SDK |
| A13–A17 / M3 | NOT_RUN；真实容器生命周期、下载恢复/离线导入、新 Ubuntu 安装/已有系统兼容 |
| A18–A19 / M4 | NOT_RUN；实际 SDK 只读调用、真实遥测、机器人配置写入 |
| A20–A21 / M5 | NOT_RUN；传感器/时间/TF、建图定位导航与回放链 |
| A22–A24 / M6 | NOT_RUN；控制权限、断连、本体停止、物理急停及模式差异 |

未连接机器人、未运行厂商 SDK/demo、未创建/停止真实容器、未修改网卡/驱动/固件、未实现 arm 或运动接口。Docker info/Compose version 是唯一 Docker 接触路径。所有研发测试服务器已停止，临时 bootstrap 文件已删除，只关闭本轮自建浏览器窗口，未操作用户个人浏览器窗口。

## 启动与交付

当前目录运行 `./scripts/start-demo.sh` 即可再开独立 Chrome MOCK 向导。README 提供从源码准备、CLI、端口占用与停止方法。源码交付包含锁文件、构建后的前端、文档、测试、报告和实际截图；不含虚拟环境、node_modules、凭据、运行数据库或厂商 SDK 二进制。M0 原始 checkout/完整命令留在当前 work/；随包提供本轮精选去敏测试证据，不能将压缩包当成 SDK 发行包。

下一阶段入口仅指向 ROADMAP 的 M3 门槛，**没有自动开始下一阶段**。

## GitHub 发布前补充（2026-10-06）

后续用户授权上传 GitHub。发布审查发现，旧失败测试日志中 pytest 的 authenticated fixture repr 保留了一枚本次测试使用的 CSRF 值，另有 macOS 临时目录中的个人路径。它们不在产品诊断报告中，但被收入原本地证据提交与压缩包，因此前次证据包的去敏检查不完整。

已清理当前可交付证据，并重新封装压缩包。由于新增清理提交不能移除旧 Git blob，GitHub 从仅含清理后文件的新发布历史上传，原本地研发分支历史保留且不推送。发布前复核所有待上传文件和压缩包，不输出或重复该值。上传、哈希和 Linux 限制记录见 [GITHUB_PUBLISH.md](GITHUB_PUBLISH.md)。这次补充不改变原测试命令/结果，也不新增 Linux 或真机验收结论。
