import type { GalleryView } from '../galleryView';
import { useGalleries } from '../hooks/useGalleries';
import type { GalleryListItem } from '../models';
import { GalleryCard } from './GalleryCard';

type GalleryFeedProps = {
  view: GalleryView;
  onSelect: (gallery: GalleryListItem) => void;
};

export function GalleryFeed({ view, onSelect }: GalleryFeedProps) {
  const { galleries, loadMore, hasMore, isLoading, error } = useGalleries(view);

  return (
    <>
      {error && <div className="error-text">Failed to load galleries: {String(error)}</div>}
      <div className="gallery-grid">
        {galleries.map((gallery) => (
          <GalleryCard
            key={gallery.gid}
            gallery={gallery}
            onClick={() => onSelect(gallery)}
          />
        ))}
        {isLoading && <div className="muted">Loading...</div>}
      </div>
      {hasMore && (
        <button type="button" className="load-more" onClick={loadMore} disabled={isLoading}>
          Load More
        </button>
      )}
    </>
  );
}
