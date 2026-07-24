import useSWR from 'swr';
import { fetcher } from '../api/client';
import type {
  DownloadTaskSnapshot,
  FavoritesResponse,
  HistoryItem,
  LibraryItem,
} from '../models';

export function useFavorites(slot = -1) {
  return useSWR<FavoritesResponse>(`/favorites?slot=${slot}&page=0`, fetcher);
}

export function useHistory() {
  return useSWR<HistoryItem[]>('/history?limit=50&offset=0', fetcher);
}

export function useDownloads() {
  return useSWR<DownloadTaskSnapshot[]>('/downloads', fetcher);
}

export function useLibrary() {
  return useSWR<LibraryItem[]>('/library', fetcher);
}
