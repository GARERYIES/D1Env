import type { Mode, VerifiedScope } from './types';

export function scopeMatchesMode(mode: Mode, scope: VerifiedScope) {
  return (mode === 'mock' && scope === 'mock') || (mode === 'software_test' && scope === 'software');
}

export function modeLabel(mode: Mode) {
  return mode === 'mock' ? 'MOCK' : mode === 'software_test' ? '真实软件测试' : '真实机器人只读（尚未实施）';
}
