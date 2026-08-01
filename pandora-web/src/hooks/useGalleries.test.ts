import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import useSWRInfinite from 'swr/infinite';
import type { GalleryListItem } from '../models';
import { useGalleries } from './useGalleries';

vi.mock('swr/infinite', () => ({ default: vi.fn() }));

const gallery = (gid: string): GalleryListItem => ({
  gid,
  token: `token-${gid}`,
  title: `Gallery ${gid}`,
  category: 'Manga',
  uploader: 'fixture-user',
  thumb_url: '',
  posted: '2026-01-01',
  rating: 4,
  pages: 20,
  rated: false,
  thumb_width: 250,
  thumb_height: 350,
});

describe('useGalleries', () => {
  const setSize = vi.fn();
  const mutate = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    setSize.mockResolvedValue(undefined);
  });

  it('builds paginated advanced search keys from the real daemon contract', () => {
    vi.mocked(useSWRInfinite).mockReturnValue({
      data: [[gallery('1')]],
      size: 1,
      setSize,
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate,
    } as never);

    renderHook(() => useGalleries({
      kind: 'search',
      criteria: { query: 'fixture', minRating: 4, searchTags: true },
    }));

    const getKey = vi.mocked(useSWRInfinite).mock.calls[0][0] as (
      index: number,
      previous: GalleryListItem[] | null,
    ) => string | null;
    expect(getKey(0, null)).toBe('/search?keyword=fixture&page=0&min_rating=4&search_tags=true');
    expect(getKey(1, [gallery('1')])).toBe('/search?keyword=fixture&next=1&min_rating=4&search_tags=true');
    expect(getKey(2, [])).toBeNull();
  });

  it('paginates the default browse feed with the last visible gallery cursor', () => {
    vi.mocked(useSWRInfinite).mockReturnValue({
      data: [[gallery('100'), gallery('90')]],
      size: 1,
      setSize,
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate,
    } as never);

    renderHook(() => useGalleries({ kind: 'homepage' }));

    const getKey = vi.mocked(useSWRInfinite).mock.calls[0][0] as (
      index: number,
      previous: GalleryListItem[] | null,
    ) => string | null;
    expect(getKey(0, null)).toBe('/homepage');
    expect(getKey(1, [gallery('100'), gallery('90')])).toBe('/homepage?next=90');
  });

  it('deduplicates overlapping pages and guards concurrent page loads', () => {
    vi.mocked(useSWRInfinite).mockReturnValue({
      data: [[gallery('1'), gallery('2')], [gallery('2'), gallery('3')]],
      size: 2,
      setSize,
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate,
    } as never);

    const { result } = renderHook(() => useGalleries({ kind: 'watched' }));
    expect(result.current.galleries.map((item) => item.gid)).toEqual(['1', '2', '3']);

    act(() => result.current.loadMore());
    expect(setSize).toHaveBeenCalledOnce();

    vi.mocked(useSWRInfinite).mockReturnValue({
      data: [[gallery('1')], undefined],
      size: 2,
      setSize,
      error: undefined,
      isLoading: false,
      isValidating: true,
      mutate,
    } as never);
    const loading = renderHook(() => useGalleries({ kind: 'watched' }));
    act(() => loading.result.current.loadMore());
    expect(setSize).toHaveBeenCalledOnce();
    expect(loading.result.current.isLoadingMore).toBe(true);
  });

  it('marks an empty trailing page as the end of the feed', () => {
    vi.mocked(useSWRInfinite).mockReturnValue({
      data: [[gallery('1')], []],
      size: 2,
      setSize,
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate,
    } as never);

    const { result } = renderHook(() => useGalleries({ kind: 'watched' }));
    expect(result.current.hasMore).toBe(false);
    expect(result.current.isReachingEnd).toBe(true);
  });

  it('stops when an upstream page does not advance its cursor', () => {
    vi.mocked(useSWRInfinite).mockReturnValue({
      data: [[gallery('2'), gallery('1')], [gallery('2'), gallery('1')]],
      size: 2,
      setSize,
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate,
    } as never);

    const { result } = renderHook(() => useGalleries({ kind: 'homepage' }));
    expect(result.current.hasMore).toBe(false);
    expect(result.current.isReachingEnd).toBe(true);
  });
});
