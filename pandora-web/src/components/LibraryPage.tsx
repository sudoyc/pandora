import { useState } from 'react';
import { DAEMON_URL, libraryFileUrl } from '../api/client';
import { useLibrary } from '../hooks/useWorkspaceData';
import type { LibraryItem } from '../models';
import { Reader } from './Reader';
import { WorkspaceLayout, WorkspaceState } from './WorkspaceLayout';

function libraryAssetUrl(path: string): string {
  if (path.startsWith('http')) return path;
  return `${DAEMON_URL.replace(/\/+$/, '')}/${path.replace(/^\/+/, '')}`;
}

export function LibraryPage() {
  const { data, error, isLoading, mutate } = useLibrary();
  const [selected, setSelected] = useState<LibraryItem | null>(null);

  return (
    <WorkspaceLayout
      title="Library"
      count={data?.length}
      onRefresh={() => void mutate()}
    >
      <WorkspaceState
        isLoading={isLoading}
        error={error}
        isEmpty={Boolean(data && data.length === 0)}
        emptyLabel="No downloaded galleries yet."
        errorLabel="Couldn't load library."
        onRetry={() => void mutate()}
      >
        <div className="gallery-grid library-grid">
          {data?.map((item) => {
            const gid = String(item.gid);
            const title = item.title ?? `Gallery ${gid}`;
            const pages = item.pages ?? 0;
            return (
              <button
                key={gid}
                type="button"
                className="gallery-card library-card"
                disabled={pages <= 0}
                aria-label={`Read ${title}`}
                onClick={() => setSelected(item)}
              >
                <img src={libraryAssetUrl(item.thumb_url)} alt={title} className="gallery-card__thumb" loading="lazy" />
                <span className="gallery-card__body">
                  <span className="gallery-card__title">{title}</span>
                  <span className="gallery-card__meta">{pages ? `${pages} pages` : 'No pages'}</span>
                </span>
              </button>
            );
          })}
        </div>
      </WorkspaceState>

      {selected && (
        <Reader
          gid={String(selected.gid)}
          pages={selected.pages ?? 0}
          onClose={() => setSelected(null)}
          pageUrl={(page) => libraryFileUrl(String(selected.gid), `page/${page}`)}
        />
      )}
    </WorkspaceLayout>
  );
}
