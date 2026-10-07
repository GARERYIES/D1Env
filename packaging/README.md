# M3 发行资源与离线数据基础

## 0.3.0 当前候选

当前完整 Mac 候选在运行时、依赖和界面之外，包含受信 ROS 数据包；向导提供“准备运行环境”，自动核验并复用 Docker/镜像，缺少 Docker 时使用固定官方来源并衔接原生安装确认。实际包摘要与验证范围见 [M3-setup-summary](../reports/M3-setup-summary.md)，用户入口见 [Start Here](../START_HERE.md)。全新 Mac 安装、Linux、发行签名及完整动态库许可仍未验收。

构建完整包需在下述便携构建参数中提供 `--ros-bundle`，输入固定 ROS 工件，并使用实际 0.3.0 wheel。构建材料不随 GitHub 源码交付；具体命令、来源锁和工件摘要保存在阶段报告。Docker 专有安装包不随 D1Env 再分发。

## 资源契约与 0.2.0 历史构建说明

本目录记录真实资源打包边界，不代表已交付 Ubuntu 自包含安装器。Python wheel 必须随包包含 `d1env/_assets/`：`profiles/*.yaml`、`frontend/dist/` 与 `docs/research/UPSTREAM_LOCK.json`；第三方版权声明也应随包保留。Node 仅用于构建前端，不是安装后运行依赖。

运行时资源采用同构布局。冻结应用从 `sys._MEIPASS/assets` 读取；普通安装从 `d1env/_assets` 读取；开发模式可以显式提供源码根目录。状态默认写当前用户的 `~/Library/Application Support/D1Env`（Mac）或 `${XDG_STATE_HOME:-~/.local/state}/d1env`（Linux），与只读安装目录分开。`D1ENV_ASSETS_DIR`、`D1ENV_STATE_DIR` 仅作为可信本地启动参数，不接入 Web 请求。

可实际生成确定性资源数据包：

```sh
python scripts/build-release.py --output work/d1env-assets.zip
```

命令不会调用 Node、Docker、SDK 或系统安装器；前端需要已由研发构建。它只打包资源和清单，输出实际 SHA-256、大小和 `self_contained_runtime=false`。数据包不是可执行发行包，也不附带 Python 或 Linux 动态库。构建同一资源会得到同一归档摘要；输出文件已存在时拒绝覆盖。

离线 API 为 `validate_offline_archive(path, expected_sha256, destination)` 和 `import_offline_archive(...)`。可信期望 SHA-256 必须由受信的发行记录明确提供，不能直接信任同一个未知归档附带的散列。API 只接受含 `d1env-offline.json` 的 ZIP/TAR 数据包；所有 payload 文件均列出路径、大小和 SHA-256。

清单格式为 `schema_version=1`、`kind=d1env_data_bundle`、`bundle_id` 与 `files`。每项文件只允许 `path`（必须在 `payload/`）、`size_bytes`、`sha256`。导入拒绝异常路径、链接/特殊文件、重复/大小写冲突、容量超限、额外或缺失文件、摘要不符以及已有目的目录；先完整验证，再写私有暂存目录，不覆盖式原子发布。脚本只作为权限 0600 的数据保存，绝不执行。

Docker save 的 `manifest.json`、镜像层 TAR 和安装器不是这种数据清单。需要专门的可信镜像导入契约才能交给受限 Docker 执行器，不盲目展开其层或执行包内脚本。通用资源数据包 API 供研发使用；本轮 ROS 镜像使用单独的受信导入服务，已接入中文 UI 并在 Mac 实际验证。界面不接受任意资源包、用户期待摘要或安装脚本；空 Docker daemon 与 Ubuntu 的导入仍未验证。

原生便携候选可以包含完整 CPython 运行时、固定且带 SHA-256 的运行依赖、本项目 wheel 和已构建页面。以下是研发构建命令；输入路径必须是已有的完整运行时与真实 wheel，不会安装主机全局依赖：

```sh
python scripts/build-release.py --portable \
  --runtime work/python/official-20260610/python \
  --runtime-source-archive work/python/cpython-3.10.20-20260610-official.tar.gz \
  --runtime-provenance-json docs/build/PYTHON_RUNTIME_LOCK.json \
  --wheel work/m3-dist/d1env-0.2.0-py3-none-any.whl \
  --requirements work/m3-runtime-requirements.txt \
  --platform macos --architecture aarch64 \
  --output work/D1Env-0.2.0-macos-aarch64.tar.gz
```

构建默认使用已有 uv 缓存并禁止网络，重新校验锁定依赖的 hash；缓存不完整时失败，不自动回退到下载。研发首次准备缓存可显式使用 `--allow-downloads`，保留 HTTPS 校验；`--cache-dir` 可选择已有可信缓存。uv 仅用于研发构建，不进入发行运行依赖。构建在新暂存目录复制完整运行时，清除复制品的旧开发依赖，绝不修改输入运行时。发行标识与实际解释器平台/架构不符时直接拒绝，例如 Mac 运行时不能标成 Linux。

Mac 用户解压后双击包内 `D1Env.command`，入口启动中文 MOCK 向导。在向导明确选择真实软件测试后，可选择本轮随包提供的 ROS 镜像文件导入，再预览和部署软件探针。CLI 用户也可在自己的包目录启动：

```sh
./d1env.sh
```

入口默认启动中文 MOCK 向导，并按现有本地启动规则新开 Chrome 窗口；需要本机已有支持的浏览器。`./d1env.sh --help`、`./d1env.sh doctor` 可直接运行。用户无需 Node、uv、系统 Python、ROS 源码编译或 YAML 手工修改。真实软件部署仍需要用户已有且可访问的 Docker/Compose，以及与平台匹配的可信 ROS 镜像；机器人状态保留 UNKNOWN。

`D1ENV-RELEASE.json` 记录实际 Python 版本、CPU/系统、运行依赖版本、输入 wheel/requirements/原运行时树摘要和包内文件摘要。发布记录还必须提供完整 TAR.gz 的实际 SHA-256；文件清单校验不替代可信发行摘要。Mac 当前验证包括无开发 PATH 的搬迁启动、只读 doctor、实际回环 HTTP 页面/静态文件和 API 安全边界。这是本机软件候选证据，未验证 Mac 下载隔离属性、签名/公证、其他 Mac 系统或全新 Ubuntu 安装。

官方来源记录见 `docs/build/PYTHON_RUNTIME_LOCK.json`，包含实际 GitHub 下载 URL、发布归档 SHA-256/大小、完整运行时树摘要与 `python-build-standalone` 的实际 tag commit。构建提供来源锁和原下载归档时，在执行解释器前校验归档、来源锁和待复制运行时树一致，之后记为 `runtime_provenance.status=verified`。构建工具提交不等于 CPython 源码提交；后者仍为 null。未提供来源材料的旧本地运行时保留 blocked，不据目录名或 `BUILD` 推断来源。

实际 `lib/python3.10/LICENSE.txt` 随便携包保留；运行时附带动态库的完整许可核对仍为 blocked。当前工件仅供本机候选验证，未签名；下载隔离/Gatekeeper、公证、旧 Mac 版本与 Intel CPU 亦未验证。

后续自包含 Linux 工件必须在准确目标架构的 Linux 环境中构建，纳入实际运行时/依赖与许可、产物摘要和干净 Ubuntu 桌面安装证据。Mac 资源/wheel 测试或容器构建不能替代 A16 全新系统安装与 A17 已有系统兼容验收。
