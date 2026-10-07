# 首次运行准备核心的实现与验证

日期：2026-10-07（Asia/Shanghai）。仅软件实现和注入测试；本代理没有安装、启动、停止主机 Docker，没有创建容器或运行厂商 SDK。

实现所有权：`src/d1env/setup/{__init__,models,download,installer,manager}.py`、`tests/test_setup_{download,installer,manager}.py`。没有修改其他代理负责的 API、服务、前端和打包文件，没有创建提交或推送。

接口：SetupManager 的 status/get 重新调用只读 probe 和 image_probe，任务历史 state 与当前 environment_ready 分开；需要当前本机 Linux aarch64 Docker、Compose、锁定镜像都取得 literal true，未知为 null。prepare、continue_task、cancel 使用后台任务、用户私有 JSON/锁、原子写和取消标记；同 key 复用，另一个进程持有租约时不恢复/重复启动。服务重启后无活租约的 RUNNING 标记 INTERRUPTED，不自动安装或继续。

缺失 Docker 的 Mac aarch64 支持候选先 WAITING_USER，要求确认官方许可。随后固定官方 HTTPS 地址、字节数、SHA；拒绝跳转、弱 TLS、共享/链接缓存，取消片段不会晋升。坏的本项目私有缓存失效后，下次明确重试重新下载；不进行 Range 恢复。macOS 系统/版本未知或未支持、已有权限/架构/端点错误不会安装或替换。

Mac 原生操作严格 argv、不使用 shell/sudo/系统密码：只读挂载，codesign 的固定 bundle/Team 要求，Gatekeeper 评估；使用 ditto 保存扩展属性，不清除 quarantine。不存在已有 Docker.app 且可写时暂存复制，macOS RENAME_EXCL 原子提交不覆盖。权限不足打开已验证官方安装盘等待用户原生安装。启动只用固定 open Docker.app；必要原生许可和设置等待用户完成，超时 WAITING_USER。取消/超时只结束本任务子进程组，不停止 Docker，不卸载应用，不清理其他项目。挂载卸载失败明确失败并保留应用/安装盘。

真实测试命令与退出码：

| 命令 | 退出码 | 结果 | 证据 |
|---|---:|---|---|
| `.venv/bin/python -m pytest --tb=short -q tests/test_setup_download.py tests/test_setup_installer.py tests/test_setup_manager.py` | 0 | 70 passed / 0 failed / 0 skipped | backend-final-python312.log |
| `work/venv310/bin/python -m pytest --tb=short -q tests/test_setup_download.py tests/test_setup_installer.py tests/test_setup_manager.py` | 0 | 70 passed / 0 failed / 0 skipped，同 70 用例 | backend-final-python310.log |
| `.venv/bin/ruff check src/d1env/setup tests/test_setup_*.py` | 0 | All checks passed | backend-final-ruff.log |
| `.venv/bin/mypy src/d1env/setup` | 0 | 5 source files 无错误 | backend-final-mypy.log |

TDD 历史：download-red、installer-red、manager-red 各实际 pytest 退出 2（实现模块缺失，1 collection error）；各最小实现后通过。初版 manager-green 为 1 failed/22 passed（退出 1），测试把失败任务与当前环境混淆，修正测试使模拟镜像观测也未通过，不把真实当前证据藏掉。status-contract-red 为 9 failed/22 passed（退出 1），添加 error_code、前端平台契约、观察时间与严格当前 Docker availability 后 58 passed（退出 0）。recovery-review-red 为 6 failed/60 passed（退出 1），修复失效缓存恢复、原生卸载返回码、应用权限、重复 key 竞态、 malformed 只读观测后 66 passed（退出 0）。额外取消/时限验证后当前 70 passed。旧失败输出保留，无任何失败折算为通过。

首次 download-red 的外层工具命令还读取日志，所以外层返回 0；日志中 pytest 本身是 collection error，真实 pytest 退出 2。后续所有测试命令独立返回 pytest 退出码；没有再用读日志后的退出码代表测试。

未验证：真实缺失 Docker 的 Mac 安装、无 /Applications 写权限的原生授权、实际首次许可、首次启动超时/取消、已有真实 Docker 的 current/reuse（由 root 另验）、Intel/Linux/全新 Ubuntu、厂商 SDK/机器人/传感器/运动。原生过程以上为注入/单元验证，不称实机安装通过。程序不自动勾选 Docker 的协议或订阅，不声称 Docker Desktop 完整源码提交可取得。

构造语义：SetupManager 初始化会创建私有任务文件并进行必要中断恢复；status/get 本身刷新不写，测试逐字节和 mtime 验证。若服务保持懒加载，则第一次 GET 触发构造写；HTTP GET 绝对无状态初始化写需服务启动时构造 manager，由 root 决定集成。
