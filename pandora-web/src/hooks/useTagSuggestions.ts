import { useEffect, useState } from 'react';
import useSWR from 'swr';
import { fetcher } from '../api/client';
import { suggestionTerm, type TagSuggestion } from '../search';

type TagSuggestionResponse = {
  suggestions: TagSuggestion[];
};

export function useTagSuggestions(query: string, enabled: boolean) {
  const term = suggestionTerm(query);
  const [debouncedTerm, setDebouncedTerm] = useState('');

  useEffect(() => {
    if (!enabled || !term) return undefined;
    const timeout = window.setTimeout(() => setDebouncedTerm(term), 180);
    return () => window.clearTimeout(timeout);
  }, [enabled, term]);

  const current = enabled && Boolean(term) && debouncedTerm === term;
  const key = current
    ? `/tags/suggest?q=${encodeURIComponent(debouncedTerm)}&limit=6`
    : null;
  const { data, error, isLoading } = useSWR<TagSuggestionResponse>(key, fetcher, {
    dedupingInterval: 30_000,
  });
  return {
    suggestions: current ? data?.suggestions ?? [] : [],
    isLoading: Boolean(current && key && isLoading),
    error,
  };
}
