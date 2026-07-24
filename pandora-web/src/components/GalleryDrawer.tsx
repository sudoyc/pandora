// pandora-web/src/components/GalleryDrawer.tsx
import * as Dialog from '@radix-ui/react-dialog';
import * as Tabs from '@radix-ui/react-tabs';
import { X } from 'lucide-react';
import { useLayoutEffect, useRef, useState } from 'react';
import useSWR from 'swr';
import { fetcher, imageProxyUrl } from '../api/client';
import type { GalleryDetail } from '../models';
import { Reader } from './Reader';

type GalleryDrawerProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  gid: string;
  token: string;
};

export const GalleryDrawer = ({ open, onOpenChange, gid, token }: GalleryDrawerProps) => {
  const [readerOpen, setReaderOpen] = useState(false);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const { data: detail, error, isLoading } = useSWR<GalleryDetail>(
    open ? `/gallery/${gid}/${token}` : null,
    fetcher,
  );

  useLayoutEffect(() => {
    if (open && document.activeElement instanceof HTMLElement) {
      returnFocusRef.current = document.activeElement;
    }
  }, [open]);

  return (
    <>
      <Dialog.Root open={open} onOpenChange={onOpenChange}>
        <Dialog.Portal>
          <Dialog.Overlay className="drawer-overlay" />
          <Dialog.Content
            className="drawer-content"
            aria-describedby={undefined}
            onEscapeKeyDown={(event) => {
              if (readerOpen) event.preventDefault();
            }}
            onCloseAutoFocus={(event) => {
              event.preventDefault();
              if (returnFocusRef.current?.isConnected) returnFocusRef.current.focus();
            }}
          >
            <Dialog.Title className="drawer-title">{detail?.title ?? 'Gallery details'}</Dialog.Title>
            <Dialog.Close asChild>
              <button
                type="button"
                className="drawer-close"
                aria-label="Close gallery details"
                title="Close gallery details"
              >
                <X size={20} aria-hidden="true" />
              </button>
            </Dialog.Close>
            <Tabs.Root defaultValue="info">
              <Tabs.List className="drawer-tabs">
                <Tabs.Trigger value="info">Info</Tabs.Trigger>
                <Tabs.Trigger value="tags">Tags</Tabs.Trigger>
                <Tabs.Trigger value="comments">Comments</Tabs.Trigger>
              </Tabs.List>

              <Tabs.Content value="info" className="drawer-panel">
                {isLoading && <div className="muted">Loading gallery detail...</div>}
                {error && <div className="error-text">Failed to load: {String(error)}</div>}
                {detail && (
                  <>
                    {detail.cover_url && (
                      <img src={imageProxyUrl(detail.cover_url)} alt={detail.title} className="drawer-cover" />
                    )}
                    {detail.title_jpn && <div className="muted">{detail.title_jpn}</div>}
                    <div className="detail-grid">
                      <span>Category</span><strong>{detail.category}</strong>
                      <span>Uploader</span><strong>{detail.uploader}</strong>
                      <span>Pages</span><strong>{detail.pages}</strong>
                      <span>Rating</span><strong>{detail.rating} ({detail.rating_count})</strong>
                      <span>Size</span><strong>{detail.size}</strong>
                    </div>
                    <div className="drawer-actions">
                      <button type="button" onClick={() => setReaderOpen(true)}>Read</button>
                    </div>
                  </>
                )}
              </Tabs.Content>

              <Tabs.Content value="tags" className="drawer-panel">
                {detail && Object.entries(detail.tags).map(([namespace, tags]) => (
                  <div key={namespace} className="tag-row">
                    <strong>{namespace}</strong>
                    <div>{tags.map((tag) => <span key={tag} className="tag-pill">{tag}</span>)}</div>
                  </div>
                ))}
              </Tabs.Content>

              <Tabs.Content value="comments" className="drawer-panel">
                {detail?.comments.length ? detail.comments.map((comment) => (
                  <article key={comment.id} className="comment-card">
                    <strong>{comment.user}</strong>
                    <p>{comment.comment}</p>
                  </article>
                )) : <div className="muted">No comments loaded.</div>}
              </Tabs.Content>
            </Tabs.Root>

            {readerOpen && detail && (
              <Reader gid={gid} token={token} pages={detail.pages} onClose={() => setReaderOpen(false)} />
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
};
