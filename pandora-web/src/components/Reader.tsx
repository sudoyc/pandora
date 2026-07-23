import { galleryPageUrl } from '../api/client';

interface ReaderProps {
  gid: string;
  token: string;
  pages: number;
  onClose: () => void;
}

export function Reader({ gid, token, pages, onClose }: ReaderProps) {
  const imageUrls = Array.from({ length: pages }, (_, index) => galleryPageUrl(gid, token, index + 1));

  return (
    <div className="reader-shell">
      <div className="reader-toolbar">
        <span>{pages} pages</span>
        <button type="button" onClick={onClose}>Exit</button>
      </div>
      <div className="reader-scroll">
        {imageUrls.map((url, index) => (
          <img
            key={url}
            src={url}
            alt={`Page ${index + 1}`}
            className="reader-page"
            loading={index < 2 ? 'eager' : 'lazy'}
          />
        ))}
      </div>
    </div>
  );
}
