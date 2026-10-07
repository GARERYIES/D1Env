# M3 补充交付：首次运行环境准备（0.3.0）

2026-10-07。本轮根据用户“补上”实现此前确认的首次准备流程，沿用 IOENV 环境定义、容器生命周期、独立业务启动分层；未扩展到 SDK 或机器人。源码提交：`c4bd2f9094fc7f8340b7e7c7653de25457c20714`，本地 `codex/m3-runtime-setup`。旧 M0–M2、0.2.0 M3包保留，没有推送或发布。

## 用户现在能做什么

Mac Apple Silicon 上解压完整版，双击 `D1Env.command`，默认进入中文 MOCK 五步向导。选择真实软件测试后，第三步点击“准备运行环境”：复用经过核验的本机 Docker；缺少时先等待用户明确确认官方许可，再固定下载、校验、受控原生安装、启动和有限等待，最后自动准备内置 ROS 镜像。许可和系统权限在明确提示与原生窗口中确认，不收集系统密码。

环境准备成功只表示 `runtime_environment`，继续预览并启动 ROS 软件测试才检查 CPU ROS 通信。所有 D1 型号仍禁用，真机遥测 UNKNOWN/null，运动未启用。界面、CLI、API共用服务边界；Mac候选之外的平台无法通过直接准备API绕过限制。

## 实现与上游对应

| IOENV参考 | D1Env改造 | 证据 |
|---|---|---|
| `resolve_environment()`、数据与环境拆分 | 严格来源锁/固定平台，准备任务与业务计划独立 | 原蓝图/新实施计划、严格API/平台负例 |
| `docker_pull()`、缓存 | 官方固定Desktop URL/大小/SHA；TLS/跳转拒绝；read1/整体1800s门槛；损坏缓存、取消片段不晋升 | 官方完整DMG只读核验；下载28项假HTTP/文件测试 |
| 容器/工作目录复用 | 持久任务、请求键、跨进程租约、恢复、取消；只复用/启动已核本机入口 | 真实已有Docker/镜像UI复用，重复点击、恢复及竞态回归 |
| CLI入口/首次环境体验 | 内置运行时、官方签名CLI、固定用户Unix socket、自动配套ROS包 | 0.3.0完整版迁移启动/2356entry哈希；实际新入口只读核验 |
| 原`run`进入shell、业务另由launch启动 | 准备环境、ROS软件就绪、D1支持分别判断 | runtime_scope、ROS软件故障、UNKNOWN/过期数据与禁用运动审查 |

参考固定 `ioenv_cli` 提交 `ec1f8354095de91a234dc31a9213ee1a410b5cc9`，MIT；未执行其脚本或照搬 privileged/host网络/整个/dev/X11宽泛授权。详见 `docs/IOENV_BLUEPRINT.md`、`docs/superpowers/plans/2026-10-07-runtime-setup.md`。

## 真实命令、退出码与范围

工作目录为项目根；前端命令在 `frontend/`。完整原始选定日志位于 `reports/evidence/m3-setup/`，保留失败历史，未将跳过计为通过。

| 命令 | 退出码 | 通过/失败/跳过与含义 | 日志 |
|---|---:|---|---|
| `D1ENV_RELEASE_WHEEL=<0.3.0 wheel绝对路径> .venv/bin/python -m pytest --tb=short -q` | 0 | Python3.12：467/0/0，69.40s | `python312-native-handoff-final.log` |
| 同一工件，`work/venv310/bin/python -m pytest --tb=short -q` | 0 | Python3.10：467/0/0，68.61s；是同一套467案例，不能加成934个不同案例 | `python310-native-handoff-final.log` |
| `.venv/bin/ruff check src/d1env tests scripts/build-release.py` | 0 | 静态检查通过 | `native-handoff-ruff.log` |
| `.venv/bin/mypy src/d1env scripts/build-release.py` | 0 | 30source files，无错误 | `native-handoff-mypy.log` |
| `npm test -- --run` | 0 | 4文件，55/0/0 | `ui-all-final.log` |
| `npm run build` | 0 | 中文实际产物编译通过 | `ui-actual-final-build.log` |
| `D1ENV_E2E_SOFTWARE=1 D1ENV_E2E_TOKEN_FILE=<私有0600文件> D1ENV_E2E_URL=http://127.0.0.1:18766 npx playwright test` | 0 | 修补前真实源码API+浏览器：2/0/0；本机准备复用、ROS成功/故障/停止/报告、MOCK成功/故障/刷新/防注入 | `ui-e2e-final.log` |
| 同一命令，端口18767，使用完整发行包内Python/已安装wheel提供API | 0 | 实际发行包内Python3.10/wheel/API+浏览器：2/0/0，自动准备复用和软件/MOCK全流程，约1.3m | `ui-e2e-native-handoff-packaged.log` |
| `uv build --offline --wheel --out-dir work/m3-setup-dist` | 0 | 最终0.3.0 wheel | `wheel-native-handoff-build.log` |
| 下列完整版构建命令 | 0 | 完整运行时+固定ROS包，非assets-only | `portable-native-handoff-build.log` |
| `.venv/bin/python work/setup-evidence/portable-native-handoff-smoke.py` | 0 | 实际归档移动/PATH空CLI与启动、HTML/JS、401/403、2356entry哈希、来源锁、ROS摘要、所有Python源与wheel逐字节匹配 | `portable-native-handoff-smoke.json` |
| 官方固定DMG完整下载、摘要、`hdiutil verify`、只读挂载、显式TeamID `codesign --deep --strict`、Gatekeeper、DMG stapler、本次卸载 | 全部0 | 575775824bytes，SHA一致；来源与签名只读核验，不是安装或启动通过 | `docker-dmg-readonly-results.json`及来源文件索引 |
| 实际官方绝对CLI入口核验+固定用户Unix socket `docker info` | 0 | 冷签名核验8.6077s，Docker Linux/aarch64 29.6.1；未启动/停止daemon | `actual-desktop-entry.json` |
| 来源与最终包UI轮次前后受限只读Docker资源盘点 | 0 | 12images/10既有containers/6networks所有ID保持，测试临时资源已清理 | `docker-inventory-source-e2e-comparison.json`、`docker-inventory-native-handoff-before.json`/`after.json`与最终`cleanup-final.json` |

```sh
.venv/bin/python scripts/build-release.py --portable \
  --runtime work/python/official-20260610/python \
  --runtime-source-archive work/python/cpython-3.10.20-20260610-official.tar.gz \
  --runtime-provenance-json docs/build/PYTHON_RUNTIME_LOCK.json \
  --wheel work/m3-setup-dist/d1env-0.3.0-py3-none-any.whl \
  --requirements work/m3-runtime-requirements.txt \
  --platform macos --architecture aarch64 \
  --ros-bundle outputs/D1Env-M3/d1env-ros-probe-m3-aarch64.tar \
  --output outputs/D1Env-M3-Setup/D1Env-0.3.0-macos-aarch64.tar.gz
```

初次冻结和打包后，最终只读交付检查又发现原生安装窗口交接与校验盘清理的顺序风险。新增顺序/卸载失败/卸载后取消回归，先记录3FAIL/14PASS（exit1），修复后17PASS（exit0）；最后源码固定为上述c4bd2f9，重新构建wheel/完整包、双Python全套、搬迁烟测和包内实际浏览器流程。原归档保留在忽略目录 `work/m3-setup-before-native-handoff.tar.gz`，更早样包另存；最终交付只认下述摘要。Python全套原有release兼容测试仍保留部分0.2.0 legacy输入；本轮另独立核验实际0.3.0完整包，不将旧包测试当作新包全部证明。

## TDD与真实失败记录

最初下载/安装/任务/API/UI/ROS配套打包均先出现可失败测试，再最小实现。新增复审回归覆盖：旧观测覆盖新false/null、WAITING_USER取消交接、任务JSON原子替换、内部应用权限/签名变化、直接API平台绕过、PATH/default入口绕过、自动导入取消传播、下载deadline/进度与签名冷启动超时。独立审查发现后逐项RED→GREEN，最终无未闭合代码发现。原生安装交接先完成本任务只读卸载，再请求打开原生窗口，卸载失败或取消不会调用open；仅软件夹具证明调用顺序，没有升级为新机安装证据。

保留以下非通过记录：一次旧进程边界测试在同时开发负载下超时（退出1，66PASS/1FAIL），单项重跑0后最终完整套件均0；AF_UNIX夹具路径过长一次失败；测试构造函数参数错误导致5FAIL；API/UI契约、多个安全回归的预期RED；Ruff排序/B018与mypy类型错误后修复；辅助脚本曾指向错误工作目录/manifest名称，未记成功，纠正后完成归档核验。独立审查使用默认系统Python时缺typer，退出2/3个collection errors；改用已有完整锁定测试环境后465PASS。详见审查报告和失败日志，源码回归与环境/辅助脚本错误分开记录。

## 发行与截图

- 完整包：`outputs/D1Env-M3-Setup/D1Env-0.3.0-macos-aarch64.tar.gz`，167626300bytes，SHA256 `e2866d49ff3e795ede21f6350a8edca97987e37fc26320fb542fb8859daff6ad`。
- 本机已解压入口：`outputs/D1Env-M3-Setup/ready/D1Env-0.3.0-macos-aarch64/D1Env.command`，也可运行包内 `./d1env.sh`。首次默认MOCK，Chrome新窗口；端口冲突会明确失败，不停止已有程序。
- ROS配套tar固定140574720bytes，SHA `8da67f547b7885be741f8fbf0b2fd06f989cec0e2b7ed41d4a24c2adaf2414df`；自动打包到 `_assets/bundles`，不会由用户自由选择镜像或网址。
- Docker Desktop官方4.80.0/build232116/arm64 DMG不随D1Env分发；这是固定候选，不声明最新版本。对应专有源码提交保持 `null / blocked`。完整字节/SHA/应用签名/来源许可证入口有实际证据，安装许可适用性仍由用户确认。
- 截图来自上述实际headless浏览器运行，trace/video和自动失败截图关闭，认证完成并移除fragment后取图；未生成/拼接界面。最终完整发行包服务截图在 `reports/screenshots/m3-setup/`；最终运行环境准备截图：`m3-ui-runtime-prepare-success.png`，MOCK成功/故障：`m3-ui-mock-success.png`、`m3-ui-mock-failure.png`，软件故障和网络故障注入分别记录；修补前源码服务复核截图另存 `reports/screenshots/m3-setup-source/`；MOCK成功/故障图保留MOCK标识，真实Docker/ROS图保留软件范围和未接真机标识。
- 启动方法见输出目录 `START-HERE.md`；独立误报成功、注入、权限、重复/恢复/取消审查见 `reports/M3-setup-review.md`。

## 未验证与下一轮入口

| 范围 | 当前状态 |
|---|---|
| 已有Docker+固定ROS镜像的Mac软件准备复用 | 实际UI已验证；native安装/start阶段未执行 |
| 官方DMG下载/完整摘要/签名/Gatekeeper/只读挂卸 | 已验证；没有执行DMG安装或厂商机器人代码 |
| 全新Mac真实安装、Docker许可、系统授权和启动；空daemon首次自动ROS导入 | NOT_RUN；假执行器测试不替代此范围 |
| Linux新机/完整Ubuntu发行、IntelMac、旧Mac版本 | NOT_RUN，自动准备入口禁用 |
| D1准确型号/SDK版本/固件/许可证及硬件兼容 | blocked / not_implemented；SDK不运行，遥测UNKNOWN |
| D1传感器、建图、导航、arm/运动及现场停止机制 | not_implemented；不连接机器人、不改网络/驱动/固件、不发送运动指令 |
| 本程序正式签名/公证、浏览器下载隔离/Gatekeeper、全部内置动态库许可证 | NOT_RUN / blocked，不能称正式生产发行 |
| 下载最坏网络时延 | 同步连接/单次read1依赖15s socket timeout；1800s门槛在调用返回时检查，不宣称毫秒级取消或所有恶意慢速HTTP头已测试 |

下一轮先验收隔离的新Mac真实首次安装和Linux正式目标发行；机器人工程仍按准确型号与厂商版本证据单独进入M4，只读候选不自动变成真机支持。本轮到此停止，不实现后续机器人功能。
