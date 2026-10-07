import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../../src/App';
import type { Catalog, DeploymentPlan, DoctorResponse, JobEvent, JobSnapshot, Profile } from '../../src/types';
import { catalog, checkedAt, doctor, job, plan } from './fixtures';

// Controlled HTTP fixtures for UI logic only; these are not built image evidence.
const softwareProfile: Profile = {
  ...catalog.profiles[0], profile_id: 'ros-probe', name: 'CPU ROS 通信测试', kind: 'software',
  profile_revision: 'software-unit-fixture', capabilities: { ros_probe: { status: 'implemented', declared_by_vendor: false, evidence_refs: ['unit-fixture'], reason: '仅验证 ROS 软件消息，不连接机器人' } },
  artifact_requirements: [{ kind: 'local_build', source: 'd1env/ros-probe', architecture: 'aarch64', immutable_id: `sha256:${'c'.repeat(64)}` }],
};
const softwareCatalog: Catalog = { schema_version: 1, profiles: [...catalog.profiles, softwareProfile] };
const softwareDoctor: DoctorResponse = { ...doctor, facts: { ...doctor.facts, docker_available: true, docker_accessible: true, compose_available: true, docker_error: null, docker_os: 'linux', docker_architecture: 'aarch64', docker_version: 'unit-version' }, checks: [{ code: 'DOCKER_RUNTIME', status: 'PASS', reason: 'Linux aarch64 Docker 只读观测', remediation: '审阅真实软件计划', origin: 'local_probe', observed_at: checkedAt, evidence: { runtime: 'linux' } }] };
const softwarePlan: DeploymentPlan = { ...plan, plan_id: 'c'.repeat(64), mode: 'software_test', profile_id: 'ros-probe', verified_scope: 'software', network: 'project_internal', request: { mode: 'software_test', profile_id: 'ros-probe', target_id: 'local', task: 'ros_probe', demo_scenario: 'success', probe_scenario: 'success' }, operations: [{ operation_id: 'verify', kind: 'docker_step', label: '验证 ROS 消息新鲜度', timeout_s: 60, reversible: true, required_evidence: ['fresh_messages'], artifact: softwareProfile.artifact_requirements[0], probe_scenario: 'success' }], services: ['publisher', 'subscriber'], permissions: ['Docker daemon 操作权'], directories: ['仅项目作业目录'] };
const softwareJob: JobSnapshot = { ...job, job_id: 'software-job-1', plan_id: softwarePlan.plan_id, mode: 'software_test', verified_scope: 'software', current_software_ready: true, current_health_evidence: { containers_running: true, software_ready: true, sample_count: 5 } };
const softwareEvents: JobEvent[] = [{ job_id: softwareJob.job_id, seq: 1, timestamp: checkedAt, event_type: 'verified', operation_id: 'verify', mode: 'software_test', origin: 'docker', message: '测试节点已接收新鲜 ROS 消息', evidence: { fresh_messages: true, sample_count: 5 } }];
type Call = { path: string; init?: RequestInit };
let calls: Call[];
let responseJob: JobSnapshot;
let responsePlan: DeploymentPlan;
let responseEvents: JobEvent[];
let responseCatalog: Catalog;
let responseArtifact: Record<string, unknown>;
let importFails: boolean;
let importUnverified: boolean;
let jobReadFails: boolean;
let jobReadHangs: boolean;
const trustedBundle = { schema_version: 1, filename: 'ros-probe.bundle.tar', sha256: 'd'.repeat(64), size_bytes: 4, source: 'd1env/ros-probe', image_id: softwareProfile.artifact_requirements[0].immutable_id, architecture: 'aarch64' };

beforeEach(() => {
  calls = []; responseJob = softwareJob; responsePlan = softwarePlan; responseEvents = softwareEvents; responseCatalog = softwareCatalog;
  responseArtifact = { trusted_bundle: trustedBundle, blocked_reason: null }; importFails = false; importUnverified = false;
  jobReadFails = false; jobReadHangs = false;
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    calls.push({ path, init });
    if (path === `/api/jobs/${softwareJob.job_id}` && jobReadFails) return new Response(JSON.stringify({ detail: { code: 'SESSION_REQUIRED', message: '本地会话已失效', remediation: '从启动入口重新打开工作台' } }), { status: 401 });
    if (path === `/api/jobs/${softwareJob.job_id}` && jobReadHangs) return new Promise<Response>(() => undefined);
    if (path === '/api/artifacts/ros-probe/import' && importFails) return new Response(JSON.stringify({ detail: 'IMPORT_DIGEST_MISMATCH: 镜像包校验失败，请选择完整发行包' }), { status: 409 });
    const value = path === '/api/session' ? { csrf_token: 'test-software-csrf', mode: 'mock' }
      : path === '/api/catalog' ? responseCatalog
      : path === '/api/doctor' ? softwareDoctor
      : path === '/api/plans' ? { plan: responsePlan, blockers: [] }
      : path === '/api/jobs' && init?.method !== 'POST' ? [responseJob]
      : path === '/api/artifacts/ros-probe' ? responseArtifact
      : path === '/api/artifacts/ros-probe/import' ? { status: 'imported', image_id: importUnverified ? `sha256:${'e'.repeat(64)}` : trustedBundle.image_id, architecture: trustedBundle.architecture, software_scope_only: true }
      : path.endsWith('/plan') ? responsePlan
      : path.endsWith('/events') ? responseEvents
      : path.endsWith('/stop') ? { ...responseJob, state: 'CANCELLED' }
      : path === '/api/reports' ? { report: { schema_version: 1, mode: 'software_test', verified_scope: 'software', job: responseJob, checks: softwareDoctor.checks, events: responseEvents, source_locks: {}, unverified_items: ['D1 真机未验证'], redactions: [] }, markdown: '# 真实软件测试报告' }
      : responseJob;
    return new Response(JSON.stringify(value), { status: 200, headers: { 'Content-Type': 'application/json' } });
  }));
});
afterEach(() => vi.useRealTimers());

async function softwarePreview() {
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole('button', { name: /真实软件测试（Docker\/ROS，未接真机）/ }));
  await user.click(screen.getByRole('button', { name: '下一步：机器人配置' }));
  expect(screen.getByRole('button', { name: /选择 D1 点足候选/ })).toBeDisabled();
  expect(screen.getByRole('button', { name: /选择 软件演示/ })).toBeDisabled();
  await user.click(screen.getByRole('button', { name: '下一步：执行电脑' }));
  await user.click(await screen.findByRole('button', { name: '下一步：部署预览' }));
  return user;
}

async function softwareHost() {
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole('button', { name: /真实软件测试（Docker\/ROS，未接真机）/ }));
  await user.click(screen.getByRole('button', { name: '下一步：机器人配置' }));
  await user.click(screen.getByRole('button', { name: '下一步：执行电脑' }));
  await screen.findByRole('button', { name: '下一步：部署预览' });
  return user;
}

describe('M3 软件模式的真实范围与生命周期', () => {
  it('选择软件模式只解析软件配置，预览工件和内部网络，硬件与遥测保持未验证', async () => {
    await softwarePreview();
    expect(await screen.findByRole('button', { name: '启动真实软件测试' })).toBeEnabled();
    expect(screen.getByTestId('mode-watermark')).toHaveTextContent('真实软件测试');
    expect(screen.getByTestId('telemetry-state')).toHaveTextContent('UNKNOWN');
    expect(screen.getByTestId('battery-value')).toHaveTextContent('未知');
    expect(screen.getByText('d1env/ros-probe')).toBeVisible();
    expect(screen.getByText(/项目内部网络/)).toBeVisible();
    expect(screen.getByText(/Docker.*高权限/)).toBeVisible();
    const requested = calls.find((call) => call.path === '/api/plans');
    expect(JSON.parse(String(requested?.init?.body))).toMatchObject({ mode: 'software_test', profile_id: 'ros-probe', task: 'ros_probe', probe_scenario: 'success' });
  });

  it('真实软件成功显示 software 范围并通过认证停止当前服务，停止不是机器人急停', async () => {
    const user = await softwarePreview();
    fireEvent.click(screen.getByRole('button', { name: '启动真实软件测试' }));
    fireEvent.click(screen.getByRole('button', { name: '启动真实软件测试' }));
    expect(await screen.findByRole('heading', { name: '软件环境检查通过，未连接真机' })).toBeVisible();
    expect(screen.getByTestId('verified-scope')).toHaveTextContent('software');
    expect(calls.filter((call) => call.path === '/api/jobs')).toHaveLength(1);
    expect(screen.queryByText('演示流程完成（MOCK），未部署真机')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '停止测试服务' }));
    expect(await screen.findByTestId('job-state')).toHaveTextContent('CANCELLED');
    const stop = calls.find((call) => call.path === '/api/jobs/software-job-1/stop');
    expect(stop?.init?.method).toBe('POST');
    expect(new Headers(stop?.init?.headers).get('X-CSRF-Token')).toBe('test-software-csrf');
    expect(screen.getByText(/软件停止请求不等于硬件急停/)).toBeVisible();
  });

  it('刷新软件故障作业恢复原模式与故障场景，重新预览保留原始请求', async () => {
    localStorage.setItem('d1env.currentJob', softwareJob.job_id);
    responseJob = { ...softwareJob, state: 'FAILED', error_code: 'ROS_NO_MESSAGES' };
    responsePlan = { ...softwarePlan, request: { ...softwarePlan.request, probe_scenario: 'no_publisher' } };
    responseEvents = [{ ...softwareEvents[0], event_type: 'failed', message: '故障注入：无发布者，未收到消息', evidence: { fault_injection: true, fresh_messages: false } }];
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByTestId('mode-watermark')).toHaveTextContent('真实软件测试');
    await screen.findByRole('button', { name: '重新预览软件计划' });
    expect(screen.getByText('故障注入测试 · 无发布者')).toBeVisible();
    await user.click(screen.getByRole('button', { name: '重新预览软件计划' }));
    await screen.findByRole('button', { name: '启动真实软件测试' });
    await waitFor(() => expect(calls.some((call) => call.path === '/api/plans')).toBe(true));
    const requested = calls.find((call) => call.path === '/api/plans');
    expect(JSON.parse(String(requested?.init?.body))).toMatchObject({ mode: 'software_test', profile_id: 'ros-probe', task: 'ros_probe', probe_scenario: 'no_publisher' });
    expect(calls.filter((call) => call.path === '/api/jobs')).toHaveLength(0);
  });

  it('恢复后直接重试软件故障使用原始计划，不自动降级 MOCK', async () => {
    localStorage.setItem('d1env.currentJob', softwareJob.job_id);
    responseJob = { ...softwareJob, state: 'INTERRUPTED', error_code: 'WORKER_INTERRUPTED' };
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole('button', { name: '重试真实软件测试' }));
    await waitFor(() => expect(calls.filter((call) => call.path === '/api/jobs')).toHaveLength(1));
    expect(JSON.parse(String(calls.find((call) => call.path === '/api/jobs')?.init?.body)).plan_id).toBe(softwarePlan.plan_id);
    expect(calls.filter((call) => call.path === '/api/plans')).toHaveLength(0);
  });

  it('software SUCCEEDED 每三秒复核，资源消失撤销成功，400ms 不触发高成本探针', async () => {
    localStorage.setItem('d1env.currentJob', softwareJob.job_id);
    vi.useFakeTimers();
    render(<App />);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(screen.getByRole('heading', { name: '软件环境检查通过，未连接真机' })).toBeVisible();
    const reads = calls.filter((call) => call.path === `/api/jobs/${softwareJob.job_id}`).length;
    await act(async () => { await vi.advanceTimersByTimeAsync(400); });
    expect(calls.filter((call) => call.path === `/api/jobs/${softwareJob.job_id}`).length).toBe(reads);
    responseJob = { ...softwareJob, state: 'FAILED', error_code: 'SOFTWARE_HEALTH_LOST' };
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    expect(screen.getByTestId('job-state')).toHaveTextContent('FAILED');
    expect(screen.queryByRole('heading', { name: '软件环境检查通过，未连接真机' })).not.toBeInTheDocument();
  });

  it('没有软件配置时明确阻塞，不能沿用 MOCK 配置执行', async () => {
    responseCatalog = catalog;
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole('button', { name: /真实软件测试（Docker\/ROS，未接真机）/ }));
    await user.click(screen.getByRole('button', { name: '下一步：机器人配置' }));
    expect(screen.getByText(/尚无可执行的软件配置/)).toBeVisible();
    expect(screen.getByRole('button', { name: '下一步：执行电脑' })).toBeDisabled();
    expect(calls.filter((call) => call.path === '/api/jobs')).toHaveLength(0);
  });

  it('历史成功无法复核时显示当前 UNKNOWN 与 TARGET_BUSY，不沿用绿色通信成功', async () => {
    localStorage.setItem('d1env.currentJob', softwareJob.job_id);
    responseJob = { ...softwareJob, current_software_ready: null, current_health_evidence: { error_code: 'TARGET_BUSY', message: '另一个作业占用目标锁，本次未复核当前服务' } };
    render(<App />);
    expect(await screen.findByRole('heading', { name: '部署曾完成，当前软件状态未知' })).toBeVisible();
    expect(document.querySelector('.result-symbol')).not.toHaveTextContent('✓');
    expect(screen.getByText('TARGET_BUSY')).toBeVisible();
    expect(screen.queryByText('新鲜度检查通过')).not.toBeInTheDocument();
    expect(screen.getByTestId('telemetry-state')).toHaveTextContent('UNKNOWN');
  });

  it('随包镜像导入只提交原始文件并携带 CSRF，成功仅表示软件镜像已导入', async () => {
    const user = await softwareHost();
    const button = await screen.findByRole('button', { name: '导入随发行包提供的 ROS 软件镜像' });
    expect(button).toBeDisabled();
    const file = new File(['data'], trustedBundle.filename, { type: 'application/octet-stream' });
    await user.upload(screen.getByLabelText('随包 ROS 镜像文件'), file);
    await user.click(button);
    expect(await screen.findByText('软件镜像已导入；还需启动测试并检查 ROS 通信。')).toBeVisible();
    const imported = calls.find((call) => call.path === '/api/artifacts/ros-probe/import');
    expect(imported?.init?.body).toBe(file);
    expect(imported?.init?.credentials).toBe('same-origin');
    expect(new Headers(imported?.init?.headers).get('Content-Type')).toBe('application/octet-stream');
    expect(new Headers(imported?.init?.headers).get('X-CSRF-Token')).toBe('test-software-csrf');
    expect(calls.filter((call) => call.path === '/api/jobs')).toHaveLength(0);
    expect(screen.getByTestId('telemetry-state')).toHaveTextContent('UNKNOWN');
  });

  it('没有受信发行元数据时文件选择和导入均禁用并说明原因', async () => {
    responseArtifact = { trusted_bundle: null, blocked_reason: '缺少匹配的发行元数据，不能导入任意镜像' };
    await softwareHost();
    expect(await screen.findByText('缺少匹配的发行元数据，不能导入任意镜像')).toBeVisible();
    expect(screen.getByLabelText('随包 ROS 镜像文件')).toBeDisabled();
    expect(screen.getByRole('button', { name: '导入随发行包提供的 ROS 软件镜像' })).toBeDisabled();
    expect(calls.filter((call) => call.path === '/api/artifacts/ros-probe/import')).toHaveLength(0);
  });

  it('镜像校验错误按原文展示具体错误与下一步，不能显示导入成功', async () => {
    importFails = true;
    const user = await softwareHost();
    await user.upload(await screen.findByLabelText('随包 ROS 镜像文件'), new File(['data'], trustedBundle.filename));
    await user.click(screen.getByRole('button', { name: '导入随发行包提供的 ROS 软件镜像' }));
    expect(await screen.findByText('IMPORT_DIGEST_MISMATCH')).toBeVisible();
    expect(screen.getByRole('alert')).toHaveTextContent('镜像包校验失败');
    expect(screen.getByRole('alert')).toHaveTextContent('下一步');
    expect(screen.queryByText('软件镜像已导入；还需启动测试并检查 ROS 通信。')).not.toBeInTheDocument();
  });

  it('导入返回非发行镜像身份时不推断成功', async () => {
    importUnverified = true;
    const user = await softwareHost();
    await user.upload(await screen.findByLabelText('随包 ROS 镜像文件'), new File(['data'], trustedBundle.filename));
    await user.click(screen.getByRole('button', { name: '导入随发行包提供的 ROS 软件镜像' }));
    expect(await screen.findByText('IMPORT_RESULT_UNVERIFIED')).toBeVisible();
    expect(screen.queryByText('软件镜像已导入；还需启动测试并检查 ROS 通信。')).not.toBeInTheDocument();
  });

  it('终态作业后更改验证范围会开始新配置，不把旧软件结果混在 MOCK 标识下', async () => {
    localStorage.setItem('d1env.currentJob', softwareJob.job_id);
    responseJob = { ...softwareJob, state: 'FAILED', error_code: 'ROS_NO_MESSAGES' };
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole('button', { name: '重试真实软件测试' });
    await user.click(screen.getByRole('button', { name: '1 使用方式' }));
    await user.click(screen.getByRole('button', { name: /软件演示体验/ }));
    await user.click(screen.getByRole('button', { name: '5 运行与结果' }));
    expect(screen.queryByTestId('job-id')).not.toBeInTheDocument();
    expect(screen.getByTestId('mode-watermark')).toHaveTextContent('MOCK');
    expect(screen.getByTestId('verified-scope')).toHaveTextContent('mock');
    expect(localStorage.getItem('d1env.currentJob')).toBeNull();
    expect(calls.filter((call) => call.path === '/api/jobs')).toHaveLength(0);
  });

  it('软件当前健康读取失去会话时立即降级 UNKNOWN，保留历史成功与步骤证据', async () => {
    localStorage.setItem('d1env.currentJob', softwareJob.job_id);
    vi.useFakeTimers();
    render(<App />);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(screen.getByRole('heading', { name: '软件环境检查通过，未连接真机' })).toBeVisible();
    jobReadFails = true;
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    expect(screen.getByRole('heading', { name: '部署曾完成，当前软件状态未知' })).toBeVisible();
    expect(screen.getByText('CURRENT_HEALTH_UNAVAILABLE')).toBeVisible();
    expect(screen.getByTestId('job-state')).toHaveTextContent('SUCCEEDED');
    expect(screen.getByText('测试节点已接收新鲜 ROS 消息')).toBeVisible();
    expect(screen.queryByText('新鲜度检查通过')).not.toBeInTheDocument();
  });

  it('软件健康请求挂起时五秒有效期后降级 UNKNOWN，不无限保留绿色状态', async () => {
    localStorage.setItem('d1env.currentJob', softwareJob.job_id);
    vi.useFakeTimers();
    render(<App />);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    jobReadHangs = true;
    await act(async () => { await vi.advanceTimersByTimeAsync(5100); });
    expect(screen.getByRole('heading', { name: '部署曾完成，当前软件状态未知' })).toBeVisible();
    expect(screen.getByText('CURRENT_HEALTH_EXPIRED')).toBeVisible();
    expect(document.querySelector('.result-symbol')).not.toHaveTextContent('✓');
  });

  it.each(['FAILED', 'INTERRUPTED'] as const)('软件 %s 可显式清理本作业遗留服务，再重试原计划', async (state) => {
    localStorage.setItem('d1env.currentJob', softwareJob.job_id);
    responseJob = { ...softwareJob, state, error_code: 'CLEANUP_INCOMPLETE' };
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole('button', { name: '清理本作业遗留服务' }));
    expect(await screen.findByTestId('job-state')).toHaveTextContent('CANCELLED');
    expect(calls.find((call) => call.path === `/api/jobs/${softwareJob.job_id}/stop`)?.init?.method).toBe('POST');
    await user.click(screen.getByRole('button', { name: '重试真实软件测试' }));
    await waitFor(() => expect(calls.filter((call) => call.path === '/api/jobs' && call.init?.method === 'POST')).toHaveLength(1));
    expect(JSON.parse(String(calls.find((call) => call.path === '/api/jobs' && call.init?.method === 'POST')?.init?.body)).plan_id).toBe(softwarePlan.plan_id);
  });

  it('从历史软件作业入口恢复已移除的指针，同步原范围与故障场景并可清理', async () => {
    responseJob = { ...softwareJob, state: 'FAILED', error_code: 'CLEANUP_INCOMPLETE' };
    responsePlan = { ...softwarePlan, request: { ...softwarePlan.request, probe_scenario: 'no_publisher' } };
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole('button', { name: '查看历史软件作业' }));
    await user.click(await screen.findByRole('button', { name: `恢复软件作业 ${softwareJob.job_id}` }));
    expect(await screen.findByTestId('job-id')).toHaveTextContent(softwareJob.job_id);
    expect(screen.getByTestId('mode-watermark')).toHaveTextContent('真实软件测试');
    expect(screen.getByText('故障注入测试 · 无发布者')).toBeVisible();
    expect(localStorage.getItem('d1env.currentJob')).toBe(softwareJob.job_id);
    expect(calls.filter((call) => call.path === '/api/jobs' && call.init?.method === 'POST')).toHaveLength(0);
    await user.click(screen.getByRole('button', { name: '清理本作业遗留服务' }));
    expect(await screen.findByTestId('job-state')).toHaveTextContent('CANCELLED');
  });
});
