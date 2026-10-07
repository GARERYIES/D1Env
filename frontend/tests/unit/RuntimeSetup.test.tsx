import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../../src/App';
import { catalog, doctor } from './fixtures';

// HTTP fixtures exercise the UI contract only, never an installed Docker runtime.
const softwareCatalog = { ...catalog, profiles: [...catalog.profiles, {
  ...catalog.profiles[0], profile_id: 'ros-probe', name: 'CPU ROS 通信测试', kind: 'software',
  capabilities: { ros_probe: { status: 'implemented', declared_by_vendor: false, evidence_refs: ['unit-fixture'], reason: '仅软件测试' } },
}] };
const task = {
  task_id: 'runtime-task-1', request_key: 'unit-request-key', scope: 'runtime_environment',
  state: 'WAITING_USER', stage: 'license', updated_at: '2026-10-07T04:00:00Z',
  environment_ready: false, user_action: 'accept_license',
  evidence: { installer_verified: true, source: 'unit-fixture' }, events: [],
  message: '下载前请阅读 Docker 许可条件并确认适用性。',
  remediation: '阅读许可后点击明确确认按钮。', error_code: null,
};
const runtimeStatus = {
  environment_ready: false, task: null, platform: { os: 'Darwin', architecture: 'aarch64', supported: true },
  installer: { version: 'unit-version', sha256: 'a'.repeat(64), size_bytes: 100, license_url: 'https://www.docker.com/legal/docker-subscription-service-agreement/', blocked_reason: null },
  evidence: { docker_available: false, docker_accessible: false, compose_available: false, companion_bundle_available: true },
  message: '尚未准备本机容器运行环境。', remediation: '点击准备运行环境，由应用检测和准备。', observed_at: '2026-10-07T04:00:00Z',
};
type Call = { path: string; init?: RequestInit };
let calls: Call[];
let statusResponse: Record<string, unknown>;
let taskResponse: Record<string, unknown>;
let taskReadsFail: boolean;
let prepareFails: boolean;
let statusReadsFail: boolean;

beforeEach(() => {
  calls = []; statusResponse = runtimeStatus; taskResponse = task; taskReadsFail = false; prepareFails = false; statusReadsFail = false;
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input); calls.push({ path, init });
    if (path === '/api/runtime/prepare' && prepareFails) throw new TypeError('controlled network failure');
    if (path === '/api/runtime/status' && statusReadsFail) throw new TypeError('controlled network failure');
    if (path === '/api/runtime/tasks/runtime-task-1' && taskReadsFail) throw new TypeError('controlled network failure');
    const value = path === '/api/session' ? { csrf_token: 'ui-runtime-unit-fixture', mode: 'mock' }
      : path === '/api/catalog' ? softwareCatalog
      : path === '/api/doctor' ? doctor
      : path === '/api/artifacts/ros-probe' ? { trusted_bundle: null, blocked_reason: 'unit fixture without image bundle' }
      : path === '/api/runtime/status' ? statusResponse
      : path === '/api/runtime/prepare' || path === '/api/runtime/tasks/runtime-task-1' ? taskResponse
      : path.endsWith('/continue') ? taskResponse
      : path.endsWith('/cancel') ? { ...taskResponse, state: 'CANCELLED', user_action: null, environment_ready: false }
      : {};
    return new Response(JSON.stringify(value), { status: 200, headers: { 'Content-Type': 'application/json' } });
  }));
});
afterEach(() => vi.useRealTimers());

async function softwareHost() {
  const user = userEvent.setup(); render(<App />);
  await user.click(await screen.findByRole('button', { name: /真实软件测试（Docker\/ROS，未接真机）/ }));
  await user.click(screen.getByRole('button', { name: '下一步：机器人配置' }));
  await user.click(screen.getByRole('button', { name: '下一步：执行电脑' }));
  await screen.findByRole('button', { name: '准备运行环境' });
  return user;
}

describe('首次运行环境准备的许可与可信状态', () => {
  it('MOCK 执行电脑页只读检测，不出现运行环境准备也不发准备请求', async () => {
    const user = userEvent.setup(); render(<App />);
    await user.click(await screen.findByRole('button', { name: '3 执行电脑' }));
    await screen.findByText(/Darwin/);
    expect(screen.queryByRole('button', { name: '准备运行环境' })).not.toBeInTheDocument();
    expect(calls.filter((call) => call.path.startsWith('/api/runtime/'))).toHaveLength(0);
  });

  it('重复准备点击只提交一个带 CSRF 的固定请求，许可不自动接受', async () => {
    await softwareHost();
    const prepare = screen.getByRole('button', { name: '准备运行环境' });
    fireEvent.click(prepare); fireEvent.click(prepare);
    expect(await screen.findByRole('button', { name: '已阅读许可并确认适用，继续准备' })).toBeVisible();
    const posts = calls.filter((call) => call.path === '/api/runtime/prepare');
    expect(posts).toHaveLength(1);
    const body = JSON.parse(String(posts[0].init?.body));
    expect(Object.keys(body)).toEqual(['request_key']);
    expect(body.request_key).toBeTruthy();
    expect(new Headers(posts[0].init?.headers).get('X-CSRF-Token')).toBe('ui-runtime-unit-fixture');
    expect(calls.filter((call) => call.path.endsWith('/continue'))).toHaveLength(0);
    expect(localStorage.getItem('d1env.currentRuntimePrepare')).toBe('runtime-task-1');
    expect(screen.getByTestId('telemetry-state')).toHaveTextContent('UNKNOWN');
  });

  it('只有明确许可按钮提交 accept_license，原生安装等待仅复核且不收密码', async () => {
    const user = await softwareHost();
    await user.click(screen.getByRole('button', { name: '准备运行环境' }));
    expect(await screen.findByRole('link', { name: '阅读 Docker 许可条件' })).toHaveAttribute('href', runtimeStatus.installer.license_url);
    taskResponse = { ...task, state: 'WAITING_USER', stage: 'native_setup', user_action: 'check_again', message: '请在 Docker 原生界面完成系统授权。' };
    await user.click(screen.getByRole('button', { name: '已阅读许可并确认适用，继续准备' }));
    expect(await screen.findByRole('button', { name: '已完成原生提示，重新检查' })).toBeVisible();
    expect(screen.queryByLabelText(/密码/)).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '已完成原生提示，重新检查' }));
    const actions = calls.filter((call) => call.path.endsWith('/continue')).map((call) => JSON.parse(String(call.init?.body)));
    expect(actions).toEqual([{ action: 'accept_license' }, { action: 'check_again' }]);
    expect(calls.filter((call) => call.path === '/api/jobs')).toHaveLength(0);
  });

  it('刷新准备任务只恢复软件范围并读取，不再次准备或自动接受许可', async () => {
    localStorage.setItem('d1env.currentRuntimePrepare', 'runtime-task-1');
    statusResponse = { ...runtimeStatus, task };
    render(<App />);
    expect(await screen.findByRole('button', { name: '已阅读许可并确认适用，继续准备' })).toBeVisible();
    expect(screen.getByTestId('mode-watermark')).toHaveTextContent('真实软件测试');
    expect(calls.some((call) => call.path === '/api/runtime/tasks/runtime-task-1')).toBe(true);
    expect(calls.filter((call) => call.init?.method === 'POST' && call.path.startsWith('/api/runtime/'))).toHaveLength(0);
  });

  it('已准备仅指运行环境与镜像，自动重查电脑但不会启动 ROS 或显示真机正常', async () => {
    taskResponse = { ...task, state: 'SUCCEEDED', stage: 'complete', user_action: null, environment_ready: true, message: '运行环境和配套软件镜像已准备。', evidence: { docker_accessible: true, compose_available: true, image_imported: true } };
    const user = await softwareHost();
    const previousDoctorReads = calls.filter((call) => call.path === '/api/doctor').length;
    await user.click(screen.getByRole('button', { name: '准备运行环境' }));
    expect(await screen.findByText('运行环境已准备；尚未启动 ROS 通信检查。')).toBeVisible();
    await waitFor(() => expect(calls.filter((call) => call.path === '/api/doctor').length).toBeGreaterThan(previousDoctorReads));
    expect(screen.getByTestId('telemetry-state')).toHaveTextContent('UNKNOWN');
    expect(screen.queryByRole('heading', { name: '软件环境检查通过，未连接真机' })).not.toBeInTheDocument();
    expect(calls.filter((call) => call.path === '/api/jobs')).toHaveLength(0);
  });

  it('伪成功与未知平台无法显示环境已准备，错误带证据和下一步', async () => {
    taskResponse = { ...task, state: 'SUCCEEDED', stage: 'complete', user_action: null, environment_ready: null, error_code: 'PREPARATION_EVIDENCE_MISSING', message: '没有当前 Docker 与镜像证据。', remediation: '重新检查运行环境。' };
    const user = await softwareHost();
    await user.click(screen.getByRole('button', { name: '准备运行环境' }));
    expect(await screen.findByText('PREPARATION_EVIDENCE_MISSING')).toBeVisible();
    expect(screen.queryByText('运行环境已准备；尚未启动 ROS 通信检查。')).not.toBeInTheDocument();
    expect(screen.getByTestId('runtime-current-state')).toHaveTextContent('UNKNOWN');
  });

  it('平台或可信安装来源被阻塞时禁止准备，不接任意来源输入', async () => {
    statusResponse = { ...runtimeStatus, platform: { os: 'Unknown', architecture: null, supported: false }, installer: { ...runtimeStatus.installer, blocked_reason: '未核到此平台的可信安装包。' }, message: '当前平台未支持。', remediation: '使用已验证的 Mac aarch64 候选。' };
    await softwareHost();
    expect(screen.getByRole('button', { name: '准备运行环境' })).toBeDisabled();
    expect(screen.getByText('未核到此平台的可信安装包。')).toBeVisible();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });

  it('准备响应丢失后显式重试复用同一个请求键，不重复提交新任务', async () => {
    prepareFails = true;
    const user = await softwareHost();
    await user.click(screen.getByRole('button', { name: '准备运行环境' }));
    await screen.findByText('LOCAL_API_UNREACHABLE');
    prepareFails = false;
    await user.click(screen.getByRole('button', { name: '准备运行环境' }));
    await screen.findByRole('button', { name: '已阅读许可并确认适用，继续准备' });
    const keys = calls.filter((call) => call.path === '/api/runtime/prepare').map((call) => JSON.parse(String(call.init?.body)).request_key);
    expect(keys).toHaveLength(2); expect(keys[0]).toBe(keys[1]);
  });

  it('准备复核失去响应时立即 UNKNOWN，不保留当前环境成功', async () => {
    localStorage.setItem('d1env.currentRuntimePrepare', 'runtime-task-1');
    taskResponse = { ...task, state: 'RUNNING', stage: 'wait_ready', user_action: null, environment_ready: null };
    statusResponse = { ...runtimeStatus, task: taskResponse };
    vi.useFakeTimers(); render(<App />);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(screen.getByTestId('runtime-stage')).toHaveTextContent('等待运行环境响应');
    taskReadsFail = true;
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    expect(screen.getByTestId('runtime-current-state')).toHaveTextContent('UNKNOWN');
    expect(screen.getByText('LOCAL_API_UNREACHABLE')).toBeVisible();
    expect(screen.queryByText('运行环境已准备；尚未启动 ROS 通信检查。')).not.toBeInTheDocument();
  });

  it('首次状态读取失败可显式只读重查，恢复后准备按钮可用且不自动安装', async () => {
    statusReadsFail = true;
    const user = await softwareHost();
    expect(await screen.findByText('LOCAL_API_UNREACHABLE')).toBeVisible();
    expect(screen.getByRole('button', { name: '准备运行环境' })).toBeDisabled();
    statusReadsFail = false;
    await user.click(screen.getByRole('button', { name: '重新读取准备状态' }));
    await waitFor(() => expect(screen.getByRole('button', { name: '准备运行环境' })).toBeEnabled());
    expect(calls.filter((call) => call.init?.method === 'POST' && call.path.startsWith('/api/runtime/'))).toHaveLength(0);
  });

  it('原型属性不能冒充有效阶段，非法任务返回保留 UNKNOWN', async () => {
    taskResponse = { ...task, stage: '__proto__' };
    const user = await softwareHost();
    await user.click(screen.getByRole('button', { name: '准备运行环境' }));
    expect(await screen.findByText('RUNTIME_RESPONSE_UNVERIFIED')).toBeVisible();
    expect(screen.getByTestId('runtime-current-state')).toHaveTextContent('UNKNOWN');
    expect(screen.queryByRole('button', { name: '已阅读许可并确认适用，继续准备' })).not.toBeInTheDocument();
  });

  it('未支持平台的矛盾 ready 响应不显示成功，复核保持 UNKNOWN', async () => {
    statusResponse = { ...runtimeStatus, environment_ready: true, platform: { os: 'Unknown', architecture: null, supported: false } };
    await softwareHost();
    expect(screen.getByRole('button', { name: '准备运行环境' })).toBeDisabled();
    expect(screen.queryByText('运行环境已准备；尚未启动 ROS 通信检查。')).not.toBeInTheDocument();
    expect(screen.getByTestId('runtime-current-state')).toHaveTextContent('UNKNOWN');
  });

  it('准备完成后也复核当前环境；配套镜像或环境丢失撤销准备成功', async () => {
    localStorage.setItem('d1env.currentRuntimePrepare', 'runtime-task-1');
    taskResponse = { ...task, state: 'SUCCEEDED', stage: 'complete', user_action: null, environment_ready: true };
    statusResponse = { ...runtimeStatus, environment_ready: true, task: taskResponse };
    vi.useFakeTimers(); render(<App />);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(screen.getByText('运行环境已准备；尚未启动 ROS 通信检查。')).toBeVisible();
    statusResponse = { ...runtimeStatus, environment_ready: false, task: taskResponse };
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    expect(screen.queryByText('运行环境已准备；尚未启动 ROS 通信检查。')).not.toBeInTheDocument();
    expect(screen.getByTestId('runtime-current-state')).toHaveTextContent('UNKNOWN');
  });

  it('取消后迟到的旧轮询不能覆盖新取消记录或继续显示准备进行中', async () => {
    const originalFetch = globalThis.fetch;
    let releaseOld: (response: Response) => void = () => undefined;
    const held = new Promise<Response>((resolve) => { releaseOld = resolve; });
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) === '/api/runtime/tasks/runtime-task-1') { calls.push({ path: String(input), init }); return held; }
      return originalFetch(input, init);
    }));
    const user = await softwareHost();
    await user.click(screen.getByRole('button', { name: '准备运行环境' }));
    await screen.findByRole('button', { name: '取消本次环境准备' });
    vi.useFakeTimers();
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    fireEvent.click(screen.getByRole('button', { name: '取消本次环境准备' }));
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(screen.getByText('CANCELLED')).toBeVisible();
    releaseOld(new Response(JSON.stringify(task), { status: 200 }));
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(screen.getByText('CANCELLED')).toBeVisible();
    expect(screen.queryByRole('button', { name: '已阅读许可并确认适用，继续准备' })).not.toBeInTheDocument();
    const cancelled = calls.find((call) => call.path.endsWith('/cancel'));
    expect(JSON.parse(String(cancelled?.init?.body))).toEqual({});
  });

  it('完成记录复核挂起超过十秒时未知，不让已准备标识永久留绿', async () => {
    localStorage.setItem('d1env.currentRuntimePrepare', 'runtime-task-1');
    taskResponse = { ...task, state: 'SUCCEEDED', stage: 'complete', user_action: null, environment_ready: true };
    statusResponse = { ...runtimeStatus, environment_ready: true, task: taskResponse };
    vi.useFakeTimers(); render(<App />);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    const originalFetch = globalThis.fetch;
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => String(input) === '/api/runtime/tasks/runtime-task-1' ? new Promise<Response>(() => undefined) : originalFetch(input, init)));
    await act(async () => { await vi.advanceTimersByTimeAsync(10100); });
    expect(screen.getByTestId('runtime-current-state')).toHaveTextContent('UNKNOWN');
    expect(screen.getByText('RUNTIME_OBSERVATION_EXPIRED')).toBeVisible();
    expect(screen.queryByText('运行环境已准备；尚未启动 ROS 通信检查。')).not.toBeInTheDocument();
  });

  it('许可 URL 不允许执行协议，缺少可信许可链接时不能提交确认', async () => {
    statusResponse = { ...runtimeStatus, installer: { ...runtimeStatus.installer, license_url: 'javascript:alert(1)' } };
    const user = await softwareHost();
    await user.click(screen.getByRole('button', { name: '准备运行环境' }));
    expect(screen.queryByRole('link', { name: '阅读 Docker 许可条件' })).not.toBeInTheDocument();
    expect(await screen.findByRole('button', { name: '已阅读许可并确认适用，继续准备' })).toBeDisabled();
    expect(calls.filter((call) => call.path.endsWith('/continue'))).toHaveLength(0);
  });

  it.each(['updated_at', 'error_code'])('非法任务字段 %s 不造成渲染崩溃，状态保持 UNKNOWN', async (field) => {
    taskResponse = { ...task, [field]: { unexpected: 'object' } };
    const user = await softwareHost();
    await user.click(screen.getByRole('button', { name: '准备运行环境' }));
    expect(await screen.findByText('RUNTIME_RESPONSE_UNVERIFIED')).toBeVisible();
    expect(screen.getByTestId('runtime-current-state')).toHaveTextContent('UNKNOWN');
  });

  it.each(['platform', 'installer'])('非法状态字段 %s 不显示准备成功且可重查', async (field) => {
    statusResponse = field === 'platform'
      ? { ...runtimeStatus, platform: { ...runtimeStatus.platform, os: { unexpected: 'object' } } }
      : { ...runtimeStatus, installer: { ...runtimeStatus.installer, blocked_reason: { unexpected: 'object' } } };
    await softwareHost();
    expect(await screen.findByText('RUNTIME_RESPONSE_UNVERIFIED')).toBeVisible();
    expect(screen.getByTestId('runtime-current-state')).toHaveTextContent('UNKNOWN');
    expect(screen.getByRole('button', { name: '重新读取准备状态' })).toBeEnabled();
  });

  it('安装源未知但已有本地 Docker 的嵌套 host 证据可复用，不要求重装或许可确认', async () => {
    statusResponse = { ...runtimeStatus, evidence: { host: { docker_accessible: true, endpoint_local: true }, artifact: { artifact_ready: false } }, installer: { version: null, sha256: null, size_bytes: null, license_url: null, blocked_reason: '没有新的可信安装包，已有本机环境可复用。' } };
    taskResponse = { ...task, state: 'SUCCEEDED', stage: 'complete', user_action: null, environment_ready: true };
    const user = await softwareHost();
    expect(screen.getByRole('button', { name: '准备运行环境' })).toBeEnabled();
    await user.click(screen.getByRole('button', { name: '准备运行环境' }));
    expect(await screen.findByText('运行环境已准备；尚未启动 ROS 通信检查。')).toBeVisible();
    expect(calls.filter((call) => call.path.endsWith('/continue'))).toHaveLength(0);
    expect(calls.filter((call) => call.path === '/api/runtime/prepare')).toHaveLength(1);
  });

  it('下载进度只显示后台实际字节数与总大小，缺失进度显示未知', async () => {
    taskResponse = { ...task, state: 'RUNNING', stage: 'download', user_action: null, progress: { downloaded_bytes: 5000000, total_bytes: 10000000 } };
    const user = await softwareHost();
    await user.click(screen.getByRole('button', { name: '准备运行环境' }));
    expect(await screen.findByText('已下载 5.0 MB / 10.0 MB')).toBeVisible();
    expect(screen.getByRole('progressbar', { name: '安装包下载进度' })).toHaveAttribute('value', '5000000');
    expect(screen.getByRole('progressbar', { name: '安装包下载进度' })).toHaveAttribute('max', '10000000');
    taskResponse = { ...taskResponse, progress: null };
    await user.click(screen.getByRole('button', { name: '重新读取准备状态' }));
    expect(await screen.findByText('下载进度未知；尚未取得可核对的字节数。')).toBeVisible();
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    expect(screen.queryByText('82%')).not.toBeInTheDocument();
  });

  it('下载字节数超过总大小时拒绝畸形进度，不显示错误百分比或成功', async () => {
    taskResponse = { ...task, state: 'RUNNING', stage: 'download', user_action: null, progress: { downloaded_bytes: 5000000, total_bytes: 4000000 } };
    const user = await softwareHost();
    await user.click(screen.getByRole('button', { name: '准备运行环境' }));
    expect(await screen.findByText('RUNTIME_RESPONSE_UNVERIFIED')).toBeVisible();
    expect(screen.getByTestId('runtime-current-state')).toHaveTextContent('UNKNOWN');
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });
});

it.each([false, null])('当前任务新观测 %s 不能被较旧的状态 true 覆盖', async (latestReady) => {
  const saved = { ...task, state: 'SUCCEEDED', stage: 'complete', user_action: null, environment_ready: true };
  localStorage.setItem('d1env.currentRuntimePrepare', 'runtime-task-1');
  statusResponse = { ...runtimeStatus, environment_ready: true, task: saved };
  taskResponse = { ...saved, environment_ready: latestReady };
  render(<App />);
  await waitFor(() => expect(calls.some((call) => call.path === '/api/runtime/tasks/runtime-task-1')).toBe(true));
  await waitFor(() => expect(screen.getByTestId('runtime-current-state')).toHaveTextContent('UNKNOWN'));
  expect(screen.queryByText('运行环境已准备；尚未启动 ROS 通信检查。')).not.toBeInTheDocument();
});
