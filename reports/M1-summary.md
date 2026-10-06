# M1 基础核心实际实施报告

日期：2026-10-06。范围：Foundation Task 1–4；只有 MOCK Executor，没有机器人、厂商 SDK 或真实容器执行。

## 实际完成

严格 Pydantic v2 数据契约、数据型 YAML Catalog、来源化候选 Profile、只读本机 Doctor、确定性 Plan Resolver、SQLite 作业/事件/幂等键、POSIX 单目标锁、取消归属清理和中断恢复已实现。CLI/UI 后续通过同一 ApplicationService 使用这些接口。

真实候选为 `edu-zsl-1`、`edu-zsl-1w`、`maxpro` 和 `unknown`。型号、固件、SDK 版本、工件或适配器不足时返回阻塞，不能自动切成 MOCK。只有明确 `kind=mock` 的 demo 可执行；所有作业成功的 `verified_scope` 固定为 `mock`。

Plan ID 为规范化有效配置的 SHA-256；包含 Profile 修订、应用版本、请求场景和执行平台，排除观测时间与会话凭据。保存原始不可变请求；开始前重新检测、重新解析，条件或计划变化时拒绝执行。

Job Engine 使用短 SQLite 事务、单目标活动作业唯一约束和文件锁。相同键/计划复用原作业，键/计划不一致冲突，同目标不同活动计划拒绝。已成功计划可复用历史结果；失败/取消/中断重试用新键并保留原始计划。旧活动任务在实际工作进程消失后转 INTERRUPTED，保存资源盘点，不自动重试。取消仅处理登记的本作业资源，核对 device/inode，不删除其他项目、用户地图或 bag。

## TDD 和实际命令

| 命令 | 退出码 | 实际结果/证据 |
|---|---:|---|
| `.venv/bin/python -m pytest tests/test_catalog.py -q`，实现前/后 | 2 / 0 | 最初缺模块；初版 GREEN 5 passed，`work/evidence/task1-{red,green}.log` |
| `.venv/bin/python -m pytest tests/test_doctor.py tests/test_process.py tests/test_planner.py -q`，实现前/后 | 2 / 0 | 最初缺模块；初版 GREEN 22 passed，`task2-3-{red,green}.log` |
| Task 1–3 锁定依赖后联合运行 | 0 | 27 passed；`tasks1-3-locked-green.log` |
| `.venv/bin/python -m pytest tests/test_jobs.py tests/test_recovery.py -q`，实现前/后 | 2 / 0 | 最初缺模块；初版 GREEN 21 passed；`task4-red.log`、`task4-final-0.log` |
| `.venv/bin/d1env doctor` | 0 | 实际本机只读检查；`doctor-local.json`，并非 stub |
| `.venv/bin/d1env plan --profile unknown --mode real_readonly` | 1 | 正确阻塞：plan=null、PROFILE_UNVERIFIED；`cli-real-blocked.json` |
| 最终 Python 3.10.20 全套 `work/venv310/bin/python -m pytest -q` | 0 | 90 passed / 0 failed / 0 skipped；涵盖 M1/M2，不能把阶段重复运行相加为独立测试数 |

后续审查补充了 literal-true readiness、缺失/陈旧/null/非有限遥测、不可变工件摘要、UTF-8 和超时标记的 64 KiB 输出上限回归。每项实际 RED→GREEN；最终日志见 [M2-summary.md](M2-summary.md)。以上阶段计数是当时快照，最终独立 Python 用例数为 90。

## 本机检查与范围

实际 Darwin 26.6.2 / aarch64：PLATFORM=WARN，DOCKER/COMPOSE/DISK=PASS，GPU/NETWORK=SKIPPED，ROBOT=UNKNOWN。Docker 仅执行默认本地 context 的 info 与 Compose version；枚举本地接口名称，没有机器人 IP 探测。电量、姿态、遥测时间和来源均为 null。此处的三个 PASS 不证明容器部署或机器人健康。

依赖实际锁于 uv.lock。开发初期使用已有 Python 3.12；随后隔离下载 CPython 3.10.20，完成实际 3.10 测试，未加载厂商 Python 扩展。源码审计、准确版本/固件和许可阻塞见 [M0-summary.md](M0-summary.md)。

## 未验证与下一阶段

真实 Docker 生命周期、Linux 安装包、工件下载/导入、SDK 加载/API、真实遥测、网卡/驱动/固件、SLAM/导航、运动与物理停止全为 NOT_RUN。Mock readiness 只验证 mock_ready=true；容器 running 或进程活着不能替代业务就绪。M1 核心进入同轮 M2 向导/报告，M3 仍需独立授权和真实验收。本轮已停在 M2。
