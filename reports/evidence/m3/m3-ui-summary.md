# M3 前端验收证据

当前前端单元测试 29/29 PASS，构建 PASS；真实本地 API 浏览器测试 2/2 PASS。没有提交代码、修改 Python 或依赖锁。真实 Docker/ROS 证据来自实际 API E2E；HTTP 单元 fixture 不作为 Docker 或真机验证。

## TDD 与构建

命令均在 `frontend/` 运行。

| 功能 | 失败证据（`npm test -- --run`，退出 1） | 后续通过 |
|---|---|---|
| 软件模式、原计划恢复、软件停止与 3s 轮询 | `m3-ui-red.log`：6 failed / 12 passed | 18 passed |
| 历史成功不能作为当前健康 | `m3-ui-health-unknown-red.log`：1 failed / 18 passed | 19 passed |
| 受信随包镜像导入、缺元数据禁用、错误与身份复核 | `m3-ui-import-red.log`：4 failed / 19 passed | 23 passed |
| 改变配置范围不能混用旧软件结果与 MOCK 标识 | `m3-ui-scope-red.log`：1 failed / 23 passed | 24 passed |
| 会话失效降级、挂起 5s 失效、FAILED/INTERRUPTED 清理、历史恢复 | `m3-ui-p1-red.log`：5 failed / 24 passed | `m3-ui-p1-green.log`：29 passed，退出 0 |

`npm run build`：退出 0，证据 `m3-ui-build.log`；包含 TypeScript 检查和 Vite 正式构建。最终生成 27 个模块，静态产物位于 `frontend/dist/`。

## 实际浏览器验证

独立 headless Chromium，`http://[IP]:18765`，真实本地 API。会话凭据仅从私有引导文件读取到内存，单次建立 HttpOnly cookie；导航、日志、保存的认证文件与截图不含凭据，trace/video/自动截图关闭。

最终命令：`D1ENV_E2E_SOFTWARE=1 D1ENV_E2E_ROS_BUNDLE_FILE=<绝对发行工件路径> D1ENV_E2E_TOKEN_FILE=<私有引导文件路径> D1ENV_E2E_URL=http://[IP]:18765 npx playwright test`。

- `m3-ui-e2e-mock.log`：初次实际 MOCK 流程 1 passed / 软件 1 skipped，退出 0。此 skipped 明确计为软件 NOT_RUN。
- `m3-ui-e2e-software-first-failure.log`：首次完整软件轮次 2 failed，退出 1。软件已走到真实成功/刷新/断连降级，但 UNKNOWN 错误码定位同时匹配标题和证据 JSON，断言失败；Playwright 换 worker 后 MOCK 因单次引导已消费而失败。本轮整体没有记为 PASS，后端就绪条件没有为此放宽。
- `m3-ui-e2e-software.log`：修正精确定位、重新建立新会话后 2 passed，退出 0，耗时约 1.2 分钟。软件用例约 1 分钟，MOCK 约 5.9 秒。

软件实际流程：发行包原始文件导入（受信镜像已存在时 reused）→固定软件计划/重复点击单提交→当前 ROS 通信通过→刷新恢复同一作业与原模式→浏览器网络读取故障注入降级 UNKNOWN→恢复当前通信→显式停止→`no_publisher` 故障注入 FAILED→刷新→切换模式后从历史入口恢复原软件作业与场景→实际下载软件范围 JSON/Markdown→显式清理→原计划、新请求键重试同一故障→显式清理。测试 finally 逐个从历史入口恢复并清理本次 POST 返回的作业 ID；不自动清理其他作业。

MOCK 实际流程保留成功、故障注入、重复提交防护、刷新、原计划重试、去敏报告与脚本文本不执行验证。

## 原始截图与下载来源

以下均来自最终真实浏览器界面，保存于 `frontend/test-results/`：

- `m3-ui-software-import.png`：受信软件镜像导入结果，仍须另行通信检查。
- `m3-ui-software-success.png` / `m3-ui-software-success-viewport.png`：当前软件检查通过，software 范围，未连接真机。
- `m3-ui-software-network-fault-injection.png`：浏览器网络读取故障注入；历史 SUCCEEDED 保留、当前 UNKNOWN，绿色通信结果撤下。
- `m3-ui-software-failure.png` / `m3-ui-software-failure-viewport.png`：真实软件 no_publisher 故障注入证据。
- `m3-ui-software-report.png`：软件诊断报告预览。
- `m3-ui-software-report.json` / `m3-ui-software-report.md`：实际浏览器 Blob 下载保存；JSON 已验证 mode=software_test、verified_scope=software，包含 docker 来源事件。
- `m3-ui-mock-{success,failure}{,-viewport}.png`：MOCK 实际界面，显式 MOCK 标识。

## 验证边界

软件健康每 3s 从服务读取。读取失败立即置 `current_software_ready=null`，证据为 CURRENT_HEALTH_UNAVAILABLE；超过 5s 未取得新成功观测时本地降级 CURRENT_HEALTH_EXPIRED；窗口重新可见也检查过期。保留历史作业状态和事件。没有当前健康证据时不显示绿色通信成功。

硬件配置仍禁用；真实电量和姿态为 UNKNOWN/null，运动权限未启用。没有 SDK、D1 驱动、传感器、导航、真机或硬件急停验证。软件停止仅清理本作业拥有的软件资源。最终服务器与私有会话文件由根代理关闭/移除。
