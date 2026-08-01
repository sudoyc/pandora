import * as Dialog from '@radix-ui/react-dialog';
import * as Tabs from '@radix-ui/react-tabs';
import { BookOpen, Star, X } from 'lucide-react';
import { useLayoutEffect, useRef, useState } from 'react';
import useSWR from 'swr';
import { fetcher, imageProxyUrl } from '../api/client';
import { useMediaQuery } from '../hooks/useMediaQuery';
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
  const isMobile = useMediaQuery('(max-width: 760px)');
  const { data: detail, error, isLoading } = useSWR<GalleryDetail>(
    open ? `/gallery/${gid}/${token}` : null,
    fetcher,
  );

  useLayoutEffect(() => {
    if (open && document.activeElement instanceof HTMLElement) {
      returnFocusRef.current = document.activeElement;
    }
  }, [gid, open]);

  return (
    <>
      <Dialog.Root open={open} onOpenChange={onOpenChange} modal={isMobile}>
        <Dialog.Portal>
          <Dialog.Overlay className="drawer-overlay" />
          <Dialog.Content
            className="drawer-content"
            aria-describedby={undefined}
            onEscapeKeyDown={(event) => {
              if (readerOpen) event.preventDefault();
            }}
            onInteractOutside={(event) => {
              if (!isMobile) event.preventDefault();
            }}
            onCloseAutoFocus={(event) => {
              event.preventDefault();
              if (returnFocusRef.current?.isConnected) returnFocusRef.current.focus();
            }}
          >
            <div className="drawer-head">
              <span>Selected / {gid}</span>
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
            </div>

            <div className="drawer-scroll">
              {isLoading && (
                <div className="drawer-state" role="status">
                  <Dialog.Title className="drawer-title">Gallery details</Dialog.Title>
                  <span>Loading gallery detail...</span>
                </div>
              )}
              {error && (
                <div className="drawer-state error-text" role="alert">
                  <Dialog.Title className="drawer-title">Gallery details</Dialog.Title>
                  <span>Failed to load: {String(error)}</span>
                </div>
              )}
              {detail && (
                <>
                  <section className="drawer-hero">
                    {detail.cover_url ? (
                      <img src={imageProxyUrl(detail.cover_url)} alt="" className="drawer-cover" />
                    ) : (
                      <div className="drawer-cover drawer-cover--empty">No preview</div>
                    )}
                    <div className="drawer-summary">
                      <span className="drawer-category">{detail.category}</span>
                      <Dialog.Title className="drawer-title">{detail.title}</Dialog.Title>
                      {detail.title_jpn && <div className="drawer-subtitle">{detail.title_jpn}</div>}
                      <div className="drawer-score">
                        <Star size={16} aria-hidden="true" />
                        <strong>{detail.rating}</strong>
                        <span>{detail.rating_count} ratings</span>
                      </div>
                    </div>
                  </section>

                  <Tabs.Root key={gid} defaultValue="info" className="drawer-tab-root">
                    <Tabs.List className="drawer-tabs">
                      <Tabs.Trigger value="info">Info</Tabs.Trigger>
                      <Tabs.Trigger value="tags">Tags</Tabs.Trigger>
                      <Tabs.Trigger value="comments">Comments</Tabs.Trigger>
                    </Tabs.List>

                    <Tabs.Content value="info" className="drawer-panel">
                      <dl className="detail-grid">
                        <dt>Uploader</dt><dd>{detail.uploader}</dd>
                        <dt>Pages</dt><dd>{detail.pages}</dd>
                        <dt>Posted</dt><dd>{detail.posted}</dd>
                        <dt>Size</dt><dd>{detail.size}</dd>
                        <dt>Favorites</dt><dd>{detail.favorite_count}</dd>
                      </dl>
                    </Tabs.Content>

                    <Tabs.Content value="tags" className="drawer-panel">
                      {Object.entries(detail.tags).map(([namespace, tags]) => (
                        <div key={namespace} className="tag-row">
                          <strong>{namespace}</strong>
                          <div>{tags.map((tag) => <span key={tag} className="tag-pill">{tag}</span>)}</div>
                        </div>
                      ))}
                    </Tabs.Content>

                    <Tabs.Content value="comments" className="drawer-panel">
                      {detail.comments.length ? detail.comments.map((comment) => (
                        <article key={comment.id} className="comment-card">
                          <strong>{comment.user}</strong>
                          <p>{comment.comment}</p>
                        </article>
                      )) : <div className="muted">No comments loaded.</div>}
                    </Tabs.Content>
                  </Tabs.Root>
                </>
              )}
            </div>

            {detail && (
              <div className="drawer-actions">
                <button type="button" aria-label="Read" onClick={() => setReaderOpen(true)}>
                  <BookOpen size={18} aria-hidden="true" />
                  Read now
                </button>
              </div>
            )}

            {readerOpen && detail && (
              <Reader
                gid={gid}
                token={token}
                title={detail.title}
                pages={detail.pages}
                onClose={() => setReaderOpen(false)}
              />
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
};
