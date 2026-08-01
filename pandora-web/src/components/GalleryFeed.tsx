import { Check, LoaderCircle } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { GalleryView } from '../galleryView';
import type { GalleryDensity, GalleryLayout } from '../galleryDisplay';
import { useGalleries } from '../hooks/useGalleries';
import type { GalleryListItem } from '../models';
import { searchCriteriaKey } from '../search';
import { GalleryCard } from './GalleryCard';

type GalleryFeedProps = {
  view: GalleryView;
  layout: GalleryLayout;
  density: GalleryDensity;
  onSelect: (gallery: GalleryListItem) => void;
};

export function GalleryFeed({ view, layout, density, onSelect }: GalleryFeedProps) {
  const {
    galleries,
    loadMore,
    hasMore,
    isLoading,
    isLoadingMore,
    isRefreshing,
    isReachingEnd,
    isPaginated,
    error,
    mutate,
  } = useGalleries(view);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const viewKey = view.kind === 'search' ? searchCriteriaKey(view.criteria) : view.kind;
  const previousViewKey = useRef(viewKey);
  const [automaticPaging] = useState(() => typeof window !== 'undefined' && 'IntersectionObserver' in window);
  const errorMessage = error instanceof Error ? error.message : String(error);

  useEffect(() => {
    if (previousViewKey.current === viewKey) return;
    previousViewKey.current = viewKey;
    if (document.scrollingElement) document.scrollingElement.scrollTop = 0;
  }, [viewKey]);

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!automaticPaging || !sentinel || !hasMore || isLoadingMore) return undefined;

    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) loadMore();
    }, { rootMargin: '640px 0px' });
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [automaticPaging, hasMore, isLoadingMore, loadMore]);

  return (
    <section className="gallery-feed" aria-busy={isLoading || isLoadingMore}>
      <div className="feed-summary">
        <span>{galleries.length} {galleries.length === 1 ? 'result' : 'results'}</span>
        {isRefreshing && <span>Updating...</span>}
      </div>
      {error && (
        <div className="feed-error" role="alert">
          <div><strong>Gallery service unavailable</strong><span>{errorMessage}</span></div>
          <button type="button" onClick={() => void mutate()}>Retry</button>
        </div>
      )}
      {!isLoading && !error && galleries.length === 0 && (
        <div className="gallery-empty">No galleries found.</div>
      )}
      <div className="gallery-grid" data-layout={layout} data-density={density}>
        {galleries.map((gallery) => (
          <GalleryCard
            key={`${gallery.gid}:${gallery.token}`}
            gallery={gallery}
            onClick={() => onSelect(gallery)}
          />
        ))}
        {isLoading && galleries.length === 0 && Array.from({ length: 6 }, (_, index) => (
          <div className="gallery-skeleton" key={index} aria-hidden="true"><span /><span /><span /></div>
        ))}
      </div>

      {isPaginated && !error && galleries.length > 0 && (
        <>
          <div className="infinite-scroll-sentinel" ref={sentinelRef} aria-hidden="true" />
          <div className="feed-pagination" role="status" aria-live="polite">
            {isLoadingMore && (
              <span className="feed-pagination__status">
                <LoaderCircle size={17} aria-hidden="true" /> Loading next page...
              </span>
            )}
            {!isLoadingMore && hasMore && (
              <button type="button" className="load-more" onClick={loadMore}>
                Load next page
              </button>
            )}
            {!isLoadingMore && isReachingEnd && (
              <span className="feed-pagination__status feed-pagination__status--complete">
                <Check size={17} aria-hidden="true" /> End of results
              </span>
            )}
          </div>
        </>
      )}
    </section>
  );
}
