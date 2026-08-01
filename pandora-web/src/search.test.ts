import { describe, expect, it } from 'vitest';
import {
  ALL_CATEGORY_MASK,
  buildSearchPath,
  insertTagSuggestion,
  normalizeSearchCriteria,
  searchCriteriaKey,
} from './search';

describe('search criteria', () => {
  it('serializes every supported daemon search parameter', () => {
    expect(buildSearchPath({
      query: '  female:stockings  ',
      category: ALL_CATEGORY_MASK - 2,
      minRating: 4,
      minPages: 10,
      maxPages: 30,
      searchName: true,
      searchTags: true,
      searchDescription: true,
      searchTorrent: true,
      searchLowPowerTags: true,
      disableLanguageFilter: true,
      showExpunged: true,
    }, 2)).toBe(
      '/search?keyword=female%3Astockings&page=2&category=1021&min_rating=4'
      + '&search_name=true&search_tags=true&search_description=true&search_torrent=true'
      + '&search_low_power_tags=true&disable_language_filter=true&show_expunged=true'
      + '&min_pages=10&max_pages=30',
    );
  });

  it('normalizes persisted values before they become request state', () => {
    expect(normalizeSearchCriteria({
      query: '  fixture  ',
      category: 2048,
      minRating: 8,
      minPages: -1,
      maxPages: 25.5,
      searchTags: true,
      showExpunged: false,
    })).toEqual({ query: 'fixture', searchTags: true });
  });

  it('uses one stable key for equivalent searches', () => {
    expect(searchCriteriaKey({ query: ' fixture ', minRating: 4 })).toBe(
      searchCriteriaKey({ minRating: 4, query: 'fixture' }),
    );
  });

  it('replaces only the unfinished term when a tag suggestion is chosen', () => {
    expect(insertTagSuggestion('language:english stock', {
      namespace: 'female',
      tag: 'stockings',
      translation: 'Silk stockings',
    })).toBe('language:english female:"stockings$" ');
  });
});
