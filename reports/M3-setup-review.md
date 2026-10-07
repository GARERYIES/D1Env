# M3 补充：首次运行环境准备独立审查

审查日期：2026-10-07。最终产品源码固定点为 `c4bd2f9094fc7f8340b7e7c7653de25457c20714`，由实际 `git rev-parse HEAD` 核对。独立主审依 code-review 的 Standards/Spec 两轴阅读和复现；有空闲代理后增加一名只读 Spec 交叉审查者。最终已发现的代码缺陷均已闭合，软件检查通过；结论限于本轮候选，**不证明新机安装、Linux 或 D1 就绪**。

## 范围与方法

已读 `AGENTS.md`、`README.md`、`docs/IOENV_BLUEPRINT.md`、本轮 `2026-10-07-runtime-setup.md` 和 code-review skill。逐项审查 `src/d1env/setup/`、`docker/endpoint.py`、DockerClient/ProbeRunner、service/runtime API、中文 RuntimeSetupPanel/App、新增测试，以及发行包配套 ROS 工件和资源权限改动。

Standards 轴核查命令/来源白名单、TLS、私有状态、签名缓存、目录权限、原子替换、取消和不覆盖资源。Spec 轴核查环境/镜像/ROS/D1 分层、许可明确确认、MOCK 不触发准备、未知/过期观测、平台门槛和恢复授权。主审没有安装、启动或停止真实 Docker，没有创建、导入或清理容器/镜像，没有调用 SDK 或机器人；仅运行软件夹具、静态读取、单元测试和归档扫描。主审唯一写入文件是本报告。

## 发现与最终闭合

| 重要度 | 初始问题及真实证据 | 最终修复与独立复核 |
|---|---|---|
| P1 | API/UI 契约不一致：后台缺 UI 必需 `evidence`，blocked installer 缺 nullable 字段，真实状态会被前端拒绝。 | `SetupManager.status` 提供完整 host/artifact evidence 和 blocked null 字段；独立读回，最终契约回归及 UI 全套通过。 |
| P1 | `readCurrent` 先读 status=true，随后读到 task=false/null，却把较早 true 覆盖到新任务观测，误显示当前已准备。 | 首读与轮询保守合并两次观测；有 false/null 时不升级为 true。独立读回，两个失效回归及 UI 全套通过。 |
| P1 | 启动前只查 app 根目录；纯假签名夹具中 Contents=0777 仍调用 fake open。夹具只证明权限缺口，未宣称真实签名通过。 | MacInstaller 检查全树 uid/mode/type/nlink、合法内部链接与固定主程序；签名前后元数据一致才允许继续。最终权限/TOCTOU 回归通过；主审实际只读检查当前官方 app 的 706 条目通过。 |
| P2 | 等待状态持久化后、worker 释放 lease 前，一次 cancel 写 marker 后抛 SETUP_BUSY；worker 退出仍 WAITING_USER。主审 barrier 夹具重现。 | 取消请求被接受，worker finally、跨进程有限交接及 startup 持久 marker 恢复落 CANCELLED；license/native_setup 交接回归在最终全套通过。 |
| P2 | GET 打开旧 tasks.json inode 后，本程序正常 os.replace 令旧 fd nlink=0，误报 SETUP_STATE_INVALID。主审 barrier 夹具重现。 | 仅确认旧 fd 原权限安全且当前路径为不同的安全 inode 时有限重读，最多 3 次；拒绝 symlink/hardlink/owner/mode 等异常。11 项确定性边界回归在最终全套通过。 |
| P2 | 自动镜像准备未传取消谓词，现有 ROSImporter 的 copy/load 取消支持未接入；须等导入返回才落终态。 | 任务取消谓词贯穿 manager→service→ROSImageImporter；marker 异常失败关闭，正常取消落 CANCELLED；独立读回，最终取消传递回归通过。 |
| P2 | 未支持的 Intel Mac/Linux/旧 macOS，在已有 Linux/aarch64 Docker 时可通过 API 绕过界面禁用，任务 SUCCEEDED、status 却 supported=false。Spec 交叉夹具实际重现。 | worker 的任何变更前及当前观测都使用同一平台门槛；直接 API 未支持平台 FAILED/UNKNOWN，不调用 image preparation。3 个平台回归在最终全套通过。 |
| P1 | Mac PATH＋legacy socket 分支跳过签名、CLI/目录/端点检查，却 local=true；普通 legacy 文件夹具签名调用次数为 0。 | Mac 已知 Desktop 一律使用核验后的绝对 CLI＋当前用户 Unix socket；未知 PATH CLI 被拒绝，不运行。全树权限/合法内部链接、签名前后指纹一致及冷缓存 RLock 防重复验证；绕过/TOCTOU/并发回归在最终全套通过。 |
| P2 | 首次官方入口同步签名可超过旧 runtime GET 的 5s；来源实际当前 app 入口核验为 8.6077s，健康环境也会被 UI 判请求不可达。 | runtime 读写请求均为有限 90s，初次读取显示签名耗时提示；冷签名仅执行一次，后续每次完整指纹复核。独立代码复核及 deadline/并发回归通过；仍不把冷缓存时间当首次安装验收。 |

增补独立交付检查确认一个P2交接顺序风险：原先不可写Applications分支在open DMG后finally卸载本任务校验卷，无法保证Finder复用卷时窗口仍可用。这是调用顺序判断，未真实复现原生安装。最终改为校验盘卸载成功后才open DMG；卸载失败/超时或取消不打开窗口。三个预期RED修补后通过，独立Python3.10单项17PASS/0FAIL/0SKIP（exit0），增补记录见 `reports/evidence/m3-setup/native-handoff-independent-review.md`。

附带报告文字已修：doctor evidence 采用 `fixed local Unix entry`，不再把实际 `--host` 路径误写为 default context，也不公开用户 socket 绝对路径。初版少数 stat 签名缓存已被全组件 ctime/权限/归属指纹和签名前后检查替换，不能沿用被改变组件的旧签名。

## 实际独立软件检查

| 实际命令/检查 | exit | 通过/失败/跳过 | 范围 |
|---|---:|---|---|
| `python3 -m pytest -q tests/test_docker_endpoint.py tests/test_setup_download.py tests/test_setup_installer.py tests/test_setup_manager.py tests/test_runtime_api.py` | 0 | 100 PASS / 0 FAIL / 0 SKIP；1.07s | 初轮靶向；其后新增缺陷另补回归，不能把初轮计数当最终全套。 |
| stdin Python：WAITING_USER/license barrier 后 cancel | 0 | 成功复现 SETUP_BUSY、退出后 WAITING_USER/marker 存在 | 修复前的纯软件失败证据，不是通过。 |
| stdin Python：GET fd barrier＋本程序正常原子写 | 0 | 成功复现 SETUP_STATE_INVALID；后续读正常 | 修复前，临时自有文件。 |
| stdin Python：fake app Contents=0777 后 start | 0 | fake open 被调用，复现权限缺口 | 修复前，签名/原生调用为 fake；没有修改真实 app。 |
| Spec 交叉审查 stdin 夹具：`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests work/venv310/bin/python -` | 初次 1；修正临时路径后 0 | 初次 STATE_UNSAFE 正确拒绝临时 /var 链接祖先；`.resolve()` 后重现 unsupported false/ready true 及 UNKNOWN 原生等待 | 纯软件；UNKNOWN＋已有 app 在显式 prepare 下 fake start=1，最终 WAITING_USER/null、download/import=0，不判作误绿。 |
| Spec 交叉审查 stdin：PATH＋普通 legacy socket、拒绝 verify_app adapter | 0 | 签名调用 0，local=true，重现入口绕过 | 修复前，仅调用 resolve_endpoint，未执行 CLI。 |
| `cd frontend && npm test -- tests/unit/RuntimeSetup.test.tsx` | 0 | 25 PASS / 0 FAIL / 0 SKIP；1.54s | 独立准备面板复测。 |
| `python3 -m pytest -q`（默认 Python 3.12.0） | 2 | 3 collection ERROR；0.63s；未执行全套 | 默认环境缺 typer；CLI 3 文件无法收集，不计通过或跳过。 |
| `python3 -m pytest --collect-only -q` | 2 | 同 3 collection ERROR | 确认缺 typer 的环境原因，没有安装依赖或隐去失败。 |
| `work/venv310/bin/python -m pytest -q`（实际 Python 3.10.20） | 0 | **465 PASS / 0 FAIL / 0 SKIP；56.12s** | 最后交接顺序修补前的冻结点完整独立软件检查，使用已有完整测试环境。 |
| `cd frontend && npm test` | 0 | **55 PASS / 0 FAIL / 0 SKIP；4 files，2.08s** | 冻结后独立 UI 全套。 |
| stdin Python：`MacInstaller._check_app('/Applications/Docker.app')` | 0 | 权限树检查通过；706 条目 | 实际已有 4.80.0/232116、主程序 com.docker.backend；仅 lstat/plist，无启动、原生程序或权限修改。 |
| stdin Python：交接修补前归档 manifest/hash/path/source 校验 | 0 | 2356 payload 全一致；文件集/源码差异 0 | 归档字节和静态文件检查，没有解包执行。 |
| stdin Python：交接修补前归档高置信凭据模式及文本熵扫描 | 0 | 高置信命中 0；7 个候选均已判读为公开代码/文档常量 | 2348 普通文件、1755 选定文本文件；无敏感值写入输出。 |
| `work/venv310/bin/python -m pytest -q tests/test_setup_installer.py` | 0 | 17 PASS / 0 FAIL / 0 SKIP；0.15s | 最后交接顺序修补的增补独立复跑，仅模拟原生runner。 |
| 增补独立新归档manifest/hash/path/source校验 | 0 | 2356 payload全一致；29个Python模块逐字节一致 | 新167626300bytes归档，完整集/模式/来源锁，无解包执行。 |
| 增补独立新归档敏感范围流式扫描 | 0 | 高置信命中0；5个规则选中的熵候选均属公开内容 | 2348普通文件、1755选定文本；规则与前轮不同，不混同原7候选计数。 |

运行输出仅保留计数、错误码和假夹具权限。探针 exit 0 表示复现脚本完成，不能解释为缺陷已通过。

## 最终发行归档

实际审查 `outputs/D1Env-M3-Setup/D1Env-0.3.0-macos-aarch64.tar.gz`：167,626,300 bytes；SHA-256 `e2866d49ff3e795ede21f6350a8edca97987e37fc26320fb542fb8859daff6ad`。manifest 声明 2356 文件/链接 payload，每项 SHA/大小/模式及完整文件集均独立核对一致，当前 `src/d1env/*.py` 与包内模块逐字节一致。

9 个 Python 运行时符号链接均指向包内存在的普通文件；没有重复成员、绝对名称、父目录越界、特殊设备、硬链接或危险链接。Tar uid/gid 均为 0、owner 名称为空。没有 Docker DMG/pkg、私有 runtime-setup 状态或 jobs.sqlite。内置 ROS 包与既有审定 140,574,720 bytes、`8da67f547b7885be741f8fbf0b2fd06f989cec0e2b7ed41d4a24c2adaf2414df` 一致；没有把 Docker 专有安装器再分发许可当作已取得。

增补复审流式读取新包2348普通文件、1755所选文本，当前开发机准确home/workspace字节及高置信key/Bearer/私钥/长敏感字段/JWT候选命中0。本轮独立规则选出的5个熵候选分别为CPython构建元数据2项、Pydantic Base64示例2项、Cocoa公开符号表1项；通用 `/Users/` 150处均属第三方wheel上游CI构建路径。前轮7候选按原规则另保留，不混同。唯一0666普通文件是零字节site-packages/.lock，原0.2.0已有相同元数据且manifest准确记录，本轮未新增权限变化。原先私有known-secret候选表已不在工作区，故不宣称其精确值重扫完成；扫描不能证明任意秘密绝不存在。

## 实际界面与其他执行者证据

原主审实际查看修补前的准备/MOCK截图，增补复审又实际查看本轮刷新的 `reports/screenshots/m3-setup/m3-ui-runtime-prepare-success-viewport.png`（SHA `404b6b2405bd0502932f5b2bbd4a0d6eeaa5b6197967501d666d58b89d8152de`）；主执行者复核本轮MOCK故障截图。前者可见真实软件范围、只读主机检测、仅运行环境已准备、software/待验证、真机 UNKNOWN/null、运动未启用；后者保留明确 MOCK 水印和演示结果不代表部署/真机的说明。没有可见令牌、用户绝对路径或密码。

实际读取准备 proof JSON：来源 actual_local_api_and_browser，scope=runtime_environment，SUCCEEDED/complete，复用已有 Docker/固定镜像，prepare POST=1、continue=0、部署 POST=0，无安装或启动阶段，刷新不重复准备、真机 UNKNOWN。修补前源码/包装日志及本轮 `ui-e2e-native-handoff-packaged.log` 均实际记录2 passed，范围仅既有Docker/镜像复用与软件测试，审查者没有重新执行E2E。

实际读取修补前 `portable-release-smoke.json` 及修补后 `portable-native-handoff-smoke.json`：执行者记录 exit 0、2356 payload 校验、内置 Python 3.10.20、搬迁后 CLI help、HTML/JS、本机 doctor/真机 UNKNOWN、无会话 401、非可信 Host 403、wheel 源码一致。这是执行者证据，不能写成主审亲自运行了发行程序。

## 保留的未验证/阻塞范围

- **真实首次安装 NOT_RUN**：没有在全新 Mac 执行安装/首次许可/受保护目录授权、下载/安装中途硬退出及真实恢复/挂载清理。假执行器回归、官方 DMG 只读签名、已有 app 权限检查、已有 Docker 复用分别记录，不合并为新装 PASS。
- Linux 新系统、Ubuntu x86_64 runtime、Intel Mac、其他/旧 macOS 实际安装未验收；未支持的准备平台由 API/UI 禁用或 UNKNOWN，MOCK 可继续。
- D1 SDK、真机连接/遥测、驱动/网络/固件与运动未运行、未实现；运行环境准备成功不代表 ROS 消息通过，更不代表 D1 就绪。软件停止不是硬件急停。
- D1Env 下载文件 quarantine/Gatekeeper、发行签名/notarization 未验收；manifest `signed_release=false`、`linux_fresh_vm_verified=false`、`robot_verified=false`。官方 Docker 的签名验证不能当作 D1Env 包签名。
- 完整随包动态库许可证核查仍 blocked。Docker DMG 来源可下载不等于取得再分发授权，最终包没有该 DMG。
- runtime 请求 90s 是有限客户端等待，Docker 子进程 5s 不包含首次系统签名；首次 CLI 入口签名子命令各有 30s 上限，原生安装器的签名子命令各有 90s 上限；下载网络接收 15s、整体 1800s。未宣称这些限时保证任意系统/DNS/磁盘故障下的严格实时终止。

本审查没有发布或推送，不授权实际原生安装、SDK 或硬件操作。后续进入真实首次安装或 Linux 验收须按相应轮次取得具体环境与现场授权。
