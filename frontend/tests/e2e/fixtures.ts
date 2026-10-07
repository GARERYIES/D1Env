import { test as base, expect, type BrowserContext } from '@playwright/test';
import { readFile } from 'node:fs/promises';

// Cookie state stays in one isolated browser context, never in a saved auth file.
export const test = base.extend<object, { authenticatedContext: BrowserContext }>({
  authenticatedContext: [async ({ browser }, use) => {
    const tokenFile = process.env.D1ENV_E2E_TOKEN_FILE;
    if (!tokenFile) throw new Error('缺少本地 E2E 引导文件；此测试未验证，不可计为通过');
    const context = await browser.newContext({
      baseURL: process.env.D1ENV_E2E_URL ?? 'http://127.0.0.1:8765',
      viewport: { width: 1440, height: 1040 },
      acceptDownloads: true,
    });
    const bootstrapPage = await context.newPage();
    await bootstrapPage.addInitScript((token: string) => {
      history.replaceState(null, '', `${location.pathname}#bootstrap=${encodeURIComponent(token)}`);
    }, (await readFile(tokenFile, 'utf8')).trim());
    // The navigation URL contains no credential, including on test failure.
    await bootstrapPage.goto('/');
    await expect(bootstrapPage.getByRole('button', { name: '下一步：机器人配置' })).toBeEnabled();
    expect(new URL(bootstrapPage.url()).hash).toBe('');
    await bootstrapPage.close();
    await use(context);
    await context.close();
  }, { scope: 'worker' }],
  page: async ({ authenticatedContext }, use) => {
    const page = await authenticatedContext.newPage();
    await use(page);
    // Clear only the UI's saved pointer between scenarios; no resources are stopped here.
    if (!page.isClosed()) {
      await page.evaluate(() => {
        localStorage.removeItem('d1env.currentJob');
        localStorage.removeItem('d1env.currentRuntimePrepare');
        localStorage.removeItem('d1env.runtimePrepareKey');
      }).catch(() => undefined);
      await page.close();
    }
  },
});

export { expect };
