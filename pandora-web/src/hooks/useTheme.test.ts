import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { useTheme } from './useTheme';

describe('useTheme', () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.theme;
  });

  it('applies and persists a selected theme', () => {
    const { result, unmount } = renderHook(() => useTheme());

    expect(result.current.theme).toBe('forest');
    expect(document.documentElement.dataset.theme).toBe('forest');

    act(() => result.current.setTheme('signal'));
    expect(document.documentElement.dataset.theme).toBe('signal');
    expect(localStorage.getItem('pandora-theme')).toBe('signal');

    unmount();
    const restored = renderHook(() => useTheme());
    expect(restored.result.current.theme).toBe('signal');
  });

  it('falls back to forest for an unknown stored value', () => {
    localStorage.setItem('pandora-theme', 'unknown');
    const { result } = renderHook(() => useTheme());

    expect(result.current.theme).toBe('forest');
    expect(document.documentElement.dataset.theme).toBe('forest');
  });
});
