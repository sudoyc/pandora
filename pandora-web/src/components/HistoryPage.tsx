import { imageProxyUrl } from '../api/client';
import { useHistory } from '../hooks/useWorkspaceData';
import { WorkspaceLayout, WorkspaceState } from './WorkspaceLayout';

export function HistoryPage() {
  const { data, error, isLoading, mutate } = useHistory();

  return (
    <WorkspaceLayout
      title="History"
      count={data?.length}
      onRefresh={() => void mutate()}
    >
      <WorkspaceState
        isLoading={isLoading}
        error={error}
        isEmpty={Boolean(data && data.length === 0)}
        emptyLabel="No browsing history yet."
        errorLabel="Couldn't load history."
        onRetry={() => void mutate()}
      >
        <div className="workspace-list">
          {data?.map((item) => (
            <article key={item.gid} className="history-row">
              {item.thumb_url ? (
                <img src={imageProxyUrl(item.thumb_url)} alt="" className="history-thumb" loading="lazy" />
              ) : (
                <div className="history-thumb-placeholder" aria-hidden="true" />
              )}
              <div className="history-main">
                <strong>{item.title}</strong>
                <span className="muted">{item.category || item.uploader || 'Gallery'}</span>
                <span className="muted">
                  Page {Math.min(item.read_page + 1, Math.max(item.pages, 1))} of {item.pages || '?'}
                </span>
              </div>
              <span className="history-date">
                {new Date(item.time * 1000).toLocaleDateString()}
              </span>
            </article>
          ))}
        </div>
      </WorkspaceState>
    </WorkspaceLayout>
  );
}
