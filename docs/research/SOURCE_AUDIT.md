# IOENV 与 D1：源码层调研结论

这是静态阅读结论，不是已经运行成功的复现报告。来源编号对应 [SOURCES.md](SOURCES.md)。

## 1. IOENV 实际分成两层

**环境层**：`ioenv.sh` 注册命令入口；`bin/ioenv` 根据环境名读取 `env.d`，拉取镜像并创建/复用容器。配置包含镜像引用、卷、工作区和可选能力。镜像站由独立配置控制。[S01–S07]

**机器人业务层**：教程在进入容器之后，仍分别调用训练程序与 ROS launch。控制器选择、策略推理和机器人硬件对接并不是 `ioenv run` 自己完成的。[S08–S12]

```text
环境管理：命令入口 → 环境定义 → 镜像获取 → 容器＋持久化目录
                                                    ↓
业务启动：ROS launch → 控制器/状态估计 → 仿真插件或真机硬件插件
```

因此 D1Env 的“一键启动业务”比原 CLI 多一层职责：任务编排＋就绪检查。不能只给原 Bash 套一个按钮，就宣称全流程自动部署。

## 2. 代码中值得参考的设计

| 参考点 | D1Env 的继承方式 |
|---|---|
| 环境由数据描述 | 改为严格校验的 Profile，不执行任意 shell 配置 |
| 开发/仿真/机载环境分开 | 诊断、只读 SDK、建图、导航、未来训练按需分包 |
| 容器和工作目录复用 | 幂等部署，地图、bag 和配置独立持久化 |
| 镜像站可选 | 来源可审查、摘要校验，增加离线导入与缓存 |
| 仿真/真机 launch 参数化 | 共用上层契约，使用独立且经过验证的适配器 |
| 真机控制器非全部激活启动 | 默认只读，运动授权与软件部署完全分开 |

这些是设计借鉴，不表示已复用、编译或测试上游代码。[S02、S04–S11]

## 3. 不能照搬的部分

主脚本启用 host 网络并映射主机设备目录；X11 路径中有宽泛授权；机载配置使用 privileged 和实时调度权限；可选 SSH 操作会配置 root 密码登录。[S02、S06]

这些做法降低特定开发环境的操作成本，但不应成为面向新手 Web 部署工具的默认权限。D1Env 只为已知能力放行所需设备，浏览器不能任意指定镜像、挂载目录或命令。Docker 官方也专门提醒 Web 服务代理 Docker 时的参数与权限风险。[S19]

另外，仿真/真机虽可共享控制器结构，不能共享未经检查的时钟、硬件模式与关节配置。launch 里出现一个型号选项，不是该型号已完成实机测试的证据。[S10–S12]

## 4. D1 不是一个统一 SDK 目标

| 研究入口 | 看到的事实 | 对产品的影响 |
|---|---|---|
| Edu-Ultra SDK | 部署文档区分 ZSL-1 与 ZSL-1w，平台依赖为 Ubuntu 22.04 系列；轮足不提供 LowLevel 示例接口。[S13–S17] | 点足、轮足必须独立能力配置，不照搬人形关节 policy |
| Edu-Ultra CMake | 有 x86_64 与 aarch64 分支。[S17] | 两种 CPU 都可作为候选；源码分支不等于已验证可运行 |
| Edu-Ultra 网络文档 | 配置不止本机 IP，还涉及本体目标地址/启动环境；文档警告错误配置可能影响遥控器。[S14] | 默认只检查、生成差异；禁止自动覆盖机器人配置 |
| MaxPro SDK | 官方建议 Ubuntu 20.04 x86；仓库同时有 arm64 目录；高层 SDK 不需 ROS1，底层 SDK 才需。[S18] | 不先入为主搭 ROS1 bridge；先验证高层 SDK 的 ABI 与运行环境 |
| 未确认的 D1 商品名称 | 不能仅由 Max/Edu/Ultra 字样推断准确 SDK。[S13、S18] | 收集铭牌/厂商说明和固件证据，无法匹配则阻止实机部署 |

上一轮对话中把 MaxPro 的 ROS1 依赖说得过宽，本次以官方“高层/底层”区别修正。也不再将“点云、里程计等接口所有型号都有”作为既定事实。

## 5. 已见签名不等于已确认语义

Edu 点足与轮足头文件都有高层连接、移动以及姿态/位置/速度读数相关方法；但头文件没有充分说明时间戳、坐标系、估计质量、异常哨兵值和失联行为。[S15、S16]

设计后果：不能直接把某个向量塞进 `/odom` 并当作已合格里程计；不能因为某方法接受 vy 就认定当前机器人模式支持可靠横移；也不能因为能读取关节状态就认定能做低层控制。

## 6. 当前支持声明

本项目所有真实机器人组合均为 `not_implemented`；上游部分能力可标记 `documented`。目前没有一个组合可标记 `hardware_verified`。下拉框展示的是待匹配配置，不是已完成产品支持。

最优先的软件路径是：通用配置/诊断 → 真实 Docker 基础部署 → 一个有来源的高层 SDK 只读适配 → 现场确认后扩展同契约。具体型号由界面输入，研发不能靠选项掩盖缺失适配。

## 7. M0 本地复核附录（2026-10-06）

本附录保留上文的原始调研记录，补充本次在 macOS arm64 开发机取得的实际 Git/文件证据。来源锁见 [UPSTREAM_LOCK.json](UPSTREAM_LOCK.json)，执行报告见 [M0-summary.md](../../reports/M0-summary.md)。本次六个参考仓库都成功取得完整提交 SHA，原包“尚未通过本地 git 固定提交”的限制已在本次来源审计中补齐；SDK/机器人运行状态仍未验证。

| 仓库 | 实际 `git rev-parse HEAD` | 仓库级许可证 |
|---|---|---|
| ioai-tech/ioenv_cli | `ec1f8354095de91a234dc31a9213ee1a410b5cc9` | MIT |
| ioai-tech/humanoid_controller | `2f94ff0ebd072e255d90bbbb2122d0f1a622a0b3` | MIT；已选 motion_tracking/LICENCE 另保留作者文本 |
| ioai-tech/robot_hardware_interface | `fbc18ed07a1926a9f8731b182931d17e1217dbd7` | MIT |
| AgibotTech/agibot_D1_Edu-Ultra | `b5fe0a86094507238944ad118721376a98615ac0` | BSD-3-Clause |
| AgibotTech/Agibot_D1_MaxPro | `7828aef8238388c11267e56d5e44bac9f6dd2eb4` | 未找到仓库级许可，null＋阻塞原因 |
| SteveMacenski/slam_toolbox（humble，后续候选） | `dccc5d1fd2b5007098f4050e681d20da37ef183f` | LICENSE 为 LGPL 2.1 文本；package.xml 仅写 LGPL |

锁中记录 83 个实际读取文件的 SHA-256，包含 73 个文本文件和 10 个 SDK 共享库。来源 SHA 只固定本次已选静态证据，不代表所有依赖已经审计，也不提升真实 Profile 的实现/验证级别。

### 7.1 与设计相关的复核结果

1. **IOENV 配置是可执行的 shell 配置。** 锁定版本 `bin/ioenv:285` 使用 `source`；`:385` 使用 `xhost +`；`:395` 为 host 网络；`:399` 挂载 `/dev`；`:564–567` 设置 root/密码 SSH。`env.d/onboard.env:21` 为 privileged。设计第 5/8 节的严格数据 Profile 与最小权限边界继续有效，不能把这些配置加载到 D1Env 服务中执行。三个环境镜像仍只有 tag（IsaacLab 1.2，MuJoCo/onboard 1.4），不是生产 image digest。
2. **控制器层没有现成 D1 适配。** `humanoid_controller/launch/real.launch.py:106–107` 分别激活 state_estimator/passive_controller，并将运动相关控制器设为 inactive；`:116–117` 的型号菜单仍是 G1/X2/PM01。`robot_hardware_interface.xml:2,9,16` 只注册对应三类插件，未见 D1。此结构支持独立环境引擎的设计选择；passive 的实际机器人行为未经验证，不能当作只读健康检查。
3. **Edu-Ultra 厂商版本声明可被记录，但尚不能当成兼容性证明。** `docs/deploy.md:4–5` 使用文字 `zsi-l/zsi-w`，分别列出 SDK、运控、本体的最低版本；该拼写与 `zsl-1/zsl-1w` 路径的对应关系应向厂商确认。`:168` 继续声明轮足无 LowLevel。部署文档 `:11` 写 CMake 3.8+，实际两个 C++ 示例 `CMakeLists.txt:1` 要求 3.16；后续打包应以实际编译验证确定工具链，不能仅沿用简表。
4. **完整 API 文档补充了部分单位/顺序。** 相比上文只审头文件，新增已读 `docs/api_zsl-1.md:450,453` 的四元数顺序 `[w,x,y,z]` 和机身轴约定，`:544,554` 的上电原点坐标与米，`:580` 的原点系速度 m/s，`:689` 的腿序 FR/FL/RR/RL；`docs/api_zsl-1w.md:360,530` 分别说明四元数顺序和电量百分比。它们只能成为 vendor documented 语义。时间戳/同步、样本新鲜度、估计质量、重置/异常/失联行为及各模式运动能力仍未验证，不足以宣布 `/odom`、TF 或运动网关已实现。
5. **MaxPro 运行时与版本仍须单独验证。** `README.md:20–22` 再次确认 Ubuntu 20.04 x86 推荐、高层无 ROS1、底层需 ROS1；`:85–87` 是 V2.0.5–V2.0.7 更新记录，而实际库位于 `high_level_remote_client_209`。头文件 `include/high_level_base.h:103` 声明 GetSdkVersion，但本次没有实例化/调用。目录后缀和更新记录不能证明确切二进制版本；锁中 `sdk_version=null`。README `:6–7` 还明确二次开发者负责状态与资源条件，不支持把部署成功解释为运动安全。
6. **许可与工件来源仍有生产阻塞。** MaxPro 完整 Git 树未找到仓库级 LICENSE/COPYING；`nlohmann/json.hpp` 中 MIT 许可仅覆盖该第三方文件，不能替代厂商 SDK 再分发许可。五个必需仓库的实际 Git tags 查询和 GitHub releases 查询均未发现 tag/发布条目；SDK 语义版本仍需独立厂商证据。SLAM 候选虽有 52 个发布条目，本轮未集成它。Edu 的 `docs/D1_Edu-Ultra` gitlink 未初始化，不能声称其子仓文档已审计。

上述新增 API 文档的不可变入口为 [点足 API](https://github.com/AgibotTech/agibot_D1_Edu-Ultra/blob/b5fe0a86094507238944ad118721376a98615ac0/docs/api_zsl-1.md)、[轮足 API](https://github.com/AgibotTech/agibot_D1_Edu-Ultra/blob/b5fe0a86094507238944ad118721376a98615ac0/docs/api_zsl-1w.md)、[MaxPro 高层 API](https://github.com/AgibotTech/Agibot_D1_MaxPro/blob/7828aef8238388c11267e56d5e44bac9f6dd2eb4/docs/source/4.1%E9%AB%98%E5%B1%82%E8%BF%90%E5%8A%A8%E6%8E%A7%E5%88%B6%E6%8E%A5%E5%8F%A3.md)。逐条行证据保存在 `work/evidence/task0-source-review-commands.jsonl`。

### 7.2 SDK 二进制只做静态检查

对官方锁定 Git 树中的 10 个 `.so` 文件设置单文件 8 MiB、单仓累计 24 MiB 的取得上限；实际合计 6,658,920 字节。取得后核对 Git blob 身份、实际字节数和 SHA-256，仅运行系统 `file` 与 `objdump -p`，未运行 `ldd`、未加载共享库、未调用 SDK、未编译或执行 demo。

Edu-Ultra 的点足/轮足 C++ 库和 Python 扩展分别覆盖 x86_64/aarch64，ELF 头与声明目录一致。C++ 库的 DT_NEEDED 有 libstdc++、libgcc_s、libc 和对应 Linux loader；Python 扩展另依赖 `libpython3.10.so.1.0`。符号版本引用包括 GLIBC_2.34，Python 扩展另见 GLIBCXX_3.4.29；这属于工件 ABI 证据，不是 Linux 运行通过的结论。

MaxPro x86/arm64 两个 C++ 库的 ELF 分别为 x86-64/AArch64，DT_NEEDED 同样列出标准 C++/GCC/C 库与对应 loader。所有库完整路径、大小、哈希、动态依赖和 ABI 符号版本都写入锁；实际 SDK 语义版本及对应固件均为未验证。

因此锁固定 `scope=static_source_audit`、`production_usable=false`。本次只完成来源与静态元数据复核；真实适配、容器、SDK 调用与硬件证据仍须在后续独立阶段取得。未知版本或缺失许可不得转为生产 ArtifactRef，MOCK 软件工作可继续。
