import { readFile } from 'node:fs/promises';
import type { Page } from '@playwright/test';
import { expect, test } from './fixtures';
import { prepareExistingRuntimeFromUi } from './runtime-preparation';

test.skip(process.env.D1ENV_E2E_SOFTWARE !== '1', 'NOT_RUN：必须显式启用真实软件测试，并提供已核验的本地 Docker/ROS 镜像');

async function stopOwnedJobFromUi(page: Page, id: string) {
  await page.getByRole('button', { name: '查看历史软件作业' }).click();
  await page.getByRole('button', { name: `恢复软件作业 ${id}` }).click();
  await expect(page.getByTestId('job-id')).toHaveText(id);
  const terminal = /SUCCEEDED|FAILED|BLOCKED|CANCELLED|INTERRUPTED/;
  if (!terminal.test(await page.getByTestId('job-state').innerText())) {
    await page.getByRole('button', { name: '取消本次软件测试' }).click();
    await expect(page.getByTestId('job-state')).toHaveText(terminal, { timeout: 60000 });
  }
  await page.getByRole('button', { name: /^(停止测试服务|清理本作业遗留服务)$/ }).click();
  await expect(page.getByTestId('job-state')).toContainText('CANCELLED');
}

test('真实本地 Docker/ROS：software 范围、刷新、停止、故障注入与原计划重试', async ({ page }) => {
  test.setTimeout(900000);
  let submissions = 0;
  const keys: string[] = [];
  const planIds: string[] = [];
  const ownedJobs = new Set<string>();
  page.on('response', async (response) => {
    if (new URL(response.url()).pathname === '/api/jobs' && response.request().method() === 'POST' && response.ok()) {
      const snapshot = await response.json().catch(() => null) as { job_id: string } | null;
      if (snapshot && typeof snapshot.job_id === 'string') ownedJobs.add(snapshot.job_id);
    }
  });
  page.on('request', (request) => {
    if (new URL(request.url()).pathname === '/api/jobs' && request.method() === 'POST') {
      const data = request.postDataJSON() as { plan_id: string; idempotency_key: string };
      submissions += 1; keys.push(data.idempotency_key); planIds.push(data.plan_id);
    }
  });
  try {
  await page.goto('/');
  const recoveryIds = (process.env.D1ENV_E2E_CLEANUP_JOB_IDS ?? '').split(',').filter(Boolean);
  for (const id of recoveryIds) {
    if (!/^[a-zA-Z0-9_-]{1,128}$/.test(id)) throw new Error('测试恢复作业ID格式无效');
    await stopOwnedJobFromUi(page, id);
    await page.getByRole('button', { name: '新建软件测试' }).click();
  }
  await page.getByRole('button', { name: '真实软件测试（Docker/ROS，未接真机）' }).click();
  await expect(page.getByTestId('mode-watermark')).toContainText('真实软件测试');
  await page.getByRole('button', { name: '下一步：机器人配置' }).click();
  await expect(page.getByRole('button', { name: /选择 D1 点足候选/ })).toBeDisabled();
  await page.getByRole('button', { name: '下一步：执行电脑' }).click();
  await expect(page.getByTestId('telemetry-state')).toContainText('UNKNOWN');
  await prepareExistingRuntimeFromUi(page);
  const bundleFile = process.env.D1ENV_E2E_ROS_BUNDLE_FILE;
  if (bundleFile) {
    await expect(page.getByLabel('随包 ROS 镜像文件')).toBeEnabled();
    await expect(page.getByRole('button', { name: '导入随发行包提供的 ROS 软件镜像' })).toBeDisabled();
    await page.getByLabel('随包 ROS 镜像文件').setInputFiles(bundleFile);
    await page.getByRole('button', { name: '导入随发行包提供的 ROS 软件镜像' }).click();
    await expect(page.getByText('软件镜像已导入；还需启动测试并检查 ROS 通信。')).toBeVisible({ timeout: 660000 });
    await expect(page.getByTestId('telemetry-state')).toContainText('UNKNOWN');
    await page.screenshot({ path: 'test-results/m3-ui-software-import.png', fullPage: true });
  } else {
    test.info().annotations.push({ type: 'NOT_RUN', description: '离线镜像导入：缺少显式发行工件文件，本次未验证导入环节' });
  }
  await page.getByRole('button', { name: '下一步：部署预览' }).click();
  await expect(page.getByText('d1env/ros-probe')).toBeVisible();
  await expect(page.getByText(/项目内部网络/)).toBeVisible();
  await page.getByRole('button', { name: '启动真实软件测试' }).evaluate((button) => {
    (button as HTMLButtonElement).click(); (button as HTMLButtonElement).click();
  });
  await expect(page.getByRole('heading', { name: '软件环境检查通过，未连接真机', exact: true })).toBeVisible({ timeout: 90000 });
  expect(submissions).toBe(1);
  await expect(page.getByTestId('verified-scope')).toContainText('software');
  const successfulJob = await page.getByTestId('job-id').innerText();
  await page.reload();
  await expect(page.getByTestId('job-id')).toHaveText(successfulJob);
  await expect(page.getByTestId('mode-watermark')).toContainText('真实软件测试');
  await expect(page.getByRole('heading', { name: '软件环境检查通过，未连接真机', exact: true })).toBeVisible({ timeout: 30000 });
  expect(submissions).toBe(1);
  expect(new URL(page.url()).hash).toBe('');
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: 'test-results/m3-ui-software-success.png', fullPage: true });
  await page.screenshot({ path: 'test-results/m3-ui-software-success-viewport.png', fullPage: false });
  // Browser-only network fault injection, separate from real Docker readiness evidence.
  const healthPath = `**/api/jobs/${successfulJob}`;
  await page.route(healthPath, (route) => route.abort('failed'));
  await expect(page.getByRole('heading', { name: '部署曾完成，当前软件状态未知', exact: true })).toBeVisible({ timeout: 10000 });
  await expect(page.getByText('CURRENT_HEALTH_UNAVAILABLE', { exact: true })).toBeVisible();
  await expect(page.getByText('新鲜度检查通过')).toHaveCount(0);
  await page.screenshot({ path: 'test-results/m3-ui-software-network-fault-injection.png', fullPage: true });
  await page.unroute(healthPath);
  await expect(page.getByRole('heading', { name: '软件环境检查通过，未连接真机', exact: true })).toBeVisible({ timeout: 15000 });
  await page.getByRole('button', { name: '停止测试服务' }).click();
  await expect(page.getByTestId('job-state')).toContainText('CANCELLED');
  await expect(page.getByText(/软件停止请求不等于硬件急停/)).toBeVisible();
  await page.getByRole('button', { name: '新建软件测试' }).click();
  await page.getByLabel('软件测试场景').selectOption('no_publisher');
  await page.getByRole('button', { name: '4 部署预览' }).click();
  await expect(page.getByText('故障注入测试 · 无发布者')).toBeVisible();
  await page.getByRole('button', { name: '启动真实软件测试' }).click();
  await expect(page.getByTestId('job-state')).toContainText('FAILED', { timeout: 90000 });
  await expect(page.getByText('故障注入测试 · 无发布者')).toBeVisible();
  await expect(page.getByRole('heading', { name: '失败环节与下一步' })).toBeVisible();
  const failedJob = await page.getByTestId('job-id').innerText();
  await page.reload();
  await expect(page.getByTestId('job-id')).toHaveText(failedJob);
  await expect(page.getByTestId('mode-watermark')).toContainText('真实软件测试');
  await expect(page.getByText('故障注入测试 · 无发布者')).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: 'test-results/m3-ui-software-failure.png', fullPage: true });
  await page.screenshot({ path: 'test-results/m3-ui-software-failure-viewport.png', fullPage: false });
  await page.getByRole('button', { name: '1 使用方式' }).click();
  await page.getByRole('button', { name: /软件演示体验/ }).click();
  await page.getByRole('button', { name: '查看历史软件作业' }).click();
  await page.getByRole('button', { name: `恢复软件作业 ${failedJob}` }).click();
  await expect(page.getByTestId('job-id')).toHaveText(failedJob);
  await expect(page.getByTestId('mode-watermark')).toContainText('真实软件测试');
  await expect(page.getByText('故障注入测试 · 无发布者')).toBeVisible();
  await page.getByRole('button', { name: '生成去敏诊断报告' }).click();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载 JSON' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toContain('software');
  await download.saveAs('test-results/m3-ui-software-report.json');
  const path = await download.path();
  if (!path) throw new Error('下载未生成实际文件');
  const report = JSON.parse(await readFile(path, 'utf8')) as { mode: string; verified_scope: string; events: { origin: string }[] };
  expect(report.mode).toBe('software_test'); expect(report.verified_scope).toBe('software');
  expect(report.events.some((event) => event.origin === 'docker')).toBe(true);
  const markdownPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载 Markdown' }).click();
  const markdown = await markdownPromise;
  expect(markdown.suggestedFilename()).toContain('software');
  await markdown.saveAs('test-results/m3-ui-software-report.md');
  await page.screenshot({ path: 'test-results/m3-ui-software-report.png', fullPage: true });
  await page.getByRole('button', { name: '清理本作业遗留服务' }).click();
  await expect(page.getByTestId('job-state')).toContainText('CANCELLED');
  await page.getByRole('button', { name: '重试真实软件测试' }).click();
  await expect.poll(() => submissions).toBe(3);
  expect(keys[2]).not.toBe(keys[1]); expect(planIds[2]).toBe(planIds[1]);
  await expect(page.getByTestId('job-state')).toContainText('FAILED', { timeout: 90000 });
  await expect(page.getByTestId('mode-watermark')).toContainText('真实软件测试');
  await page.getByRole('button', { name: '清理本作业遗留服务' }).click();
  await expect(page.getByTestId('job-state')).toContainText('CANCELLED');
  } finally {
    await page.unrouteAll({ behavior: 'wait' });
    for (const id of ownedJobs) await stopOwnedJobFromUi(page, id);
  }
});
