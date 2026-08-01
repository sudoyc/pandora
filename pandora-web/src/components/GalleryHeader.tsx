import {
  ArrowRight,
  Grid3X3,
  LayoutGrid,
  List,
  RotateCcw,
  Rows3,
  Search,
  SlidersHorizontal,
  Trash2,
  X,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import type { FormEvent, KeyboardEvent } from 'react';
import type { GalleryDensity, GalleryLayout } from '../galleryDisplay';
import { galleryViewTitle, type GalleryView } from '../galleryView';
import { useTagSuggestions } from '../hooks/useTagSuggestions';
import {
  activeSearchFilterCount,
  ALL_CATEGORY_MASK,
  insertTagSuggestion,
  isSearchCriteriaActive,
  normalizeSearchCriteria,
  SEARCH_CATEGORIES,
  type SearchCriteria,
  type TagSuggestion,
} from '../search';

type GalleryHeaderProps = {
  view: GalleryView;
  searchHistory: SearchCriteria[];
  layout: GalleryLayout;
  density: GalleryDensity;
  onSearch: (criteria: SearchCriteria) => void;
  onClearSearch: () => void;
  onRemoveSearchHistory: (criteria: SearchCriteria) => void;
  onLayoutChange: (layout: GalleryLayout) => void;
  onDensityChange: (density: GalleryDensity) => void;
};

type BooleanSearchKey =
  | 'searchName'
  | 'searchTags'
  | 'searchDescription'
  | 'searchTorrent'
  | 'searchLowPowerTags'
  | 'disableLanguageFilter'
  | 'showExpunged';

const SEARCH_TARGETS: ReadonlyArray<{ key: BooleanSearchKey; label: string }> = [
  { key: 'searchName', label: 'Gallery name' },
  { key: 'searchTags', label: 'Tags' },
  { key: 'searchDescription', label: 'Description' },
  { key: 'searchTorrent', label: 'Torrent names' },
  { key: 'searchLowPowerTags', label: 'Low-power tags' },
];

function selectedCategoryCount(criteria: SearchCriteria) {
  const mask = criteria.category ?? ALL_CATEGORY_MASK;
  return SEARCH_CATEGORIES.filter(({ bit }) => (mask & bit) !== 0).length;
}

function historyLabel(criteria: SearchCriteria) {
  return criteria.query || 'Filtered search';
}

function historyMeta(criteria: SearchCriteria) {
  const details: string[] = [];
  if (criteria.category !== undefined) {
    details.push(`${selectedCategoryCount(criteria)} categories`);
  }
  if (criteria.minRating !== undefined) details.push(`${criteria.minRating}+ rating`);
  if (criteria.minPages !== undefined || criteria.maxPages !== undefined) {
    details.push(`${criteria.minPages ?? 1}-${criteria.maxPages ?? 'any'} pages`);
  }
  const targetCount = SEARCH_TARGETS.filter(({ key }) => criteria[key]).length;
  if (targetCount) details.push(`${targetCount} targets`);
  return details.join(' / ') || 'Quick search';
}

function filterDescriptions(criteria: SearchCriteria) {
  const filters: Array<{ key: string; label: string; remove: () => SearchCriteria }> = [];
  if (criteria.category !== undefined) {
    filters.push({
      key: 'category',
      label: `${selectedCategoryCount(criteria)} categories`,
      remove: () => ({ ...criteria, category: undefined }),
    });
  }
  if (criteria.minRating !== undefined) {
    filters.push({
      key: 'minRating',
      label: `Rating ${criteria.minRating}+`,
      remove: () => ({ ...criteria, minRating: undefined }),
    });
  }
  if (criteria.minPages !== undefined) {
    filters.push({
      key: 'minPages',
      label: `From ${criteria.minPages} pages`,
      remove: () => ({ ...criteria, minPages: undefined }),
    });
  }
  if (criteria.maxPages !== undefined) {
    filters.push({
      key: 'maxPages',
      label: `Up to ${criteria.maxPages} pages`,
      remove: () => ({ ...criteria, maxPages: undefined }),
    });
  }
  for (const { key, label } of SEARCH_TARGETS) {
    if (criteria[key]) {
      filters.push({
        key,
        label,
        remove: () => ({ ...criteria, [key]: undefined }),
      });
    }
  }
  if (criteria.disableLanguageFilter) {
    filters.push({
      key: 'disableLanguageFilter',
      label: 'Any language',
      remove: () => ({ ...criteria, disableLanguageFilter: undefined }),
    });
  }
  if (criteria.showExpunged) {
    filters.push({
      key: 'showExpunged',
      label: 'Show expunged',
      remove: () => ({ ...criteria, showExpunged: undefined }),
    });
  }
  return filters;
}

export function GalleryHeader({
  view,
  searchHistory,
  layout,
  density,
  onSearch,
  onClearSearch,
  onRemoveSearchHistory,
  onLayoutChange,
  onDensityChange,
}: GalleryHeaderProps) {
  const [draft, setDraft] = useState<SearchCriteria>(
    view.kind === 'search' ? view.criteria : { query: '' },
  );
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [assistOpen, setAssistOpen] = useState(false);
  const [activeSuggestion, setActiveSuggestion] = useState(-1);
  const { suggestions, isLoading: suggestionsLoading } = useTagSuggestions(
    draft.query,
    assistOpen,
  );

  const pageRangeError = draft.minPages !== undefined
    && draft.maxPages !== undefined
    && draft.minPages > draft.maxPages;
  const filterCount = activeSearchFilterCount(draft);
  const currentFilters = useMemo(
    () => view.kind === 'search' ? filterDescriptions(view.criteria) : [],
    [view],
  );
  const showSuggestions = draft.query.trim().length > 0
    && (suggestionsLoading || suggestions.length > 0);
  const showHistory = draft.query.length === 0 && searchHistory.length > 0;
  const selectedSuggestion = activeSuggestion >= 0 && activeSuggestion < suggestions.length
    ? activeSuggestion
    : -1;

  const executeSearch = () => {
    if (pageRangeError || !isSearchCriteriaActive(draft)) {
      if (pageRangeError) setFiltersOpen(true);
      return;
    }
    const criteria = normalizeSearchCriteria(draft);
    setDraft(criteria);
    setAssistOpen(false);
    setFiltersOpen(false);
    onSearch(criteria);
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    executeSearch();
  };

  const chooseSuggestion = (suggestion: TagSuggestion) => {
    setDraft((current) => ({
      ...current,
      query: insertTagSuggestion(current.query, suggestion),
      searchTags: true,
    }));
    setActiveSuggestion(-1);
  };

  const handleSearchKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (!showSuggestions || suggestions.length === 0) {
      if (event.key === 'Escape') setAssistOpen(false);
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveSuggestion((current) => (current + 1) % suggestions.length);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveSuggestion((current) => current <= 0 ? suggestions.length - 1 : current - 1);
    } else if (event.key === 'Enter' && selectedSuggestion >= 0) {
      event.preventDefault();
      chooseSuggestion(suggestions[selectedSuggestion]);
    } else if (event.key === 'Escape') {
      setAssistOpen(false);
    }
  };

  const setPageValue = (key: 'minPages' | 'maxPages', value: string) => {
    const parsed = value === '' ? undefined : Number(value);
    setDraft((current) => ({
      ...current,
      [key]: parsed !== undefined && Number.isInteger(parsed) && parsed > 0 ? parsed : undefined,
    }));
  };

  const toggleBoolean = (key: BooleanSearchKey) => {
    setDraft((current) => ({ ...current, [key]: current[key] ? undefined : true }));
  };

  const toggleCategory = (bit: number) => {
    setDraft((current) => {
      const nextMask = (current.category ?? ALL_CATEGORY_MASK) ^ bit;
      return { ...current, category: nextMask === ALL_CATEGORY_MASK ? undefined : nextMask };
    });
  };

  return (
    <header className="gallery-header">
      <div className="main-header">
        <div className="mobile-brand">PANDORA</div>
        <div
          className="search-area"
          onFocus={() => setAssistOpen(true)}
          onBlur={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget)) setAssistOpen(false);
          }}
        >
          <form onSubmit={handleSubmit} className="search-form" role="search" aria-label="Gallery search">
            <Search className="search-form__icon" size={19} aria-hidden="true" />
            <input
              type="search"
              role="combobox"
              value={draft.query}
              onChange={(event) => {
                setDraft((current) => ({ ...current, query: event.target.value }));
                setActiveSuggestion(-1);
              }}
              onKeyDown={handleSearchKeyDown}
              placeholder="Search galleries..."
              aria-label="Search title, artist, or tag"
              aria-autocomplete="list"
              aria-controls="search-assist"
              aria-expanded={assistOpen && (showSuggestions || showHistory)}
              aria-activedescendant={selectedSuggestion >= 0 ? `tag-suggestion-${selectedSuggestion}` : undefined}
            />
            <button
              type="button"
              className="search-form__filter"
              aria-label={filterCount ? `Search filters, ${filterCount} active` : 'Search filters'}
              aria-expanded={filtersOpen}
              aria-controls="advanced-search"
              title="Search filters"
              onClick={() => {
                setFiltersOpen((open) => !open);
                setAssistOpen(false);
              }}
            >
              <SlidersHorizontal size={18} aria-hidden="true" />
              {filterCount > 0 && <span className="search-filter-count">{filterCount}</span>}
            </button>
            <button
              type="submit"
              className="search-form__submit"
              aria-label="Search"
              title="Search"
              disabled={!isSearchCriteriaActive(draft) || pageRangeError}
            >
              <ArrowRight size={18} aria-hidden="true" />
            </button>
          </form>

          {assistOpen && (showSuggestions || showHistory) && (
            <div className="search-assist" id="search-assist">
              {showSuggestions && (
                <div role="listbox" aria-label="Tag suggestions">
                  <div className="search-assist__label">Tag suggestions</div>
                  {suggestionsLoading && suggestions.length === 0 && (
                    <div className="search-assist__status" role="status">Looking up tags...</div>
                  )}
                  {suggestions.map((suggestion, index) => (
                    <button
                      type="button"
                      role="option"
                      id={`tag-suggestion-${index}`}
                      aria-selected={selectedSuggestion === index}
                      className="tag-suggestion"
                      key={`${suggestion.namespace}:${suggestion.tag}`}
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => chooseSuggestion(suggestion)}
                    >
                      <span><strong>{suggestion.namespace}:</strong>{suggestion.tag}</span>
                      {suggestion.translation && <small>{suggestion.translation}</small>}
                    </button>
                  ))}
                </div>
              )}
              {showHistory && (
                <div aria-label="Recent searches">
                  <div className="search-assist__label">Recent searches</div>
                  {searchHistory.slice(0, 6).map((criteria) => (
                    <div className="recent-search-row" key={JSON.stringify(criteria)}>
                      <button
                        type="button"
                        className="recent-search-action"
                        onClick={() => {
                          setDraft(criteria);
                          setAssistOpen(false);
                          onSearch(criteria);
                        }}
                      >
                        <span>{historyLabel(criteria)}</span>
                        <small>{historyMeta(criteria)}</small>
                      </button>
                      <button
                        type="button"
                        className="recent-search-remove"
                        aria-label={`Remove ${historyLabel(criteria)} from recent searches`}
                        title="Remove recent search"
                        onClick={() => onRemoveSearchHistory(criteria)}
                      >
                        <Trash2 size={16} aria-hidden="true" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="gallery-controls">
          <div className="segmented" role="group" aria-label="Gallery layout">
            <button
              type="button"
              aria-label="Grid view"
              title="Grid view"
              aria-pressed={layout === 'grid'}
              onClick={() => onLayoutChange('grid')}
            >
              <LayoutGrid size={18} aria-hidden="true" />
            </button>
            <button
              type="button"
              aria-label="List view"
              title="List view"
              aria-pressed={layout === 'list'}
              onClick={() => onLayoutChange('list')}
            >
              <List size={19} aria-hidden="true" />
            </button>
          </div>
          <div className="segmented" role="group" aria-label="Gallery density">
            <button
              type="button"
              aria-label="Comfortable density"
              title="Comfortable density"
              aria-pressed={density === 'cozy'}
              onClick={() => onDensityChange('cozy')}
            >
              <Rows3 size={18} aria-hidden="true" />
            </button>
            <button
              type="button"
              aria-label="Compact density"
              title="Compact density"
              aria-pressed={density === 'compact'}
              onClick={() => onDensityChange('compact')}
            >
              <Grid3X3 size={18} aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>

      {filtersOpen && (
        <section className="search-panel" id="advanced-search" aria-label="Search filters">
          <div className="search-panel__head">
            <div>
              <strong>Refine search</strong>
              <span>{filterCount ? `${filterCount} active filters` : 'All galleries'}</span>
            </div>
            <button
              type="button"
              className="search-panel__close"
              aria-label="Close search filters"
              title="Close filters"
              onClick={() => setFiltersOpen(false)}
            >
              <X size={19} aria-hidden="true" />
            </button>
          </div>

          <div className="search-panel__grid">
            <fieldset className="search-filter-section search-filter-section--categories">
              <legend>Categories</legend>
              <div className="search-filter-actions">
                <button
                  type="button"
                  onClick={() => setDraft((current) => ({ ...current, category: undefined }))}
                >All</button>
                <button
                  type="button"
                  onClick={() => setDraft((current) => ({ ...current, category: 0 }))}
                >None</button>
              </div>
              <div className="search-category-options">
                {SEARCH_CATEGORIES.map(({ label, bit }) => (
                  <label key={label}>
                    <input
                      type="checkbox"
                      checked={((draft.category ?? ALL_CATEGORY_MASK) & bit) !== 0}
                      onChange={() => toggleCategory(bit)}
                    />
                    <span>{label}</span>
                  </label>
                ))}
              </div>
            </fieldset>

            <div className="search-filter-stack">
              <fieldset className="search-filter-section">
                <legend>Minimum rating</legend>
                <div className="rating-options" role="group" aria-label="Minimum rating">
                  {[undefined, 2, 3, 4, 5].map((rating) => (
                    <button
                      type="button"
                      key={rating ?? 'any'}
                      aria-pressed={draft.minRating === rating}
                      onClick={() => setDraft((current) => ({ ...current, minRating: rating }))}
                    >
                      {rating ? `${rating}+` : 'Any'}
                    </button>
                  ))}
                </div>
              </fieldset>

              <fieldset className="search-filter-section">
                <legend>Page count</legend>
                <div className="page-range">
                  <label>
                    <span>Minimum</span>
                    <input
                      type="number"
                      inputMode="numeric"
                      min="1"
                      value={draft.minPages ?? ''}
                      onChange={(event) => setPageValue('minPages', event.target.value)}
                    />
                  </label>
                  <span aria-hidden="true">to</span>
                  <label>
                    <span>Maximum</span>
                    <input
                      type="number"
                      inputMode="numeric"
                      min="1"
                      value={draft.maxPages ?? ''}
                      onChange={(event) => setPageValue('maxPages', event.target.value)}
                    />
                  </label>
                </div>
                {pageRangeError && (
                  <span className="search-field-error" role="alert">
                    Maximum pages must be at least the minimum.
                  </span>
                )}
              </fieldset>
            </div>

            <div className="search-filter-stack">
              <fieldset className="search-filter-section">
                <legend>Search targets</legend>
                <div className="search-toggle-options">
                  {SEARCH_TARGETS.map(({ key, label }) => (
                    <label key={key}>
                      <input
                        type="checkbox"
                        checked={Boolean(draft[key])}
                        onChange={() => toggleBoolean(key)}
                      />
                      <span>{label}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
              <fieldset className="search-filter-section">
                <legend>Visibility</legend>
                <div className="search-toggle-options search-toggle-options--inline">
                  <label>
                    <input
                      type="checkbox"
                      checked={Boolean(draft.disableLanguageFilter)}
                      onChange={() => toggleBoolean('disableLanguageFilter')}
                    />
                    <span>Any language</span>
                  </label>
                  <label>
                    <input
                      type="checkbox"
                      checked={Boolean(draft.showExpunged)}
                      onChange={() => toggleBoolean('showExpunged')}
                    />
                    <span>Show expunged</span>
                  </label>
                </div>
              </fieldset>
            </div>
          </div>

          <div className="search-panel__footer">
            <button
              type="button"
              className="search-reset"
              onClick={() => setDraft({ query: draft.query })}
            >
              <RotateCcw size={17} aria-hidden="true" /> Reset filters
            </button>
            <button
              type="button"
              className="search-apply"
              disabled={!isSearchCriteriaActive(draft) || pageRangeError}
              onClick={executeSearch}
            >
              <Search size={17} aria-hidden="true" /> Apply search
            </button>
          </div>
        </section>
      )}

      <div className="page-heading">
        <div>
          <div className="eyebrow">LIVE INDEX</div>
          <h1>{galleryViewTitle(view)}</h1>
          {view.kind === 'search' && currentFilters.length > 0 && (
            <div className="active-search-filters" aria-label="Active search filters">
              {currentFilters.map((filter) => (
                <button
                  type="button"
                  className="search-filter-chip"
                  key={filter.key}
                  aria-label={`Remove ${filter.label} filter`}
                  onClick={() => {
                    const next = normalizeSearchCriteria(filter.remove());
                    setDraft(next);
                    if (isSearchCriteriaActive(next)) onSearch(next);
                    else onClearSearch();
                  }}
                >
                  <span>{filter.label}</span>
                  <X size={14} aria-hidden="true" />
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
