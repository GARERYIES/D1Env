import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../../src/App';
import { catalog, doctor, failedJob, failureEvents, job, maliciousMessage, plan } from './fixtures';

type Call = { path: string; init?: RequestInit };
let calls: Call[];
let jobResponse: typeof job;
let eventsResponse: unknown[];
let blocked = false;

beforeEach(() => {
  calls = [];
  jobResponse = job;
  eventsResponse = [];
  blocked = false;
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path === '/api/session/bootstrap') expect(window.location.hash).toBe('');
    calls.push({ path, init });
    const value = path === '/api/session' || path === '/api/session/bootstrap' ? { csrf_token: 'test-csrf', mode: 'mock' }
      : path === '/api/catalog' ? catalog
      : path === '/api/doctor' ? doctor
      : path === '/api/plans' ? blocked ? { plan: null, blockers: [{ code: 'ARTIFACT_UNAVAILABLE', message: '没有可执行工件', remediation: '等待来源与实现验证', field: 'artifact_requirements' }] } : { plan, blockers: [] }
      : path.endsWith('/plan') ? { ...plan, plan_id: jobResponse.plan_id }
      : path.endsWith('/events') ? eventsResponse
      : path === '/api/reports' ? { report: { schema_version: 1, mode: 'mock', verified_scope: 'mock', job: jobResponse, checks: doctor.checks, events: eventsResponse, source_locks: {}, unverified_items: ['真机未验证'], redactions: ['标识已遮盖'] }, markdown: '# MOCK 诊断报告' }
      : jobResponse;
    return new Response(JSON.stringify(value), { status: 200, headers: { 'Content-Type': 'application/json' } });
  }));
});

async function toPreview() {
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole('button', { name: '下一步：机器人配置' }));
  await user.click(screen.getByRole('button', { name: '下一步：执行电脑' }));
  await user.click(await screen.findByRole('button', { name: '下一步：部署预览' }));
  return user;
}

describe('中文向导与证据边界', () => {
  it('五步可导航、每个视图保留 MOCK，真实选项禁用并解释能力证据', async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole('button', { name: '下一步：机器人配置' });
    expect(screen.getByRole('button', { name: /真实机器人只读/ })).toBeDisabled();
    for (const name of ['使用方式', '机器人配置', '执行电脑', '部署预览', '运行与结果']) {
      await user.click(screen.getByRole('button', { name: new RegExp(`^\\d+ ${name}$`) }));
      expect(screen.getByTestId('mock-watermark')).toHaveTextContent('MOCK');
    }
    await user.click(screen.getByRole('button', { name: '2 机器人配置' }));
    expect(screen.getByRole('button', { name: /选择 D1 点足候选/ })).toBeDisabled();
    expect(screen.getByText('documented')).toBeVisible();
    expect(screen.getByText('not_implemented')).toBeVisible();
    expect(screen.getByText(/固件范围、工件、ABI 与遥测语义未验证/)).toBeVisible();
  });

  it('服务端缺失遥测保持 UNKNOWN 和未知，不显示正常或虚构百分比', async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole('button', { name: '3 执行电脑' }));
    expect(await screen.findByTestId('battery-value')).toHaveTextContent('未知');
    expect(screen.getByTestId('pose-value')).toHaveTextContent('未知');
    expect(screen.getByTestId('telemetry-state')).toHaveTextContent('UNKNOWN');
    expect(screen.queryByText('正常')).not.toBeInTheDocument();
    expect(screen.queryByText('82%')).not.toBeInTheDocument();
    expect(screen.getByText(/Darwin/)).toBeVisible();
    expect(screen.getByText('来源：local_probe · 后端本机观测')).toBeVisible();
  });

  it('引导令牌在网络前从 fragment 清除，业务写入携带 CSRF 且不信任浏览器 HostFacts', async () => {
    window.history.replaceState(null, '', '/#bootstrap=private-test-token');
    const user = await toPreview();
    expect(window.location.hash).toBe('');
    expect(calls[0].path).toBe('/api/session/bootstrap');
    expect(calls[0].init?.body).toBe(JSON.stringify({ token: 'private-test-token' }));
    await user.click(screen.getByRole('button', { name: '开始 MOCK 演示' }));
    await screen.findByText(/演示流程完成（MOCK），未部署真机/);
    for (const call of calls.filter((item) => item.init?.method === 'POST' && item.path !== '/api/session/bootstrap')) {
      expect(call.init?.credentials).toBe('same-origin');
      expect(new Headers(call.init?.headers).get('X-CSRF-Token')).toBe('test-csrf');
      expect(call.init?.body).not.toContain('docker_available');
    }
    expect(localStorage.getItem('d1env.currentJob')).toBe('job-1');
  });

  it('连续点击只提交一个作业，结果明确限定为 mock', async () => {
    await toPreview();
    const start = screen.getByRole('button', { name: '开始 MOCK 演示' });
    fireEvent.click(start);
    fireEvent.click(start);
    await screen.findByText(/演示流程完成（MOCK），未部署真机/);
    expect(calls.filter((call) => call.path === '/api/jobs')).toHaveLength(1);
    expect(screen.getByTestId('verified-scope')).toHaveTextContent('mock');
    expect(screen.getByRole('button', { name: /运动控制未启用/ })).toBeDisabled();
  });

  it('服务端阻塞计划时不能执行，显示错误码和下一步操作', async () => {
    blocked = true;
    await toPreview();
    expect(await screen.findByText('ARTIFACT_UNAVAILABLE')).toBeVisible();
    expect(screen.getByText('没有可执行工件')).toBeVisible();
    expect(screen.getByText('等待来源与实现验证')).toBeVisible();
    expect(screen.getByRole('button', { name: '开始 MOCK 演示' })).toBeDisabled();
  });

  it('失败后的显式重试使用新幂等键，不复用旧失败作业', async () => {
    jobResponse = failedJob;
    eventsResponse = failureEvents;
    const user = await toPreview();
    await user.click(screen.getByRole('button', { name: '开始 MOCK 演示' }));
    await screen.findByRole('button', { name: '重试 MOCK 演示' });
    await user.click(screen.getByRole('button', { name: '重试 MOCK 演示' }));
    await waitFor(() => expect(calls.filter((call) => call.path === '/api/jobs')).toHaveLength(2));
    const keys = calls.filter((call) => call.path === '/api/jobs').map((call) => JSON.parse(String(call.init?.body)).idempotency_key);
    expect(keys[0]).not.toBe(keys[1]);
  });

  it('恢复中断的作业后重试原始计划，不把故障计划改成默认成功场景', async () => {
    localStorage.setItem('d1env.currentJob', 'job-1');
    jobResponse = { ...job, plan_id: 'saved-fault-injection-plan', state: 'INTERRUPTED', error_code: 'WORKER_INTERRUPTED' };
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole('button', { name: '重试 MOCK 演示' }));
    await waitFor(() => expect(calls.filter((call) => call.path === '/api/jobs')).toHaveLength(1));
    const submitted = calls.find((call) => call.path === '/api/jobs');
    expect(JSON.parse(String(submitted?.init?.body)).plan_id).toBe('saved-fault-injection-plan');
    expect(calls.filter((call) => call.path === '/api/plans')).toHaveLength(0);
  });

  it('取消仅提交当前作业的取消请求，终态停止显示取消按钮', async () => {
    jobResponse = { ...job, state: 'PREFLIGHT' };
    const user = await toPreview();
    await user.click(screen.getByRole('button', { name: '开始 MOCK 演示' }));
    const cancel = await screen.findByRole('button', { name: '取消本次演示' });
    jobResponse = { ...job, state: 'CANCELLED' };
    await user.click(cancel);
    expect(await screen.findByTestId('job-state')).toHaveTextContent('CANCELLED');
    expect(screen.queryByRole('button', { name: '取消本次演示' })).not.toBeInTheDocument();
    expect(document.querySelector('.result-symbol')).not.toHaveTextContent('✓');
    expect(calls.filter((call) => call.path === '/api/jobs/job-1/cancel')).toHaveLength(1);
  });

  it('会话被拒绝时显示环节、证据与下一步，不能进入执行流程', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'SESSION_REQUIRED' }), { status: 401 })));
    render(<App />);
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('SESSION_REQUIRED');
    expect(alert).toHaveTextContent('检测证据');
    expect(alert).toHaveTextContent('下一步');
    expect(screen.queryByRole('button', { name: '开始 MOCK 演示' })).not.toBeInTheDocument();
  });

  it('切换演示场景后丢弃迟到的旧计划，执行与当前预览场景一致', async () => {
    const originalFetch = globalThis.fetch;
    let resolveOld: (response: Response) => void = () => undefined;
    const held = new Promise<Response>((resolve) => { resolveOld = resolve; });
    let first = true;
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) === '/api/plans' && first) {
        first = false;
        calls.push({ path: String(input), init });
        return held;
      }
      return originalFetch(input, init);
    }));
    const user = await toPreview();
    await user.click(screen.getByRole('button', { name: '1 使用方式' }));
    await user.selectOptions(screen.getByLabelText('演示场景'), 'verify_failure');
    await user.click(screen.getByRole('button', { name: '4 部署预览' }));
    resolveOld(new Response(JSON.stringify({ plan, blockers: [] }), { status: 200 }));
    await waitFor(() => expect(calls.filter((call) => call.path === '/api/plans')).toHaveLength(2));
    const latest = calls.filter((call) => call.path === '/api/plans').at(-1);
    expect(JSON.parse(String(latest?.init?.body)).demo_scenario).toBe('verify_failure');
  });

  it('导出默认遮盖用户标识，用户可选择保留 IP 与序列号，凭据始终去敏', async () => {
    const user = await toPreview();
    await user.click(screen.getByRole('button', { name: '开始 MOCK 演示' }));
    const mask = await screen.findByRole('checkbox', { name: '遮盖 IP / 序列号' });
    expect(mask).toBeChecked();
    await user.click(mask);
    await user.click(screen.getByRole('button', { name: '生成去敏诊断报告' }));
    await screen.findByRole('button', { name: '下载 JSON' });
    const body = JSON.parse(String(calls.find((call) => call.path === '/api/reports')?.init?.body));
    expect(body.mask_identifiers).toBe(false);
    expect(screen.getByText(/未请求遮盖用户标识/)).toBeVisible();
    expect(screen.getByText(/凭据始终去敏/)).toBeVisible();
  });

  it('刷新恢复现有作业并以纯文本显示故障证据，重试使用新幂等键', async () => {
    localStorage.setItem('d1env.currentJob', 'job-1');
    jobResponse = failedJob;
    eventsResponse = failureEvents;
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText(maliciousMessage)).toBeVisible();
    expect(document.querySelector('script')).toBeNull();
    expect(screen.getByText('MOCK_READINESS_FAILED')).toBeVisible();
    expect(screen.getByText('下一步：检查演示故障注入设置后重试')).toBeVisible();
    expect(calls.filter((call) => call.path === '/api/jobs')).toHaveLength(0);
    const reportButton = screen.getByRole('button', { name: '生成去敏诊断报告' });
    await user.click(reportButton);
    expect(await screen.findByRole('button', { name: '下载 JSON' })).toBeEnabled();
    expect(screen.getByRole('button', { name: '下载 Markdown' })).toBeEnabled();
    await user.click(screen.getByRole('button', { name: '重试 MOCK 演示' }));
    await waitFor(() => expect(calls.filter((call) => call.path === '/api/jobs')).toHaveLength(1));
    const body = JSON.parse(String(calls.find((call) => call.path === '/api/jobs')?.init?.body));
    expect(body.idempotency_key).toBeTruthy();
  });
});
