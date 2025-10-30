import { describe, expect, it, vi } from 'vitest';

import { hslToHex } from './utils';

describe('hslToHex', () => {
  it('sanitizes percentage values before parsing', () => {
    const parseFloatSpy = vi.spyOn(globalThis, 'parseFloat');

    try {
      hslToHex('42%% 50% 50%');

      for (const [value] of parseFloatSpy.mock.calls) {
        if (typeof value === 'string') {
          expect(value.includes('%')).toBe(false);
        }
      }
    } finally {
      parseFloatSpy.mockRestore();
    }
  });
});
