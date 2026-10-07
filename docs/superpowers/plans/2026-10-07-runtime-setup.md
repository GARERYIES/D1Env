# M3 补充：首次运行环境准备

用户在已采用 IOENV 分层蓝图后要求“补上”省去手工 Docker 准备的产品流程。本轮补充当前 Mac Apple Silicon 软件候选；Linux 原始产品目标与真机验收继续按原路线实施。此文件记录本轮任务及验收入口，原始设计不改写。

| 任务 | 上游机制与本轮改造 | 对应实现 | 验收 |
|---|---|---|---|
| 可信来源 | IOENV `docker_pull()` 的获取/缓存思路；改为固定官方 Desktop 版本、大小、SHA、厂商签名，不接受用户网址、不关闭 TLS | `docs/build/DOCKER_DESKTOP_LOCK.json`、`setup/download.py` | 完整官方 DMG 下载和只读签名核验；拒跳转、损坏、磁盘不足、取消的失败测试 |
| 环境准备 | IOENV 环境层与容器层分开；新增已有环境复用、首次许可、原生安装/授权、启动和有限等待 | `setup/installer.py`、`setup/manager.py` | 状态持久化、租约、重复请求、中断恢复、权限、取消；原生安装仅假执行器测试，未修改当前 Docker 安装 |
| 本机入口及镜像 | IOENV 镜像与容器复用；严格本机 Unix 端点、可信 CLI 和固定 ROS 工件 | `docker/endpoint.py`、`service.py`、发行包 `bundles` | 端点/权限/签名失效测试，摘要固定配套包；真实已有 Docker/镜像复用 |
| 中文 UI/API | 原 CLI 进入容器不证明业务就绪；首次准备只显示 `runtime_environment` | runtime API、`RuntimeSetupPanel` | 会话/Host/Origin/CSRF、注入拒绝、UNKNOWN/TTL、按钮幂等、刷新恢复、真实浏览器截图 |
| 完整候选包 | IOENV 主机入口思想；终端用户不用安装 Node/Python、编译 ROS 或编辑 YAML | `build-release.py --ros-bundle` | 新目录 0.3.0 包、迁移启动及 manifest 校验，旧 M0–M3 包保留 |

固定参考为 `ioai-tech/ioenv_cli` 的 `ec1f8354095de91a234dc31a9213ee1a410b5cc9`，详细行证据见 `docs/IOENV_BLUEPRINT.md`。本轮不运行上游脚本，不连接机器人、调用厂商 SDK、配置网络/驱动/固件或实现运动。

许可必须由用户明确确认适用，系统权限在 macOS 原生界面处理。D1Env 不接收系统密码，不自动接受 Docker 许可，不覆盖既有应用、不修改全局 Docker context/socket，不发布或推送。本轮不会为了验证首次安装而修改研发机 Docker。

验收分开记录：单元/集成假执行器、官方包只读核验、实际既有 Docker 复用、真实 ROS 软件测试、未运行的全新系统安装。不得把后三者合并成新装通过或 D1 功能支持。交付见 `reports/M3-setup-summary.md` 与独立审查报告。
