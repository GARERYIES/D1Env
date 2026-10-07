# D1Env 采用的 IOENV 分层蓝图

日期：2026-10-07。状态：用户确认的架构约束；补充原始 D1Env 设计，不改变各阶段的执行授权和验收门槛。

## 产品目标

让新人通过中文 UI 选择已适配的型号与功能，在执行主机上准备软件环境、启动指定功能，并得到带证据的检查结果。环境安装、容器运行、软件就绪、真实数据就绪分别展示。MOCK 是研发与演示入口；真实 Docker/ROS 探针是阶段验收，均不能替代最终的 D1 功能接入。

沿用 IOENV 的配置驱动与容器生命周期思路，独立实现 D1Env 部署引擎。后续任务必须说明参考的上游机制、保留或改造的行为，以及验证方法。

## 三层职责与落点

这是逻辑职责的三层划分：IOENV 的环境定义与容器管理位于 `ioenv_cli`，机器人业务启动位于独立的 `humanoid_controller` 等包。

| 层次 | 已核到的 IOENV 机制 | D1Env 的承接方式 | 当前与后续范围 |
|---|---|---|---|
| 环境定义 | `env.d/*.env` 描述镜像、工作目录、卷、GPU、显示等；`resolve_environment()` 加载环境 | 严格数据 Profile 与 Catalog；按型号、功能、CPU、工件和证据解析确定性 DeploymentPlan | M1 已实现严格配置/解析；真实工件与运行参数在 M3 及对应适配阶段补齐 |
| 容器管理 | `docker_pull()`、`ensure_volumes()`、`docker_create/start/run/stop/remove()`：获取镜像、复用卷与容器、启动和停止 | Job Engine 持久化步骤/事件，受限 DockerExecutor 执行生命周期操作；增加幂等、归属、恢复、诊断与安装体验 | M2 仅 MockExecutor；真实 DockerExecutor、安装包和资源盘点属于 M3 |
| 机器人业务 | 独立 ROS launch 选择配置并启动控制器、状态估计与硬件接口 | 按已验证组合启动 D1 高层只读适配、传感器、建图/导航软件链；逐功能检查就绪与数据新鲜度 | M4 接一个准确组合的只读 SDK；M5 接传感器与导航软件链；运动另属 M6 现场验收 |

UI 与 CLI 共用 Application Service；它们不能绕过 Profile、计划、任务和执行器直接操作 Docker 或 SDK。现有 `catalog.py`、`planner.py`、`service.py`、`jobs/engine.py` 承接前两层的基础契约，尚未实现真实容器或机器人业务。

## 具体参考与必须改造的行为

以下行号对应 [UPSTREAM_LOCK.json](research/UPSTREAM_LOCK.json) 中固定提交的原始文件，不对应不断变化的 `main`。

| 上游入口 | 参考或改造要求 |
|---|---|
| `ioenv.sh`；`bin/ioenv` 的 `resolve_environment()`，207–287 | 前者注册 PATH/补全，后者才是命令主入口。参考环境选择与配置拆分；D1Env 不执行其 shell 配置，配置只作严格校验的数据 |
| `bin/ioenv` 的 `docker_pull()`，312–340；`conf.d/mirrors.env` | 参考镜像获取、缓存与镜像站选择；D1Env 要求真实来源、不可变标识和内容校验，失败不能关闭 TLS |
| `bin/ioenv` 的 `ensure_volumes()`、`docker_create/start/run()`，346–472 | 参考资源复用和生命周期；增加计划预览、归属标签、真实资源复核、超时、取消及中断恢复，不按名称认领外部资源 |
| `bin/ioenv` 的 `docker_stop/remove/remove_volume()`，474–542 | 分开停止、移除容器和删除数据；D1Env 自动取消/回滚只处理本次拥有且可安全撤销的资源，不清除用户地图、bag、镜像或其他项目 |
| `humanoid_controller/launch/real.launch.py`，65–117、132 | 参考业务启动独立于环境、配置与适配器分离的组织方式；该版本型号为 G1/X2/PM01，无现成 D1 适配。已激活的 passive_controller 仍属硬件控制栈，不能当只读健康检查；真实 launch 中的 `use_sim_time=True` 也需独立核验，不能照搬驱动或时钟配置 |
| `bin/ioenv`，385、395、399、451、564–567；`env.d/onboard.env`，21–24 | 改造宽泛 X11 授权、host 网络、整个 `/dev`、privileged、实时权限和可选 root 密码 SSH 行为；SSH 配置由显式 `sshopen` 触发，并非 `run` 自动开启。只开放经验证的具体能力，浏览器不接受自由命令/镜像/挂载参数 |

Docker 操作权本身属于高权限信任边界；受限执行器限制的是可执行操作范围，不能描述成安全沙箱。参见 [Docker daemon 权限说明](https://docs.docker.com/engine/security/)。

## 成功结果的含义

锁定版本 `bin/ioenv:471` 的 `run` 最终进入容器 `/bin/bash`；`:445` 的首次检查只执行 `echo`，`list` 仅查镜像、容器及 running 状态。因此这些结果不证明机器人连接、传感器数据或导航就绪。

主 CLI 未显式调用上述 ROS 业务 launch，但创建容器时没有覆盖镜像 ENTRYPOINT/CMD。本项目尚未检查 IOENV 镜像内部的默认启动逻辑，不能据此断言所有镜像都不自动启动业务；其业务健康仍需独立验证。

D1Env 的每个功能计划要声明检查目标和所需证据。启动指定功能后，只有本计划的检查通过才可成功；缺失/过期数据、仅有进程 running 或旧数据库成功记录都不能替代当前证据。结果保留 `mode`、来源和 `verified_scope`，未支持型号明确禁用，未知状态显示 UNKNOWN/null。

M3 先用真实 CPU ROS 通信探针验证部署与检查链，这是后续 D1 接入的基础；不能将其包装成 D1 驱动、传感器或导航已完成。完整出口仍按 [验收矩阵](ACCEPTANCE.md) 的 A13–A24 分阶段取证。

## 开发、发行与实施约束

Mac 可继续开发界面、核心契约与测试；首版真实运行、安装包和桌面入口以原设计的 Ubuntu 22.04 x86_64 为验收目标。Mac 上的 Docker 测试不能代替全新 Ubuntu 安装验收。终端用户不应手装 Node、编译 ROS 工作区或编辑 YAML。

后续实施计划应逐项列出：上游参考路径/提交、D1Env 对应模块、保留行为、改造理由、失败测试和实际验收证据。继续沿现有 M3→M4→M5 路线推进，每轮独立实施；本次蓝图确认不表示授权执行 SDK、机器人写操作或运动。

## 来源与本次核验

- `ioenv_cli`：`ec1f8354095de91a234dc31a9213ee1a410b5cc9`，MIT；[固定版本主脚本](https://github.com/ioai-tech/ioenv_cli/blob/ec1f8354095de91a234dc31a9213ee1a410b5cc9/bin/ioenv)。
- `humanoid_controller`：`2f94ff0ebd072e255d90bbbb2122d0f1a622a0b3`；[固定版本业务 launch](https://github.com/ioai-tech/humanoid_controller/blob/2f94ff0ebd072e255d90bbbb2122d0f1a622a0b3/launch/real.launch.py)。详细许可和其他来源见来源锁与 [SOURCE_AUDIT.md](research/SOURCE_AUDIT.md)。
- 2026-10-07 重新读取固定提交的主脚本；远程、本地及来源锁的 SHA-256 均为 `9e580d837e0ee68ca7cd6958502bbb89e4ac21cee88834b2e252d28bb05001c1`。本次只读核对并更新文档，未运行上游脚本、真实容器、SDK 或机器人。
- `work/venv310/bin/python work/evidence/task0_validate.py`：退出 0，6 个仓库、83 个文件哈希重算一致，8 个无效来源负例均被拒绝。
- 本轮仅改文档；源码未变，未重跑功能测试，不能据此新增 Docker/Linux/真机通过声明。

原始 [产品与架构设计](superpowers/specs/2026-10-06-d1env-design.md) 保留；当前运行证据仍以 M0–M2 报告为准。
