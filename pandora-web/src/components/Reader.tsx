import { X } from 'lucide-react';
import { useEffect, useRef } from 'react';
import type { KeyboardEvent } from 'react';
import { galleryPageUrl } from '../api/client';

type ReaderProps = {
  gid: string;
  pages: number;
  onClose: () => void;
} & ({ token: string; pageUrl?: never } | { token?: never; pageUrl: (page: number) => string });

export function Reader({ gid, pages, onClose, ...source }: ReaderProps) {
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
      event.preventDefault();
      event.stopPropagation();
      closeButtonRef.current?.focus();
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
        <span>{pages} pages</span>
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
