import { BookOpen } from 'lucide-react';
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
        <div className="gallery-grid library-grid" data-layout="grid" data-density="cozy">
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
                <span className="gallery-card__media">
                  <img src={libraryAssetUrl(item.thumb_url)} alt="" className="gallery-card__thumb" loading="lazy" />
                  <span className="gallery-card__category">Local</span>
                  <span className="library-read-icon" aria-hidden="true"><BookOpen size={18} /></span>
                </span>
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
          title={selected.title ?? `Gallery ${selected.gid}`}
          pages={selected.pages ?? 0}
          onClose={() => setSelected(null)}
          pageUrl={(page) => libraryFileUrl(String(selected.gid), `page/${page}`)}
        />
      )}
    </WorkspaceLayout>
  );
}
