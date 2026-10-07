import { writeFile } from 'node:fs/promises';
import type { Page, Request } from '@playwright/test';
import { expect } from './fixtures';

type RuntimeObservation = {
  scope: string; environment_ready: boolean | null;
  platform: { os: string | null; architecture: string | null; supported: boolean };
  evidence: { host: { docker_available: boolean | null; docker_accessible: boolean | null; compose_available: boolean | null; endpoint_local: boolean | null }; artifact: { artifact_ready: boolean | null } };
};
type PreparedTask = {
  task_id: string; scope: string; state: string; stage: string; environment_ready: boolean | null;
  events: { stage: string; state: string }[];
  evidence: { complete?: { image_preparation?: { status?: string; origin?: string; image_id?: string; architecture?: string } } };
};

// Only an already running local Docker and the exact installed ROS image are used.
// Missing prerequisites fail before POST; this test never accepts an installation
// license, starts Desktop intentionally, supplies passwords, or fabricates state.
export async function prepareExistingRuntimeFromUi(page: Page) {
  const panel = page.getByRole('region', { name: '准备运行环境', exact: true });
  await expect(panel).toBeVisible();
  const readonlyResponse = await page.request.get('/api/runtime/status');
  expect(readonlyResponse.ok(), '真实运行环境只读 API 必须可用').toBe(true);
  const observation = await readonlyResponse.json() as RuntimeObservation;
  const host = observation.evidence?.host;
  const artifact = observation.evidence?.artifact;
  if (observation.scope !== 'runtime_environment' || observation.environment_ready !== true || observation.platform?.supported !== true || host?.docker_available !== true || host?.docker_accessible !== true || host?.compose_available !== true || host?.endpoint_local !== true || artifact?.artifact_ready !== true) {
    await expect(page.getByTestId('telemetry-state')).toHaveText('UNKNOWN');
    expect(new URL(page.url()).hash).toBe('');
    await page.screenshot({ path: 'test-results/m3-ui-runtime-prepare-unavailable.png', fullPage: true });
    throw new Error('真实准备 E2E 前置检查失败：需要已运行的本机 Docker/Compose 和准确 ROS 镜像；未发送准备请求，未尝试安装或启动 Docker。此范围未验证，不能记作通过。');
  }

  let preparePosts = 0;
  let continuePosts = 0;
  let deploymentPosts = 0;
  const onRequest = (request: Request) => {
    const path = new URL(request.url()).pathname;
    if (request.method() !== 'POST') return;
    if (path === '/api/runtime/prepare') {
      preparePosts += 1;
      expect(Object.keys(request.postDataJSON() as object)).toEqual(['request_key']);
      expect(!!request.headers()['x-csrf-token']).toBe(true);
    }
    if (/^\/api\/runtime\/tasks\/[^/]+\/continue$/.test(path)) continuePosts += 1;
    if (path === '/api/jobs') deploymentPosts += 1;
  };
  page.on('request', onRequest);
  try {
    const preparedResponse = page.waitForResponse((response) => new URL(response.url()).pathname === '/api/runtime/prepare' && response.request().method() === 'POST');
    await expect(panel.getByRole('button', { name: '准备运行环境', exact: true })).toBeEnabled();
    await panel.getByRole('button', { name: '准备运行环境', exact: true }).evaluate((button) => {
      (button as HTMLButtonElement).click(); (button as HTMLButtonElement).click();
    });
    const response = await preparedResponse;
    expect(response.ok(), '真实准备任务提交必须成功').toBe(true);
    const initialTask = await response.json() as PreparedTask;
    expect(initialTask.scope).toBe('runtime_environment');
    expect(initialTask.task_id).toMatch(/^[0-9a-f]{32}$/);
    await expect(panel.getByText('SUCCEEDED', { exact: true })).toBeVisible({ timeout: 60000 });
    await expect(panel.getByText('运行环境已准备；尚未启动 ROS 通信检查。', { exact: true })).toBeVisible();
    await expect(page.getByTestId('runtime-current-state')).toHaveText('仅运行环境已准备');
    await expect(page.getByTestId('telemetry-state')).toHaveText('UNKNOWN');
    await expect(page.getByTestId('battery-value')).toContainText('未知');
    await expect(page.getByRole('button', { name: '运动控制未启用' })).toBeDisabled();
    expect(deploymentPosts).toBe(0); expect(preparePosts).toBe(1); expect(continuePosts).toBe(0);

    const taskResponse = await page.request.get(`/api/runtime/tasks/${initialTask.task_id}`);
    expect(taskResponse.ok()).toBe(true);
    const completed = await taskResponse.json() as PreparedTask;
    expect(completed.scope).toBe('runtime_environment'); expect(completed.state).toBe('SUCCEEDED');
    expect(completed.stage).toBe('complete'); expect(completed.environment_ready).toBe(true);
    const nativeStages = new Set(['license', 'download', 'verify', 'install', 'native_setup', 'start', 'wait_ready']);
    expect(completed.events.filter((event) => nativeStages.has(event.stage))).toEqual([]);
    expect(completed.evidence.complete?.image_preparation?.status).toBe('reused');
    expect(completed.evidence.complete?.image_preparation?.origin).toBe('docker');

    await page.reload();
    await expect(page.getByTestId('mode-watermark')).toContainText('真实软件测试');
    await expect(page.getByRole('region', { name: '准备运行环境', exact: true }).getByText('SUCCEEDED', { exact: true })).toBeVisible({ timeout: 20000 });
    await expect(page.getByText('运行环境已准备；尚未启动 ROS 通信检查。', { exact: true })).toBeVisible();
    expect(preparePosts).toBe(1); expect(continuePosts).toBe(0); expect(deploymentPosts).toBe(0);
    expect(new URL(page.url()).hash).toBe('');
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: 'test-results/m3-ui-runtime-prepare-success.png', fullPage: true });
    await page.screenshot({ path: 'test-results/m3-ui-runtime-prepare-success-viewport.png', fullPage: false });
    await writeFile('test-results/m3-ui-runtime-prepare-proof.json', JSON.stringify({
      source: 'actual_local_api_and_browser', scope: completed.scope, task_id: completed.task_id,
      state: completed.state, stage: completed.stage, environment_ready: completed.environment_ready,
      existing_docker_only: true, existing_locked_image_only: true,
      native_install_or_start_stages: [], stage_records: completed.events.map((event) => ({ state: event.state, stage: event.stage })),
      image_preparation: completed.evidence.complete?.image_preparation,
      prepare_posts: preparePosts, continue_posts: continuePosts, deployment_posts_during_preparation: deploymentPosts,
      refresh_repeated_prepare: false, robot_telemetry: 'UNKNOWN', robot_functions_verified: false,
      unverified: ['首次下载与原生安装/许可/系统授权', '未安装 Docker 的新电脑', 'Linux 与 Intel Mac', 'D1 SDK/真机/运动'],
    }, null, 2) + '\n');
  } finally {
    page.off('request', onRequest);
  }
}
