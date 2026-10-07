# 原生安装窗口交接顺序：独立复审

日期：2026-10-07。审查基点为 `2760e1685d30c18b3b29d6962b7c70069ec433e4`；本次实际审查提交为 `c4bd2f9094fc7f8340b7e7c7653de25457c20714`，提交说明 `fix: release verification mount before native installer handoff`。仅检查 `src/d1env/setup/installer.py` 与 `tests/test_setup_installer.py` 的最小差异，未编辑产品源码。

## Standards

0 项发现。不可写 Applications 分支保存原生交接结果；本任务的只读验证 mount 在 finally 中完成卸载并检查 returncode/timed_out，成功后才执行固定 `/usr/bin/open <本任务已核验DMG>`。卸载失败或超时抛出 `INSTALLER_UNMOUNT_FAILED`，不会打开窗口。交接之后不再执行卸载，因此没有继续清理原生窗口可能使用的卷。

`_run` 在调用 runner 前后均检查取消。复制、已有应用保护和本任务 staging 清理的原有边界保留；没有新增 sudo、任意命令、许可自动接受或用户资源删除。

## Spec

0 项发现。交接仍返回 `installed=false / native_setup_required=true`；`open` 返回成功不表示应用已安装、系统授权已完成或 Docker 已就绪。测试覆盖“先成功卸载、后打开、打开后无卸载”“卸载失败不得打开”“卸载后收到取消不得打开”。卸载超时的禁止交接由源码同一失败条件覆盖，本轮未新增或独立执行专门的超时夹具。

Standards 与 Spec 两个只读交叉审查者分别检查上述差异，均报告 0 项发现；交叉审查者未运行测试或原生/Docker 操作。主复审实际重新运行以下安装器单项：

```sh
work/venv310/bin/python -m pytest -q tests/test_setup_installer.py
```

- 退出码：0。
- 必要输出：`17 passed in 0.15s`。
- 通过/失败/跳过：17/0/0。
- 范围：已有软件夹具与模拟原生 runner；没有执行真实 DMG 安装、挂载/卸载、打开 Docker 原生窗口或 Docker daemon 操作。

本轮主复审未重现修复前 RED；RED→GREEN 时序属于主执行者已有日志，应另行保留，不能仅凭最终 diff 或本次 GREEN 重跑称独立复现了 RED。

此前交付报告/归档的源码冻结点为 `2760e1685d30c18b3b29d6962b7c70069ec433e4`。主执行者已更新到本次提交与新包；下述复审实际读取新归档，没有把此前归档核验直接沿用为新提交归档核验。

## 新归档与本轮界面证据增补

独立实际核对 `outputs/D1Env-M3-Setup/D1Env-0.3.0-macos-aarch64.tar.gz`：167626300 bytes；SHA-256 `e2866d49ff3e795ede21f6350a8edca97987e37fc26320fb542fb8859daff6ad`；实际 HEAD 为 `c4bd2f9094fc7f8340b7e7c7653de25457c20714`。Tar 有 2574 成员，其中 2348 普通文件、9 个符号链接；发行 manifest 保留 `signed_release=false`、`linux_fresh_vm_verified=false`、`robot_verified=false`。内置 ROS 记录为 140574720 bytes、SHA-256 `8da67f547b7885be741f8fbf0b2fd06f989cec0e2b7ed41d4a24c2adaf2414df`，架构 aarch64，固定镜像身份未扩展。

归档清单/源码交叉审查实际核对 2356 payload：type、size、SHA、mode 和完整文件集逐项一致，差异为 0。重复成员、非法/绝对/父目录越界路径、越界/悬空/成环链接、硬链接、特殊设备和异常 uid/时间均为 0。当前 `src/d1env` 的 29 个 Python 模块与包内 29 个模块逐字节相同；受信 ROS 包的实际大小/摘要与本地已核验包一致，其 payload/image.tar 与锁中大小/摘要一致，payload/ros-image.json 与锁 manifest 逐字段一致。唯一 mode=0666 的普通文件为包内零字节 site-packages/.lock；旧 0.2.0 归档已有相同元数据，两份 manifest 均准确记录，本轮没有新增权限变化。本次仅静态读包，没有解包执行。

敏感范围交叉审查实际流式读取新 tar：2348 普通文件、214675018 内部字节，其中 1755 个所选文本文件。私有 runtime-setup 状态、SQLite、`.env`、凭据/私钥文件名、Docker DMG/PKG，以及当前开发机准确 home/workspace 字节命中均为 0；高置信 API key、Bearer、私钥块、长敏感字段与 JWT 候选均为 0。本轮独立高熵规则选出 5 项并逐上下文判读：CPython 构建工具元数据 2 项、Pydantic Base64 文档示例 2 项、Pygments Cocoa 公开符号表 1 项。通用 `/Users/` 字节共 150 处，均为第三方轮子上游 CI runner 构建元数据；没有当前用户路径。未读取外部秘密或私有候选表；模式扫描不能证明任意秘密绝不存在。

主复审实际读取 `work/setup-evidence/portable-native-handoff-smoke.json`：执行者记录 exit 0、新 SHA 及 software_tool_candidate 范围。实际读取两份 `python{310,312}-native-handoff-final.log`，分别为 467 PASS/0 FAIL/0 SKIP、68.61s 与 69.40s；这是执行者证据，本次主复审没有重新运行两份完整套件。

主复审实际读取新 `ui-e2e-native-handoff-packaged.log`：`2 passed (1.3m)`。实际查看本轮刷新后的 `reports/screenshots/m3-setup/m3-ui-runtime-prepare-success-viewport.png`，其 SHA-256 为 `404b6b2405bd0502932f5b2bbd4a0d6eeaa5b6197967501d666d58b89d8152de`：可见“真实软件测试·Docker/ROS”、仅验证 CPU ROS 软件通信、未连接真机、仅运行环境已准备、software/待验证、真机 UNKNOWN/null 与运动未启用；未见令牌、密码或用户绝对路径。

实际读取本轮刷新后的准备 proof：来源 actual_local_api_and_browser，scope=runtime_environment，SUCCEEDED/complete；existing_docker_only=true、existing_locked_image_only=true，native_install_or_start_stages=[]；prepare POST=1、continue=0、部署 POST=0，刷新未重复准备；固定镜像 origin=docker/status=reused，真机 UNKNOWN，robot_functions_verified=false。该 E2E 与截图只证明新完整包的已有 Docker/镜像复用及软件流程，仍不证明原生首次安装。

## 保留边界

该修补证明的是软件调用顺序与异常/取消路径，不证明 Finder 的实际复用行为曾被复现，也不保证窗口视觉状态、用户拖拽安装或受保护目录授权成功。真实全新 Mac 首次安装、Docker 许可/系统授权、原生恢复、Linux 与机器人验收继续为 NOT_RUN/未实施；没有因这 17 项软件测试改变证据等级。

本次唯一直接写入文件是本记录；没有修改其他交付报告、推送或发布。
