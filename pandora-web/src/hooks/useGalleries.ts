import useSWRInfinite from 'swr/infinite';
import { fetcher } from '../api/client';
import type { GalleryListItem } from '../models';

export const useGalleries = (mode: string = 'homepage', params: string = '') => {
  const getKey = (pageIndex: number, previousPageData: GalleryListItem[] | null) => {
    if (previousPageData && !previousPageData.length) return null;
    return `/${mode}?page=${pageIndex}${params}`;
  };

  const { data, size, setSize, error, isLoading } = useSWRInfinite<GalleryListItem[]>(getKey, fetcher);
  
  const galleries = data ? data.flat() : [];
  const loadMore = () => setSize(size + 1);

  return { galleries, loadMore, isLoading, error };
};
