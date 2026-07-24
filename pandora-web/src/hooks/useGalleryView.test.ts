import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { useGalleryView } from './useGalleryView';

describe('useGalleryView', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('keeps search query and navigation mode in one stable view value', () => {
    const { result } = renderHook(() => useGalleryView());

    expect(result.current.view).toEqual({ kind: 'homepage' });

    act(() => result.current.search('  fixture query  '));
    expect(result.current.view).toEqual({ kind: 'search', query: 'fixture query' });
    expect(result.current.searchHistory).toEqual(['fixture query']);
    expect(JSON.parse(localStorage.getItem('searchHistory') ?? '[]')).toEqual([
      'fixture query',
    ]);

    act(() => result.current.navigate('popular'));
    expect(result.current.view).toEqual({ kind: 'popular' });
  });

  it('ignores empty searches and invalid persisted history', () => {
    localStorage.setItem('searchHistory', '{"invalid":true}');
    const { result } = renderHook(() => useGalleryView());

    expect(result.current.searchHistory).toEqual([]);
    act(() => result.current.search('   '));
    expect(result.current.view).toEqual({ kind: 'homepage' });
  });
});
