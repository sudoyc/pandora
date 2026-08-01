import { ZoomIn, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import type { KeyboardEvent } from 'react';
import { galleryPageUrl } from '../api/client';
import { useMediaQuery } from '../hooks/useMediaQuery';

type ReaderProps = {
  gid: string;
  title?: string;
  pages: number;
  onClose: () => void;
} & ({ token: string; pageUrl?: never } | { token?: never; pageUrl: (page: number) => string });

export function Reader({ gid, title, pages, onClose, ...source }: ReaderProps) {
  const [readerWidth, setReaderWidth] = useState(680);
  const isMobile = useMediaQuery('(max-width: 760px)');
  const zoomRef = useRef<HTMLInputElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const imageUrls = Array.from(
    { length: pages },
    (_, index) => source.pageUrl !== undefined
      ? source.pageUrl(index + 1)
      : galleryPageUrl(gid, source.token, index + 1),
  );

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    closeButtonRef.current?.focus();

    return () => {
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, []);

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      onClose();
    } else if (event.key === 'Tab') {
      const first = zoomRef.current;
      const last = closeButtonRef.current;
      if (!first) {
        event.preventDefault();
        last?.focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
  };

  return (
    <div
      className="reader-shell"
      role="dialog"
      aria-modal="true"
      aria-label="Gallery reader"
      onKeyDown={handleKeyDown}
    >
      <div className="reader-toolbar">
        <div className="reader-title">{title ?? `Gallery ${gid}`}</div>
        <div className="reader-counter" aria-label={`Page 1 of ${pages}`}>
          <span aria-hidden="true">01 / {pages}</span>
          <span className="sr-only">{pages} pages</span>
        </div>
        <div className="reader-tools">
          {!isMobile && (
            <label>
              <ZoomIn size={17} aria-hidden="true" />
              <input
                ref={zoomRef}
                type="range"
                min={420}
                max={960}
                value={readerWidth}
                aria-label="Reader width"
                onChange={(event) => setReaderWidth(Number(event.target.value))}
              />
            </label>
          )}
          <button
            ref={closeButtonRef}
            type="button"
            className="reader-close"
            onClick={onClose}
            aria-label="Exit reader"
            title="Exit reader"
          >
            <X size={20} aria-hidden="true" />
          </button>
        </div>
      </div>
      <div className="reader-scroll">
        <div
          className="reader-pages"
          style={{ '--reader-width': `${readerWidth}px` } as CSSProperties}
        >
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
    </div>
  );
}
