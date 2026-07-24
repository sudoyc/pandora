import { useCallback, useState } from 'react';
import {
  DEFAULT_GALLERY_VIEW,
  type GalleryNavigationKind,
  type GalleryView,
} from '../galleryView';

const SEARCH_HISTORY_KEY = 'searchHistory';

function loadSearchHistory(): string[] {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(SEARCH_HISTORY_KEY) ?? '[]');
    if (!Array.isArray(stored)) return [];
    return stored.filter((item): item is string => typeof item === 'string').slice(0, 10);
  } catch {
    return [];
  }
}

export function useGalleryView() {
  const [view, setView] = useState<GalleryView>(DEFAULT_GALLERY_VIEW);
  const [searchHistory, setSearchHistory] = useState<string[]>(loadSearchHistory);

  const navigate = useCallback((kind: GalleryNavigationKind) => {
    setView({ kind });
  }, []);

  const search = useCallback((value: string) => {
    const query = value.trim();
    if (!query) return;

    setSearchHistory((current) => {
      const next = [query, ...current.filter((item) => item !== query)].slice(0, 10);
      localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(next));
      return next;
    });
    setView({ kind: 'search', query });
  }, []);

  return { view, searchHistory, navigate, search };
}
