import { useCallback, useState } from 'react';
import {
  type AppNavigationKind,
  DEFAULT_GALLERY_VIEW,
  type AppView,
} from '../galleryView';
import {
  isSearchCriteriaActive,
  normalizeSearchCriteria,
  searchCriteriaKey,
  type SearchCriteria,
} from '../search';

const SEARCH_HISTORY_KEY = 'searchHistory';

function persistSearchHistory(history: SearchCriteria[]) {
  try {
    localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(history));
  } catch {
    // Browsing still works when storage is unavailable.
  }
}

function loadSearchHistory(): SearchCriteria[] {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(SEARCH_HISTORY_KEY) ?? '[]');
    if (!Array.isArray(stored)) return [];
    const seen = new Set<string>();
    const history: SearchCriteria[] = [];
    for (const item of stored) {
      const candidate = typeof item === 'string'
        ? normalizeSearchCriteria({ query: item })
        : normalizeSearchCriteria(item as Partial<SearchCriteria>);
      const key = searchCriteriaKey(candidate);
      if (!isSearchCriteriaActive(candidate) || seen.has(key)) continue;
      seen.add(key);
      history.push(candidate);
      if (history.length === 10) break;
    }
    return history;
  } catch {
    return [];
  }
}

export function useGalleryView() {
  const [view, setView] = useState<AppView>(DEFAULT_GALLERY_VIEW);
  const [searchHistory, setSearchHistory] = useState<SearchCriteria[]>(loadSearchHistory);

  const navigate = useCallback((kind: AppNavigationKind) => {
    setView({ kind });
  }, []);

  const search = useCallback((criteria: SearchCriteria) => {
    const normalized = normalizeSearchCriteria(criteria);
    if (!isSearchCriteriaActive(normalized)) return;

    setSearchHistory((current) => {
      const key = searchCriteriaKey(normalized);
      const next = [
        normalized,
        ...current.filter((item) => searchCriteriaKey(item) !== key),
      ].slice(0, 10);
      persistSearchHistory(next);
      return next;
    });
    setView({ kind: 'search', criteria: normalized });
  }, []);

  const removeSearchHistory = useCallback((criteria: SearchCriteria) => {
    const key = searchCriteriaKey(criteria);
    setSearchHistory((current) => {
      const next = current.filter((item) => searchCriteriaKey(item) !== key);
      persistSearchHistory(next);
      return next;
    });
  }, []);

  return { view, searchHistory, navigate, search, removeSearchHistory };
}
