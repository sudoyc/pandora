import { useCallback, useEffect, useMemo, useRef } from 'react';
import useSWRInfinite from 'swr/infinite';
import { fetcher } from '../api/client';
import { DEFAULT_GALLERY_VIEW, type GalleryView } from '../galleryView';
import type { GalleryListItem } from '../models';
import { buildSearchPath } from '../search';

export function useGalleries(view: GalleryView = DEFAULT_GALLERY_VIEW) {
  const isPaginated = view.kind === 'homepage' || view.kind === 'search' || view.kind === 'watched';

  const getKey = (pageIndex: number, previousPageData: GalleryListItem[] | null) => {
    if (previousPageData && previousPageData.length === 0) return null;
    if (!isPaginated && pageIndex > 0) return null;
    const nextGid = pageIndex > 0 ? previousPageData?.at(-1)?.gid : undefined;
    if (pageIndex > 0 && !nextGid) return null;
    if (view.kind === 'search') {
      return buildSearchPath(view.criteria, pageIndex, nextGid);
    }
    if (view.kind === 'popular') return '/popular';
    if (view.kind === 'watched') {
      return nextGid ? `/watched?next=${encodeURIComponent(nextGid)}` : '/watched?page=0';
    }
    return nextGid ? `/homepage?next=${encodeURIComponent(nextGid)}` : '/homepage';
  };

  const { data, size, setSize, error, isLoading, isValidating, mutate } = useSWRInfinite<GalleryListItem[]>(
    getKey,
    fetcher,
    { revalidateFirstPage: false },
  );
  const loadPending = useRef(false);

  const galleries = useMemo(() => {
    const seen = new Set<string>();
    const result: GalleryListItem[] = [];
    for (const page of data ?? []) {
      if (!page) continue;
      for (const gallery of page) {
        const key = `${gallery.gid}:${gallery.token}`;
        if (seen.has(key)) continue;
        seen.add(key);
        result.push(gallery);
      }
    }
    return result;
  }, [data]);
  const lastPage = data?.[data.length - 1];
  const previousPage = data && data.length > 1 ? data[data.length - 2] : undefined;
  const cursorStalled = Boolean(
    lastPage?.length
    && previousPage?.length
    && lastPage.at(-1)?.gid === previousPage.at(-1)?.gid,
  );
  const isLoadingMore = Boolean(
    !error && (isLoading || (size > 0 && data && typeof data[size - 1] === 'undefined')),
  );
  const isReachingEnd = !isPaginated
    || Boolean(data && lastPage && lastPage.length === 0)
    || cursorStalled;
  const hasMore = isPaginated && !isReachingEnd;

  useEffect(() => {
    if (!isLoadingMore) loadPending.current = false;
  }, [data, isLoadingMore]);

  const loadMore = useCallback(() => {
    if (!hasMore || isLoadingMore || loadPending.current) return;
    loadPending.current = true;
    void setSize((currentSize) => currentSize + 1).finally(() => {
      loadPending.current = false;
    });
  }, [hasMore, isLoadingMore, setSize]);

  return {
    galleries,
    loadMore,
    hasMore,
    isLoading: Boolean(isLoading && !data),
    isLoadingMore,
    isRefreshing: Boolean(isValidating && data && !isLoadingMore),
    isReachingEnd,
    isPaginated,
    error,
    mutate,
  };
}
