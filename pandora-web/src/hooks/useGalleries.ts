import useSWRInfinite from 'swr/infinite';
import { fetcher } from '../api/client';
import type { GalleryListItem } from '../models';

export function useGalleries(mode: 'homepage' | 'search' | 'popular' | 'watched' = 'homepage', keyword = '') {
  const trimmedKeyword = keyword.trim();
  const isPaginated = mode === 'search' || mode === 'watched';

  const getKey = (pageIndex: number, previousPageData: GalleryListItem[] | null) => {
    if (previousPageData && previousPageData.length === 0) return null;
    if (!isPaginated && pageIndex > 0) return null;
    if (mode === 'search') {
      return `/search?keyword=${encodeURIComponent(trimmedKeyword)}&page=${pageIndex}`;
    }
    if (mode === 'popular') return '/popular';
    if (mode === 'watched') return `/watched?page=${pageIndex}`;
    return '/homepage';
  };

  const { data, size, setSize, error, isLoading, mutate } = useSWRInfinite<GalleryListItem[]>(getKey, fetcher);

  const galleries = data ? data.flat() : [];
  const lastPage = data?.[data.length - 1];
  const hasMore = isPaginated && Boolean(lastPage?.length);
  const loadMore = () => {
    if (hasMore) void setSize(size + 1);
  };

  return { galleries, loadMore, hasMore, isLoading, error, mutate };
}
