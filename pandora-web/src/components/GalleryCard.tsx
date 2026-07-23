// pandora-web/src/components/GalleryCard.tsx
import { imageProxyUrl } from '../api/client';
import type { GalleryListItem } from '../models';

type GalleryCardProps = {
  gallery: GalleryListItem;
  onClick: () => void;
};

export const GalleryCard = ({ gallery, onClick }: GalleryCardProps) => (
  <button type="button" onClick={onClick} className="gallery-card">
    {gallery.thumb_url ? (
      <img src={imageProxyUrl(gallery.thumb_url)} alt={gallery.title} className="gallery-card__thumb" loading="lazy" />
    ) : (
      <div className="gallery-card__placeholder">No preview</div>
    )}
    <div className="gallery-card__body">
      <div className="gallery-card__title">{gallery.title}</div>
      <div className="gallery-card__meta">{gallery.uploader || gallery.category || `${gallery.pages} pages`}</div>
    </div>
  </button>
);
