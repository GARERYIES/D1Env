# M3 Mac 独立安全与正确性审查

日期：2026-10-07（Asia/Shanghai）。**M3 本机软件候选的独立审查已完成，已发现的五项问题均修复并复核；没有剩余已知软件阻断。** 结论限于下列实际检查范围，不能据此宣称正式签名发行、Linux 开箱即用或真机就绪。分支 `codex/m3-mac-product`；以最后 M2 提交 `7b2dd7c` 为基点，审查当前工作树及新增模块，不能仅以 HEAD diff 代表全部 M3 实现。

本审查独立于实现者，真实读取代码并运行软件回归。使用 code-review 技能的 Standards / Spec 两轴；当前并行实现任务已占用代理容量，两轴由同一独立审查者顺序检查，未虚构第二位审查者。必读规则、原设计、IOENV 蓝图、M3 Mac 计划和 A13–A17 是范围依据。

审查没有连接机器人、运行厂商 SDK、启动/停止真实容器、修改网络/驱动/固件或发布/push。Docker 的实际生命周期和浏览器证据由对应实施者记录，本报告将区分独立软件复核与转述的整合证据。原始 pytest 输出仅写私有工作目录；报告不含会话或测试凭据。

## Standards

### P2 / 已独立复核修复：可信资源允许同组改写

初始位置：`src/d1env/runtime.py` 的 `validate_assets_dir()` 仅拒绝 world-writable 位，没有拒绝 group-writable 资源。规则依据：可信安装资源与状态分离、来源可审查，以及不能让输入成为任意执行能力。若本地目录错误设置为可由不受信组修改，组成员可替换同源页面/JS 或 Profile；localhost 会话边界不能补偿被替换的可信页面。本审查未声称默认包存在远程攻击入口。

实际纯软件复现：创建最小合法资产目录，把页面 JS 设为 `0664`，原验证仍返回该可信目录；未启动服务。修复后同一探针被拒绝。当前验证同时检查 current-user/root 归属、组写/其他用户写权限及构建文档资源。

### 已检查的硬边界

- DockerClient 固定 `default` context、剔除 Docker/Compose 环境重定向、无 shell 执行，仅接受有限 argv；超时/取消只终止本次 CLI 进程组。
- DockerExecutor 只接受已锁定 `d1env/ros-probe` 本地构建、准确镜像 ID 和架构；Compose 由后端生成，非 root、只读根文件系统、cap_drop ALL、no-new-privileges、资源限制、私有 tmpfs、项目内部 bridge，无主机目录挂载和公开端口。
- 删除使用完整资源 ID，再核验作业/计划/角色标签、名称和镜像；停止后再次核验；有附着对象的网络保留，未知盘点不记停止成功。Docker 权限仍明确是高权限信任边界。
- Store 检查 SQLite/WAL/SHM 的 symlink、hardlink、属主及可写权限，资源根目录拒绝链接。严格 YAML、数据字段和 unsupported 型号边界保留。
- API 新增 stop/import 仍经过会话、Host/Origin/CSRF；普通 JSON 流先限制大小，镜像上传使用可信发行大小和摘要，客户端不能指定期待镜像或模板。

这些是代码与软件回归范围的检查，不提升为 Ubuntu 或硬件通过结论。

## Spec

### P1 / 已独立复核修复：健康失败或中断后创建第二套遗留服务

初始位置：`src/d1env/jobs/engine.py` 的 `get()/submit()` 与 `Store.claim()`。M3 Review Focus 2/4 要求中断盘点、历史成功复核、重复请求不创建第二套容器。

原路径把过期 ROS 健康失败的 SUCCEEDED 作业改为 FAILED，却留下原服务；新 key 不再被活动任务索引阻挡，能够创建第二套作业。同样影响仍有资源的 INTERRUPTED 作业。独立复现使用实际 SQLite/线程/POSIX 锁及 Docker 边界替身：第一次成功后人为返回 stale、保留旧 running 资源，再提交新 key，观测到 2 个 running 作业、10 次执行调用。没有运行真实 Docker。

修复把旧软件作业盘点放在新建作业的目标 lease 获取之后：资源残留、未登记或 inventory unknown 时返回 `SOFTWARE_RESOURCES_PENDING`。原独立探针现在阻塞新建，running 仍为 1。复核该盘点没有在 claim 写事务中 append 新事件；Docker inventory 的 accounting context 不回入取消写操作，未识别出该路径的数据库写死锁。

### P1 / 已独立复核修复：独立 CLI 进程退出使部署线程中断

初始位置：`src/d1env/cli.py` 的 `deploy()` 和 JobEngine 的 daemon worker。任务要求 CLI 与 UI 共用可实际运行的部署服务；同进程 CliRunner 不能证明独立 CLI 的任务生命周期。

原 CLI 启动 daemon worker 后立刻返回 exit 0。实际独立子进程的 MOCK 复现返回 PLANNED，2 秒后数据库仍 PLANNED，恢复将其置为 INTERRUPTED。修复后 CLI 等待终态并对失败返回非零；同一实际子进程复现返回 SUCCEEDED，2 秒后仍是 SUCCEEDED，恢复没有中断任务。此验证只有 MOCK，Docker 接触仅为既有只读主机探针。

### P1 / 已独立复核修复：请求失败后保留旧的绿色当前状态

初始位置：`frontend/src/App.tsx` 的软件任务 poll catch 仅展示错误，不清除 `current_software_ready=true`；ResultsPage 使用该旧值显示当前软件与消息通过。M3 Review Focus 3 及原设计要求无数据/过期数据不能显示正常。

可复现路径：软件部署和当前健康先成功，再使 job/events 请求拒绝、会话过期或本地服务断连，等待轮询。原路径让旧绿色勾和“当前检查通过”继续显示。本项首次发现是明确代码路径，没有把静态发现写成独立浏览器复现。

当前修复在请求失败时将当前软件健康置为 null/UNKNOWN，保留历史任务；正向观测超过五秒或页面重新可见时检查有效期。独立运行前端回归 29 passed，包括失败请求和挂起请求的失效用例；实际读取实施者保存的运行截图，断连注入图明确显示 `CURRENT_HEALTH_UNAVAILABLE`、历史 SUCCEEDED / 当前 UNKNOWN，容器与消息均 UNKNOWN。截图取得者与本审查的独立复核分开记录。

### P1 / 已独立复核修复：SQLite 辅助文件瞬态被当作不安全状态

全量独立 pytest 在新加入的链接/权限防护之后实际退出 1：289 passed、3 failed。失败发生于 `tests/test_recovery.py` 的 STARTING 恢复，以及 `tests/test_software_jobs.py` 的 stop/redeploy、unknown_inventory 路径；均在正常并发 SQLite 连接生命周期中抛出 `STATE_FILE_UNSAFE`。这不是被跳过的 Docker/硬件测试。

jobs 实施者随后用实际 Store 的四线程压力探针定位：42,435 次 connection close、114 次拒绝；捕获的 50 条均为 WAL/SHM 普通文件、正确 uid、0644、nlink=0，重读 47 次不存在、3 次恢复为安全 nlink=1 的新 inode，未见主数据库异常。本审查自己的第一遍 tracing 因 stdin 脚本的 multiprocessing 子进程准备错误而不可用，不用于支持根因；另以独立文件准备的重复软件测试核对，不冒充实现者的压力证据。

当前修复只对 WAL/SHM 的 nlink=0 做一次有限重读，重新检查所有拒绝条件；主数据库、symlink、hardlink、wrong owner、group-write 仍拒绝。独立全量修复后 pytest 实际退出 0：297 passed、0 failed、0 skipped；包含确定性辅助文件瞬态与拒绝不安全替换回归。另独立重复 recovery/software_jobs 十二轮，每轮 17 passed、退出 0；这组 tracing 没有捕获原瞬态，不能把未复现写为原压力复现证据。

## 实际检查命令与结果

| 实际命令/探针 | 退出码 | 观测与范围 |
|---|---:|---|
| `.venv/bin/python -m pytest tests/test_docker_executor.py tests/test_docker_offline.py tests/test_software_jobs.py tests/test_software_api.py tests/test_software_import_api.py tests/test_artifacts.py tests/test_state_paths.py tests/test_runtime.py tests/test_security.py tests/test_ros_probe.py -q` | 0 | 186 passed / 0 failed / 0 skipped，6.81s；已有软件用例。首次运行时尚未覆盖本次新发现的四项问题 |
| 独立 duplicate 边界探针（实际 SQLite/worker/lock） | 0 | 修复前如实观测 2 套 running；退出 0 只表示探针运行，不表示安全断言通过 |
| 独立 group-writable assets 探针 | 0 | 修复前如实观测 `0664` JS 被接受；未启动服务 |
| 独立 CLI MOCK 子进程探针 | 0 | 修复前部署返回 PLANNED，之后 INTERRUPTED；未运行真实容器 |
| `.venv/bin/python work/m3-review-probes.py`（修复后） | 0 | duplicate 被阻塞、group-writable assets 被拒、CLI 子进程实际完成；三个原探针均闭合 |
| `npm run test -- --run`（frontend） | 0 | 29 passed / 0 failed / 0 skipped，2 files，1.89s；含断连和超过五秒无新观测的 UNKNOWN 回归 |
| `.venv/bin/python -m pytest -q`（辅助文件瞬态修复前） | 1 | 289 passed / 3 failed / 0 skipped，59.01s；实际 pytest 退出码，外层日志收集脚本退出 0 不替代它 |
| `.venv/bin/python -m pytest -q`（辅助文件瞬态修复后） | 0 | 297 passed / 0 failed / 0 skipped，60.98s；独立全套软件回归，不包含真实容器或真机 |
| `.venv/bin/python work/m3-state-race-probe.py` | 0 | 正确独立脚本的 recovery/software_jobs 重复十二轮，每轮 17 passed；没有抓到 unsafe metadata，未编造瞬态复现 |
| `.venv/bin/ruff check src tests scripts` | 0 | All checks passed；独立当前工作树运行 |
| `.venv/bin/mypy src` | 0 | no issues found in 23 source files；独立当前工作树运行 |
| `.venv/bin/python work/m3-artifact-audit.py`（已逐项复核广谱命中后） | 0 | 2,347 个运行包 payload 记录全部匹配；0 当前源/资源不一致、0 结构问题、0 真实凭据/本机私人路径发现 |
| ROS 外层清单与内部 OCI 纯文件验证探针 | 0 | 外层摘要/sidecar、2 payload、实际 OCI graph 校验通过；RefuseDocker 客户端强制 Docker 调用为 0 |

重复资源探针第一次因 macOS 系统临时目录的 `/var` 链接祖先被安全校验拒绝，退出 1，尚未进入被审代码；将自建临时目录 resolve 到实际路径后完成复现。该准备错误不计产品通过或缺陷。

## 正式工件与未验证范围

- 离线外层只接受可信摘要、严格清单及固定 payload，拒绝路径穿越、链接/特殊成员、重复与容量超限；私有暂存后再次核摘要、原子无覆盖发布。Docker save/OCI 验证固定镜像身份、blob 摘要、架构/来源、无覆盖用户 tag，之后才受限 Docker load；不会执行归档脚本。
- 初次查看 pyproject 时 wheel 没有带构建/离线锁，已通知集成；当前已 force-include `docs/build`。实际便携包内的项目 Python 与全部打包资源逐字匹配当前源树，构建/离线锁包含在内，不能只据声明判 PASS。
- 已独立读取 software 成功/失败、MOCK 成功/失败、软件断连注入、镜像导入与报告运行 PNG：software/真实 Docker-ROS 与 MOCK 标识分离，真机始终 UNKNOWN/null，运动未启用；断连没有继续显示当前通信正常。首次隐私扫描覆盖当时 199 个 Git 工作文件（含未跟踪报告），凭据候选及个人路径/姓名均为 0；随机字符串命中人工核对为来源 URL、上游来源条目及许可证文件名。候选工件的独立扫描另见下项。
- 本报告首次完稿后、加入阶段总结与交付证据目录之前的 Git 工作文件复扫退出 0：当时 198 文件，0 凭据/个人路径/姓名发现。199/198 均为各次审查快照数量，不代表后续增加文档后的最终文件总数；工作目录私有原始日志未纳入发行内容。
- 后续独立核对 `reports/evidence/m3/INDEX.json` 与 51 份交付证据：实际 payload 文件集合精确匹配，51 份原始 SHA/大小与私有来源一致，51 份交付 SHA/大小与实际副本一致；19 份为去敏后不同摘要、32 份未修改，`redacted_copy` 标志全部正确。交付副本扫描没有凭据或私人路径命中；6 个随机字符串候选是 pytest 名称，44 个 IPv4-like 候选全部是软件包版本字段，没有把版本号当作 IP 删除。该复核只读取与比对文件，没有重新运行功能测试。
- 最后文档一致性复核覆盖 M3-summary、M3-review、Mac 实施计划和证据 README；四份文档扫描退出 0，无凭据/私人路径发现。总结中的 CLI 写法已修为先保存计划、再按 PLAN_ID 与 request-key 执行，实施计划明确当前只接受 local_build/d1env/ros-probe；registry 未实施。完整 M3、真实 API 硬中断恢复、Ubuntu/空 daemon、签名/许可和真机的 NOT_RUN/blocked 与实际证据一致；未为文档整理再次运行功能测试。
- 实际运行包 `outputs/D1Env-M3/D1Env-0.2.0-macos-aarch64.tar.gz` SHA-256 为 `d5befe4ba377dd4cf4708e1f1297aa5d23624b14d82f1e57588795f0f2ce84f4`，校验旁文件与读取前后摘要一致；其中记录的项目 wheel SHA-256 为 `efc0464d4bd7bbaa28281ec37d6ce4f1e1a2eee4de0b46914ce7b82c72a0bb5d`。2,347 个 payload 的路径集合、文件/链接类型、大小、SHA-256、mode 与实际归档全部匹配；归档没有重复/特殊成员/包外链接，uid/gid/name/mtime 已规范化。启动脚本不要求终端用户安装 Node/uv，Mac `.command` 已包含。
- 便携包的广谱扫描第一次退出 1，表示需要人工分类命中，未据此编造凭据泄露。44 条已核对为上游公开 Python/Tcl 构建配置、公开 wheel SBOM、FastAPI/Pydantic/Tcl 文档示例；三份运行时构建配置逐字与官方下载归档相同，Pydantic 文档逐字与锁定开发依赖相同。最终扫描退出 0；没有匹配到本机开发者姓名/个人工作路径或真实凭据。保留这些上游来源/许可材料，所以没有宣称包内“没有任何绝对路径”。启发式扫描与已知本机标识扫描不构成对所有编码、所有未知凭据的形式证明。
- 随包 ROS 数据归档 `outputs/D1Env-M3/d1env-ros-probe-m3-aarch64.tar` SHA-256 为 `8da67f547b7885be741f8fbf0b2fd06f989cec0e2b7ed41d4a24c2adaf2414df`，大小 140,574,720，旁文件一致；外层仅清单与两份固定普通 payload（0600），内部 OCI graph 按生产验证器纯文件校验通过。没有运行镜像或 SDK；没有对全部解压镜像层做逐个可执行二进制审计。
- Python 原官方下载归档大小/SHA 已独立与 `PYTHON_RUNTIME_LOCK.json` 核对一致；候选包 provenance 明确 `verified`，并保留 CPython 源码提交 null、库许可完整性 blocked、`signed_release=false`、`linux_fresh_vm_verified=false`、`robot_verified=false`。运行时来源提升没有被当作签名、许可或其他平台验收通过。
- Mac Docker Desktop 的真实 ROS 生命周期不等于 Ubuntu 原生或干净 VM 验证；A16、Intel/旧版 Mac、运行时附带库的完整许可、签名和真机仍应按实际取得情况记录 NOT_RUN/blocked。此次独立审查不覆盖未来生成的其他 wheel/source ZIP，也没有重跑实现者的真实 Docker/浏览器操作。

最终轴内计数：Standards 1 项已修复；Spec 4 项已修复。已审软件与上述本机候选工件没有剩余已知阻断；正式分发条件、Ubuntu 全新主机、其他 CPU、硬件与运动能力不在通过范围内。
