export const ALL_CATEGORY_MASK = 1023;

export const SEARCH_CATEGORIES = [
  { label: 'Misc', bit: 1 },
  { label: 'Doujinshi', bit: 2 },
  { label: 'Manga', bit: 4 },
  { label: 'Artist CG', bit: 8 },
  { label: 'Game CG', bit: 16 },
  { label: 'Image Set', bit: 32 },
  { label: 'Cosplay', bit: 64 },
  { label: 'Asian Porn', bit: 128 },
  { label: 'Non-H', bit: 256 },
  { label: 'Western', bit: 512 },
] as const;

export type SearchCriteria = {
  query: string;
  category?: number;
  minRating?: number;
  minPages?: number;
  maxPages?: number;
  searchName?: boolean;
  searchTags?: boolean;
  searchDescription?: boolean;
  searchTorrent?: boolean;
  searchLowPowerTags?: boolean;
  disableLanguageFilter?: boolean;
  showExpunged?: boolean;
};

export type TagSuggestion = {
  namespace: string;
  tag: string;
  translation: string;
};

const BOOLEAN_PARAMETERS = [
  ['searchName', 'search_name'],
  ['searchTags', 'search_tags'],
  ['searchDescription', 'search_description'],
  ['searchTorrent', 'search_torrent'],
  ['searchLowPowerTags', 'search_low_power_tags'],
  ['disableLanguageFilter', 'disable_language_filter'],
  ['showExpunged', 'show_expunged'],
] as const satisfies ReadonlyArray<[keyof SearchCriteria, string]>;

function positiveInteger(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isInteger(value) && value > 0
    ? value
    : undefined;
}

export function normalizeSearchCriteria(
  value: Partial<SearchCriteria> | null | undefined,
): SearchCriteria {
  const normalized: SearchCriteria = {
    query: typeof value?.query === 'string' ? value.query.trim() : '',
  };

  if (typeof value?.category === 'number'
    && Number.isInteger(value.category)
    && value.category >= 0
    && value.category < ALL_CATEGORY_MASK) {
    normalized.category = value.category;
  }
  if (typeof value?.minRating === 'number'
    && Number.isInteger(value.minRating)
    && value.minRating >= 1
    && value.minRating <= 5) {
    normalized.minRating = value.minRating;
  }

  const minPages = positiveInteger(value?.minPages);
  const maxPages = positiveInteger(value?.maxPages);
  if (minPages !== undefined) normalized.minPages = minPages;
  if (maxPages !== undefined) normalized.maxPages = maxPages;

  for (const [key] of BOOLEAN_PARAMETERS) {
    if (value?.[key] === true) normalized[key] = true as never;
  }

  return normalized;
}

export function isSearchCriteriaActive(criteria: SearchCriteria): boolean {
  const normalized = normalizeSearchCriteria(criteria);
  return normalized.query.length > 0 || Object.keys(normalized).length > 1;
}

export function searchCriteriaKey(criteria: SearchCriteria): string {
  return buildSearchPath(criteria, 0);
}

export function buildSearchPath(
  criteria: SearchCriteria,
  page: number,
  nextGid?: string,
): string {
  const normalized = normalizeSearchCriteria(criteria);
  const parameters = new URLSearchParams();
  parameters.set('keyword', normalized.query);
  if (nextGid) parameters.set('next', nextGid);
  else parameters.set('page', String(page));
  if (normalized.category !== undefined) parameters.set('category', String(normalized.category));
  if (normalized.minRating !== undefined) parameters.set('min_rating', String(normalized.minRating));
  for (const [key, parameter] of BOOLEAN_PARAMETERS) {
    if (normalized[key] === true) parameters.set(parameter, 'true');
  }
  if (normalized.minPages !== undefined) parameters.set('min_pages', String(normalized.minPages));
  if (normalized.maxPages !== undefined) parameters.set('max_pages', String(normalized.maxPages));
  return `/search?${parameters.toString()}`;
}

export function activeSearchFilterCount(criteria: SearchCriteria): number {
  const normalized = normalizeSearchCriteria(criteria);
  return Object.entries(normalized).reduce((count, [key, value]) => (
    key !== 'query' && value !== undefined && value !== false ? count + 1 : count
  ), 0);
}

export function suggestionTerm(query: string): string {
  const lastTerm = query.trimEnd().match(/(?:^|\s)(\S+)$/)?.[1] ?? '';
  if (lastTerm.includes('$"')) return '';
  return lastTerm
    .replace(/^[^:\s]+:/, '')
    .replace(/^["']+/, '')
    .replace(/[$"']+$/, '');
}

export function insertTagSuggestion(query: string, suggestion: TagSuggestion): string {
  const trimmed = query.trimEnd();
  const termStart = trimmed.search(/\S+$/);
  const prefix = termStart >= 0 ? trimmed.slice(0, termStart) : '';
  const escapedTag = suggestion.tag.replace(/(["\\])/g, '\\$1');
  const tag = suggestion.namespace === 'misc'
    ? `"${escapedTag}$"`
    : `${suggestion.namespace}:"${escapedTag}$"`;
  return `${prefix}${tag} `;
}
