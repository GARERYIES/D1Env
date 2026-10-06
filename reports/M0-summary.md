# M0 来源与静态审计报告

日期：2026-10-06。范围：Foundation Task 0，静态源码与 SDK 文件元数据；未部署软件环境、未连接机器人。

## 交付变更

- 新增 `docs/research/UPSTREAM_LOCK.json`：五个必需仓库及一个 SLAM 候选的真实完整 commit SHA、83 个实际文件 SHA-256、许可证、tag/release 查询、10 个 SDK 二进制静态元数据和未取得字段原因。
- 新增 `schemas/upstream-lock.schema.json`：拒绝未注明原因的 null、全零 SHA/摘要、路径穿越、任意执行字段和生产可用性误报。
- 向 `docs/research/SOURCE_AUDIT.md` 追加本次附录，保留原始调研文字；将新发现定位到锁定版本的具体文件/行。
- 原始命令、输出、HTTP 失败及静态检查均保存在 `work/evidence/task0*`；参考 checkout 在 `work/upstream/`，不运行上游代码、不放入产品发行包。

## 执行环境

实际探针：macOS 26.6.2（25G83），arm64；Python 3.12.0；Apple Git 2.39.5；预先可用 jsonschema 4.21.1；系统 `file` 与 Apple LLVM 16 `objdump`。这些是审计开发机信息，不是 SDK 支持平台声明。环境命令/退出码见 `work/evidence/task0-environment-commands.jsonl`。

| 仓库 | 完整 commit SHA | 文件哈希数 | 状态 |
|---|---|---:|---|
| ioenv_cli | `ec1f8354095de91a234dc31a9213ee1a410b5cc9` | 8 | 静态文件取得；MIT |
| humanoid_controller | `2f94ff0ebd072e255d90bbbb2122d0f1a622a0b3` | 8 | 静态文件取得；MIT |
| robot_hardware_interface | `fbc18ed07a1926a9f8731b182931d17e1217dbd7` | 7 | 静态文件取得；MIT |
| agibot_D1_Edu-Ultra | `b5fe0a86094507238944ad118721376a98615ac0` | 27 | 静态文件取得；BSD-3-Clause；SDK 语义版本未验证 |
| Agibot_D1_MaxPro | `7828aef8238388c11267e56d5e44bac9f6dd2eb4` | 29 | 静态文件取得；仓库级许可及 SDK 语义版本未验证 |
| slam_toolbox，humble | `dccc5d1fd2b5007098f4050e681d20da37ef183f` | 4 | 候选静态文件取得；未集成 |

每个 SHA 都来自实际 `git rev-parse HEAD`。采用 `git clone --depth 1 --filter=blob:none --no-checkout` 后逐项 sparse checkout；未递归初始化子模块。Git 网络命令限定 45 秒并设置低速超时，HTTPS 元数据请求限定 25 秒，未关闭 TLS 校验。

## 实际验证与命令证据

| 命令/检查 | 实际结果 | 退出码 | 原始证据 |
|---|---|---:|---|
| `python3 work/evidence/task0_validate.py`，实现前 | FAIL：schema 文件缺失，保存真实 RED | 1 | `work/evidence/task0-validation-commands.jsonl` 首条 |
| `python3 work/evidence/task0_retrieve.py` | 六仓 clone、rev-parse、tree、tags 查询成功 | 0 | `task0-retrieval-results.json`、每仓 `task0-*-commands.jsonl` |
| `python3 work/evidence/task0_checkout.py` | 六仓 sparse 文本 checkout 成功；八次 Python HTTPS 元数据请求因本地证书链失败 | 0（脚本）；请求各为 1 | `task0-checkout-results.json`、`task0-http-commands.jsonl` |
| `python3 work/evidence/task0_http_retry.py` | 系统 curl 正常 TLS 校验取得八个 API 响应，均 HTTP 200 | 0；curl 各为 0 | `task0-http-retry-results.json`、`task0-curl-commands.jsonl` |
| `python3 work/evidence/task0_binary_static.py` | 10 库，实际 6,658,920 字节，Git blob 身份/大小核对；10 次 file＋10 次 objdump 成功 | 0；各为 0 | `task0-binary-summary.json`、`task0-binary-commands.jsonl`、两仓 `task0-*-binary-results.json` |
| `python3 work/evidence/task0_lock.py` | 写入六仓、83 个实际 SHA-256 与 10 库元数据 | 0 | `task0-file-hashes.json`、UPSTREAM_LOCK.json |
| `python3 work/evidence/task0_validate.py`，实现后 | PASS：schema＋83 哈希重算；8 个负向用例全部被拒绝 | 0 | `task0-validation-commands.jsonl` 后续条目 |
| `python3 work/evidence/task0_source_review.py` | 已读文件/行的定点证据，避免抄入厂商示例网络口令 | 0 | `task0-source-review-commands.jsonl` |

最终验证输出为：`PASS schema and lock; 6 repositories; 83 recomputed file SHA-256 hashes; 8 negative cases rejected`。负向用例为全零 commit、占位文件哈希、null commit 无原因、绝对路径、父目录穿越、额外 shell 字段、生产可用性误报、未知 SDK 版本无原因。此处是来源锁/元数据验证，不声称 pytest、SDK、Docker 或真机测试通过。

首次 Python HTTPS 失败为 `CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`，原始失败未删；后续系统 curl 使用其正常证书链成功恢复。未使用 `-k`、未更改证书配置、未关闭安全校验。五个必需仓库的 Git tags 与 GitHub releases 结果均为空；SLAM 候选实际取得 52 个 releases。

## 已验证范围和架构结论

验收 A01：**PASS**，具备六仓真实 SHA、实际文件哈希、缺失字段的具体原因，并通过 schema 和负向验证。所有真实 Profile 保持 not_implemented；此 PASS 不能用于 A13–A24。

IOENV 提供环境/镜像/容器入口，后续机器人业务仍由独立 launch 与硬件插件承担。锁定版本的 G1/X2/PM01 插件没有 D1；采用独立的严格 Profile 引擎和分型号 D1 高层适配器的设计继续成立。IOENV 的 shell 配置、host 网络、整个 /dev、X11 宽授权、privileged 和 root/password SSH 不进入本项目默认执行路径。

静态 `.so` 架构与目录声明一致；Edu Python 扩展确实依赖 CPython 3.10 共享库。实际 ELF ABI 符号版本已逐库记录，但未在任何 Linux 运行时加载。完整 API 文档补充了厂商声明的部分单位、轴向和关节顺序；新鲜度、时钟、重置和异常行为仍不足以证明真实遥测契约。详见 SOURCE_AUDIT 第 7 节的具体文件/行。

## 未验证与阻塞

| 项目 | 状态/原因 | 下一步 |
|---|---|---|
| SDK 确切语义版本/固件对应 | 未验证；全部 `sdk_version=null`，目录名及 README 更新日志不足以绑定确切二进制 | 取得厂商版本/工件清单与准确机器人身份，再进行独立只读候选验证 |
| MaxPro SDK 再分发许可 | 阻塞；完整 Git 树未见仓库级 LICENSE/COPYING | 厂商明确许可；第三方 nlohmann 的 MIT 不能替代 SDK 许可 |
| 全部传递依赖许可证/SBOM | 未完成；仅已选源码/库静态检查 | 后续构建阶段逐项记录来源与许可 |
| IOENV 镜像 digest/构建全链 | 未取得；本轮不拉取容器镜像 | M3 自有 Dockerfile、真实 digest、CI/构建证据 |
| Edu 子仓文档 | 未取得；`docs/D1_Edu-Ultra` gitlink 未初始化 | 若后续依赖子仓，另固定地址/提交并审计 |
| 真实 Docker 生命周期 | NOT_RUN；不属于 M0 且本轮禁止创建/停止容器 | M3 独立轮次 |
| SDK 编译/加载/API 调用 | NOT_RUN；当前 Mac 是审计机，任务禁止执行 SDK/demo | M4 准确组合与现场只读授权 |
| 真实机器人/网络/运动/固件 | NOT_RUN；无机器人连接与现场安全证据 | 以后按现场清单独立取得；软件停止不视为硬件急停 |

## 截图来源和下一轮入口

本次没有截图；没有 MOCK、真实 Docker 或真机运行截图，静态文本证据没有被包装成运行截图。

M0 固定 `scope=static_source_audit`、`production_usable=false`。可以继续本轮 Task 1 的严格模型、来源化候选 Profile 与 MOCK 软件功能；真实 SDK 安装仍应被缺失工件、版本/许可和未实施适配器阻塞。后续不以本报告越过 M3/M4 门槛，不自动推送或发布镜像。
