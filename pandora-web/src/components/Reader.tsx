import { galleryPageUrl } from '../api/client';

type ReaderProps = {
  gid: string;
  pages: number;
  onClose: () => void;
} & ({ token: string; pageUrl?: never } | { token?: never; pageUrl: (page: number) => string });

export function Reader({ gid, pages, onClose, ...source }: ReaderProps) {
  const imageUrls = Array.from(
    { length: pages },
    (_, index) => source.pageUrl !== undefined
      ? source.pageUrl(index + 1)
      : galleryPageUrl(gid, source.token, index + 1),
  );

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
