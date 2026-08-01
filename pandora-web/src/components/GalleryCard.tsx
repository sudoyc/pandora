import { Star } from 'lucide-react';
import { useState } from 'react';
import { imageProxyUrl } from '../api/client';
import type { GalleryListItem } from '../models';

type GalleryCardProps = {
  gallery: GalleryListItem;
  onClick: () => void;
};

export const GalleryCard = ({ gallery, onClick }: GalleryCardProps) => {
  const [imageFailed, setImageFailed] = useState(false);

  return (
    <button
      type="button"
      onClick={onClick}
      className="gallery-card"
      aria-label={`Open ${gallery.title}`}
    >
      <span className="gallery-card__media">
        {gallery.thumb_url && !imageFailed ? (
          <img
            src={imageProxyUrl(gallery.thumb_url)}
            alt=""
            className="gallery-card__thumb"
            width={gallery.thumb_width || undefined}
            height={gallery.thumb_height || undefined}
            loading="lazy"
            onError={() => setImageFailed(true)}
          />
        ) : (
          <span className="gallery-card__placeholder">Preview unavailable</span>
        )}
        {gallery.category && <span className="gallery-card__category">{gallery.category}</span>}
      </span>
      <div className="gallery-card__body">
        <div className="gallery-card__title">{gallery.title}</div>
        <div className="gallery-card__meta">
          <span>{gallery.pages} pages</span>
          <span className="gallery-card__rating"><Star size={12} aria-hidden="true" />{gallery.rating.toFixed(2)}</span>
        </div>
        {gallery.uploader && <div className="gallery-card__uploader">{gallery.uploader}</div>}
      </div>
    </button>
  );
};
