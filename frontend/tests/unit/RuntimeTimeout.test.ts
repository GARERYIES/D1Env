import { afterEach, expect, it, vi } from 'vitest';
import { D1EnvApi } from '../../src/api';

afterEach(() => vi.useRealTimers());
it('首次入口的有限签名核验允许超过五秒，仍有九十秒请求上限', async () => {
  vi.useFakeTimers();
  let aborted = false;
  vi.stubGlobal('fetch', vi.fn((_input: unknown, init?: RequestInit) => new Promise((_resolve, reject) => {
    init?.signal?.addEventListener('abort', () => { aborted = true; reject(new TypeError('bounded observation timeout')); });
  })));
  const observation = new D1EnvApi().runtimeStatus().catch(() => null);
  await vi.advanceTimersByTimeAsync(6000);
  expect(aborted).toBe(false);
  await vi.advanceTimersByTimeAsync(90000);
  await observation;
  expect(aborted).toBe(true);
});
