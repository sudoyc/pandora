import useSWRInfinite from 'swr/infinite';
import { fetcher } from '../api/client';
import { DEFAULT_GALLERY_VIEW, type GalleryView } from '../galleryView';
import type { GalleryListItem } from '../models';

export function useGalleries(view: GalleryView = DEFAULT_GALLERY_VIEW) {
  const isPaginated = view.kind === 'search' || view.kind === 'watched';

  const getKey = (pageIndex: number, previousPageData: GalleryListItem[] | null) => {
    if (previousPageData && previousPageData.length === 0) return null;
    if (!isPaginated && pageIndex > 0) return null;
    if (view.kind === 'search') {
      return `/search?keyword=${encodeURIComponent(view.query)}&page=${pageIndex}`;
    }
    if (view.kind === 'popular') return '/popular';
    if (view.kind === 'watched') return `/watched?page=${pageIndex}`;
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
