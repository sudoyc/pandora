// pandora-web/src/components/GalleryCard.tsx
export const GalleryCard = ({ gallery, onClick }: { gallery: any, onClick: () => void }) => (
  <div onClick={onClick} style={{ cursor: 'pointer', background: 'var(--bg-card)', padding: '10px', borderRadius: 'var(--border-radius)' }}>
    <img src={`http://127.0.0.1:7860/proxy/image?url=${encodeURIComponent(gallery.thumb_url)}`} alt={gallery.title} style={{ width: '100%', aspectRatio: '2/3', objectFit: 'cover' }} />
    <div style={{ fontSize: '0.8rem', fontWeight: 'bold' }}>{gallery.title}</div>
    <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{gallery.uploader}</div>
  </div>
);
