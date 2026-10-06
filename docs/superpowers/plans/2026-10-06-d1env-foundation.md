# D1Env Foundation Implementation Plan

> **For agentic workers:** 使用已安装的 superpowers:executing-plans 按任务实施；有合适子代理能力时可使用 superpowers:subagent-driven-development。不得虚构子代理审查或测试执行。本文件是待用户采用后执行的计划，不是执行记录。

**Goal:** 交付 M0–M2：可追溯的来源审计、可测试的部署核心，以及能在无机器人条件下运行的中文演示向导。

**Architecture:** UI 与 CLI 共享 Application Service。严格 Profile 解析出不可变 DeploymentPlan，由持久化 Job Engine 执行；此阶段只有 MockExecutor，所有演示证据明确标记，不连接机器人或操作真实容器。

**Tech Stack:** Python 3.10、FastAPI、Pydantic v2、SQLite、Typer；React、TypeScript、Vite；pytest、Ruff、mypy、Vitest、Playwright。锁定真实可用依赖版本；Node 仅研发使用。

**Spec:** `docs/superpowers/specs/2026-10-06-d1env-design.md`

## Global Constraints

- 默认 MOCK / READ_ONLY；本轮不实现 arm 或任何运动 API。
- 不访问机器人、不运行厂商 SDK、不修改网卡、Docker daemon、内核或固件。
- 真实硬件 profile 为 documented/not_implemented；未验证功能不能点击执行。
- 不使用 shell=True、eval、任意 shell/Compose 模板。
- Web/API 只监听 127.0.0.1；实施会话认证及 Host/Origin/CSRF 校验。
- 所有成功结果带 mode 和 verified_scope，缺失数据是 UNKNOWN/null。
- 接触 Docker 的功能本轮只做只读检测和命令计划，不创建/停止容器。
- 保留用户已有工作区修改；网络失败、环境缺失、测试跳过不得写为 PASS。
- 包内已有文档是规划，新增源码、依赖和运行报告时才形成软件实现。

## Review Focus

1. 中文、空格与恶意路径/字段输入：严格校验且不执行 shell。归属 Task 2/3。
2. 用户连续点击部署、刷新页面或开启两个进程：同目标不得重复变更，事件可恢复。归属 Task 4。
3. 服务中途退出、数据库有旧 RUNNING：标为 INTERRUPTED，禁止直接显示完成。归属 Task 4。
4. 本地恶意网页请求 localhost：不能控制部署或读取会话数据。归属 Task 5。
5. 演示成功被误认成真实 Docker/真机成功：UI、API、截图和报告都有一致范围标识。归属 Task 5/6/7。

## 目标文件布局

这些路径是待创建文件，不表示交接包已含实现。

```text
src/d1env/
  models.py                 类型与契约
  catalog.py                Profile 加载/校验
  doctor.py                 只读主机检测
  process.py                白名单 argv 进程探针
  planner.py                确定性解析与阻塞原因
  service.py                UI/CLI 共用应用服务
  jobs/store.py             SQLite 状态/事件
  jobs/engine.py            单目标串行与任务状态
  jobs/executor.py          Executor 契约
  jobs/mock.py              明确标识的演示执行器
  reports.py                去敏诊断导出
  web/app.py                同源 API 与静态资源
  web/security.py           本地会话、Host/Origin/CSRF
  cli.py                    doctor/plan/ui/status/report
profiles/                   随包的严格数据配置
frontend/src/               React 中文向导
schemas/                    数据契约与来源锁 schema
tests/                      Python 单元/API 测试
frontend/tests/              UI 单元与 E2E
reports/                    实际运行报告；敏感数据不得提交
```

统一类型：Mode=`mock|real_readonly`；CheckStatus=`PASS|WARN|FAIL|UNKNOWN|SKIPPED`；EvidenceOrigin=`mock|local_probe|docker|sdk|operator`。本轮 Executor 只接受 origin=mock。

### 跨任务类型的固定契约

以下类型统一定义在 `src/d1env/models.py`，是 Task 1 的交付内容；后续任务不得各自创建同名异构类型。时间统一为带时区的 UTC ISO-8601，ID 使用字符串，事件 seq 为每个 job 内从 1 递增的整数。

| 类型 | 必备字段与约束 |
|---|---|
| `Catalog` | `schema_version: int=1`、`profiles: list[Profile]`；profile_id 唯一 |
| `Profile` | 采用设计第 5 节字段；增加 `kind: mock\|hardware`、`profile_revision: str`；未知实际版本为 null 并记录原因，不能伪造兼容范围 |
| `Blocker` | `code: str`、`message: str`、`remediation: str`、`field: str\|None` |
| `Operation` | `operation_id: str`、`kind: Literal['mock_step']`、`label: str`、`timeout_s: float`、`reversible: bool`、`required_evidence: list[str]`；本轮不接受 command/script 等自由执行字段 |
| `OperationResult` | `operation_id: str`、`status: succeeded\|failed\|cancelled`、`origin: mock`、`evidence: dict[str, JSONValue]`、`error_code: str\|None`、`message: str`、`resource_ids: list[str]`；evidence 仅作数据，不能被重新解释为执行参数 |
| `JobSnapshot` | `job_id`、`plan_id`、`target_id`、`mode`、`state`、`verified_scope`、`current_operation_id`、`created_at`、`updated_at`、`error_code`；可选字段缺失为 null |
| `JobEvent` | `job_id`、`seq`、`timestamp`、`event_type`、`operation_id`、`mode`、`origin`、`message`、`evidence`；错误文本转义后显示 |
| `ExecutionContext` | `job_id: str`、`target_id: str`、`mode: Mode`、`work_dir: Path`、`is_cancelled: Callable[[], bool]`、`emit: Callable[[JobEvent], None]`；不包含真实设备凭据或任意 shell 能力 |
| `ProbeResult` | `argv: tuple[str, ...]`、`returncode: int\|None`、`stdout: str`、`stderr: str`、`timed_out: bool`、`observed_at: datetime`；输出长度上限 64 KiB，截断有标记 |
| `DiagnosticReport` | `schema_version: int=1`、`mode`、`verified_scope`、`job`、`checks`、`events`、`source_locks`、`unverified_items: list[str]`、`redactions: list[str]` |

`JSONValue` 只允许 JSON 标量、列表和字符串键对象。`verified_scope` 在本轮作业中固定为 `mock`；Doctor 的真实观测单独标记 `origin=local_probe`，不会提升整个作业的范围。`JobSnapshot.state` 采用设计第 6 节状态枚举，不另加含糊的 READY 状态。

第一轮 `target_id` 只允许在服务端登记的 `local`，它不是任意 IP 或 SSH 目标。UI 输入不能让 Doctor 探测任意远端。实际主机信息由后端获取，不能相信浏览器提交的 OS/CPU/Docker 状态。

幂等规则：相同 key 与相同 plan 返回原作业；相同 key 搭配不同 plan 返回冲突；同目标已有活动作业时，重复同一计划返回该作业，另一计划被拒绝。失败/取消后明确重试使用新 key。已成功的同一计划默认复用结果；后续 Docker 阶段仍须检查实际资源，不以历史结果证明当前健康。


## Task 0：复核来源并固定审计基线（M0）

**Files:** 更新 `docs/research/SOURCE_AUDIT.md`；创建 `docs/research/UPSTREAM_LOCK.json`、`schemas/upstream-lock.schema.json`、`reports/M0-summary.md`。

**Interfaces:** 消费 `docs/research/SOURCES.md`；产出每个仓库的来源 URL、真实完整 commit_sha 或 null、observed_at、paths/file_hashes、license_path、retrieval_status、未取得原因。该锁是证据，不等于硬件适配状态。

- [ ] 在独立的参考源码目录做只读 checkout；禁止执行上游安装脚本或 demo。先检查 IOENV 的主脚本、三个环境定义、launch 和 D1 对应头文件。
- [ ] 用实际 `git rev-parse HEAD` 记录完整 SHA，实际读取文件计算 SHA-256；无法联网则明确记录 blocked，不用 README 中的版本号代替 commit。
- [ ] 核查前述设计与新取得源码是否冲突，把差异定位到具体文件/行。若阻塞真实适配，继续允许 MOCK 软件工作，不伪造兼容信息。
- [ ] 用 JSON Schema 验证锁文件；null 字段必须伴随 blocked 原因。检查不存在虚构的全零 SHA 或占位摘要。
- [ ] 写 M0 报告，保留实际命令与失败输出，提交仅包含证据与文档的变更。此任务不声称 SDK 可运行。

## Task 1：数据模型与来源化 Profile（M1）

**Files:** `pyproject.toml`、实际依赖锁；`src/d1env/models.py`、`src/d1env/catalog.py`；`profiles/demo.yaml`、三个 D1 候选配置和 `unknown.yaml`；`tests/conftest.py`、`tests/test_catalog.py`。

**Interfaces:**

- `load_catalog(path: Path) -> Catalog`
- `validate_profile(raw: dict[str, object]) -> Profile`
- `DeploymentRequest(mode, profile_id, target_id, task)`；本轮 task 只允许 `demo` 或 `diagnostics`。
- `HostFacts(target_id, os_name, os_version, architecture, docker_available, docker_accessible, compose_available, disk_free_bytes, gpu_available, checked_at)`；未知观测允许 null。
- `CheckResult(code, status, reason, remediation, origin, observed_at, evidence)`。
- `PlanResolution(plan: DeploymentPlan | None, blockers: list[Blocker])`。
- `DeploymentPlan(plan_id, mode, target_id, profile_id, operations, required_evidence, verified_scope)`。

- [ ] 写失败测试 `test_rejects_unknown_fields_and_yaml_objects`：额外 shell 字段、执行型 YAML 标签均拒绝；未知家族不能被映射到某个真实 SDK。
- [ ] 写 `test_missing_telemetry_stays_unknown`：缺失电量/姿态为 null＋UNKNOWN，不能自动填 0；源头声明的能力不自动升级为 integration_verified。
- [ ] 运行 `pytest tests/test_catalog.py -q`，保存真实失败原因。
- [ ] 实现模型与 schema；schema_version 固定为 1，Pydantic `extra='forbid'`。演示 Profile 明确 kind=mock、sdk_family=null，不与真实 D1 Profile 混用。
- [ ] 实现三个 D1 候选 Profile 的来源引用与未实施标志；本轮不填写虚构工件地址、固件兼容范围或证据。
- [ ] 再跑测试，只有全部断言通过才完成。创建小提交。

## Task 2：只读 Doctor（M1）

**Files:** `src/d1env/process.py`、`src/d1env/doctor.py`；`tests/test_doctor.py`、`tests/test_process.py`。

**Interfaces:**

- `ProbeRunner.run(argv: tuple[str, ...], timeout_s: float) -> ProbeResult`
- `inspect_host(target_id: str, runner: ProbeRunner) -> HostFacts`
- `diagnose(request: DeploymentRequest, facts: HostFacts) -> list[CheckResult]`

- [ ] 写失败测试：Docker 不存在、daemon 停止、permission denied、Compose 缺失、磁盘不足、没有 GPU、探针超时。CPU diagnostics 不得因为没有 GPU 而失败。
- [ ] 写注入测试：恶意主机/目录文本不进入 shell；argv 仅限已知只读探针；探针默认超时 5 秒，这是软件检测超时，不是机器人失联安全阈值。
- [ ] 运行 `pytest tests/test_doctor.py tests/test_process.py -q`，确认失败后实现。
- [ ] 使用系统接口获取 OS/CPU/磁盘；Docker 使用已知 argv 只读查询。正常失败返回结构化结果，不提示用户随便 chmod 或开 privileged。
- [ ] 在当前开发机实际运行 doctor，把本机的真实检测与单元测试 stub 区分。Mac 可以得到“只支持 UI/计划开发”的提示，不假称 Linux 运行时。
- [ ] 复跑测试并提交。

## Task 3：确定性部署计划和兼容阻塞（M1）

**Files:** `src/d1env/planner.py`；`tests/test_planner.py`。

**Interfaces:** `resolve(request: DeploymentRequest, facts: HostFacts, catalog: Catalog) -> PlanResolution`。

- [ ] 写 `test_unknown_profile_blocks_real_deploy`：real_readonly＋unknown 得到 plan=None 与 `PROFILE_UNVERIFIED`。
- [ ] 写 `test_real_profiles_block_without_artifacts`：没有已实现适配/真实工件时返回 `ADAPTER_UNAVAILABLE` 或 `ARTIFACT_UNAVAILABLE`；不能偷偷降级为 mock。
- [ ] 写 `test_mock_plan_never_requires_robot_network_or_gpu`：mock 计划仅含 mock operation，scope=mock。
- [ ] 写 `test_plan_id_stable_under_key_order_and_probe_timestamp`：同一有效配置的字典顺序/观测时间变化不改变 ID；目标、Profile 或版本变化必须改变 ID。
- [ ] 跑 `pytest tests/test_planner.py -q`，确认失败，再实现规范化 JSON＋SHA-256。摘要输入不含检查时间/会话令牌，但含影响执行的版本和配置。
- [ ] 复跑通过并提交。真实 profile 被阻塞是正确结果，不是缺陷待绕过。

## Task 4：持久化作业与演示执行器（M1）

**Files:** `src/d1env/jobs/{store,engine,executor,mock}.py`、`src/d1env/service.py`；`tests/test_jobs.py`、`tests/test_recovery.py`。

**Interfaces:**

- `Executor.execute(operation: Operation, context: ExecutionContext) -> OperationResult`
- `JobEngine.submit(plan: DeploymentPlan, idempotency_key: str) -> JobSnapshot`
- `JobEngine.get(job_id: str) -> JobSnapshot`
- `JobEngine.cancel(job_id: str) -> JobSnapshot`
- `JobEngine.reconcile_on_startup() -> list[JobSnapshot]`
- `ApplicationService.preview(request: DeploymentRequest) -> PlanResolution` 调用 Task 3；`start(plan_id: str, idempotency_key: str) -> JobSnapshot` 只执行已保存且重新检查仍有效的计划。

- [ ] 写状态机测试，覆盖成功、步骤失败、取消、事件保存；每个事件必须含 mode/origin，mock 成功只对应 verified_scope=mock。
- [ ] 写幂等键测试：同 key/同 plan 返回同 job，同 key/不同 plan 冲突；失败后新 key 可重试。
- [ ] 写双请求/双进程测试：同一 target 最多一个活动变更作业。除 SQLite 事务外，对同目标使用 POSIX 文件锁；当前开发运行平台为 Linux/macOS。
- [ ] 写重启测试：旧 STARTING/VERIFYING 作业变为 INTERRUPTED，不自动变成功、不自动重试硬件动作。
- [ ] 写资源归属测试：取消只撤销本次 mock 创建的资源；别的目标/作业和持久用户数据保持不变。
- [ ] 运行 `pytest tests/test_jobs.py tests/test_recovery.py -q`；实现最小串行 worker、SQLite 作业/事件和 MockExecutor。不要引入 Celery/Redis。
- [ ] 复跑并保存结果，提交。MockExecutor 不运行 Docker，也不伪造 docker pull 的真实下载字节数。

## Task 5：本地认证 API 与 CLI（M2）

**Files:** `src/d1env/web/{app,security}.py`、`src/d1env/cli.py`；`tests/test_api.py`、`tests/test_security.py`、`tests/test_cli.py`。

**Interfaces:**

API：`GET /api/catalog`、`POST /api/doctor`、`POST /api/plans`、`POST /api/jobs`、`GET /api/jobs/{id}`、`GET /api/jobs/{id}/events`、`POST /api/jobs/{id}/cancel`、`POST /api/reports`。另有一次性 session bootstrap；全部业务接口要求有效会话，修改接口还要求 CSRF/同源。

CLI：`d1env doctor`、`d1env plan --profile NAME --mode MODE`、`d1env ui --demo`、`d1env status JOB_ID`、`d1env report JOB_ID --output PATH`。本轮不提供会发送真机命令的 CLI。

- [ ] 写鉴权测试：未认证请求不能读作业或启动操作；外部 Origin/异常 Host 被拒绝；SSE 也不能漏数据；一次性引导令牌不能重放。
- [ ] 写 `test_no_arm_or_arbitrary_exec_endpoint`：运动/任意 shell 路径不存在；API 不接受 mode 隐式降级。
- [ ] 写 CLI/UI 等价测试：同一请求输出相同 plan_id/blockers；CLI 不绕过服务层。
- [ ] 写客户端伪造检测测试：提交自报 HostFacts 或非 local target 不得改变兼容性判定，实际探针由后端执行。
- [ ] 跑 `pytest tests/test_api.py tests/test_security.py tests/test_cli.py -q`，失败后实现同源服务、session、CSRF 和命令入口。
- [ ] 默认绑定 127.0.0.1:8765；端口被其他程序占用时明确报错，不杀其他程序或改为 0.0.0.0。令牌不写 URL query、终端日志或报告。
- [ ] 复跑测试并提交。

## Task 6：中文五步向导（M2）

**Files:** `frontend/package.json`、真实 npm lock；`frontend/src/App.tsx`、`frontend/src/api.ts`、`frontend/src/types.ts` 和按页面拆分的组件；`frontend/tests/`。

**Interfaces:** 从已固定的 API schema 生成或严格对齐 TypeScript 类型；页面只消费服务端状态，不自行假定 Docker/机器人成功。

- [ ] 写 UI 失败测试：模式、机器人配置、执行主机、预览、运行结果五步可导航；未支持配置显示具体原因，执行按钮禁用。
- [ ] 写 UNKNOWN/MOCK 测试：无数据不亮“正常”；MOCK 水印贯穿全部页面，截图不会因切页消失。
- [ ] 写 E2E：连续点击只生成一份作业；刷新后恢复现有 job；模拟步骤失败后出现证据/重试/导出；脚本样式日志作为纯文本，不执行 HTML。
- [ ] 执行 `npm ci && npm run test -- --run`，记录真实失败；实现组件。优先并排的“当前步骤 / 状态证据”布局，不做单列日志瀑布。
- [ ] 运行 `npm run build` 与 `npx playwright test`，截取实际界面；文件名/报告写明 mock。没有浏览器测试能力就记录未执行，不能用生成图代替。
- [ ] 提交 UI 与测试；不得以静态页面截图冒充完整部署闭环。

## Task 7：去敏报告、打通软件演示与第一轮验收（M2）

**Files:** `src/d1env/reports.py`、`tests/test_reports.py`；`reports/M1-summary.md`、`reports/M2-summary.md`；更新 README 软件开发启动方法。

**Interfaces:** `build_report(job: JobSnapshot, checks: list[CheckResult], events: list[JobEvent]) -> DiagnosticReport`；导出 JSON 与 Markdown，不收集密钥。

- [ ] 写测试：已知凭据键、session/Authorization 字段递归去敏；用户 IP/序列号在导出预览中可选择遮盖；原始证据的来源和失败内容仍可追溯。
- [ ] 写测试：报告保留 mode、verified_scope、执行机器、source locks、各检查状态、跳过项；mock 不可被格式化成 hardware_verified。
- [ ] 跑 `pytest tests/test_reports.py -q`，失败后实现；不把完整私钥、环境变量或家目录打包。
- [ ] 运行全套 Python 测试、Ruff、mypy、前端测试/build 和实际 E2E。报告实际命令、退出码、通过/失败/跳过数，不写预期结果充当实测。
- [ ] 复核 `docs/ACCEPTANCE.md` 的 A01–A12。制作一次成功演示和一次明确失败演示，截图均来自本次软件运行并带 MOCK 标识。
- [ ] 交付当前项目启动入口、真实截图、报告路径、未实现项。停止于 M2，不进入 M3、不连接机器人。提交阶段结果供用户审查。

## 第一轮完整验收

必须能够在没有机器人和厂商 SDK 的开发机上运行中文向导、真实主机只读诊断、确定性计划与清楚标识的演示作业。真实型号未实现时阻止执行。用户可以刷新看回同一作业、取消、查看失败原因、导出报告。

本轮不会生成“真机部署成功”结论，也不等于已经交付最终的一键安装包。
