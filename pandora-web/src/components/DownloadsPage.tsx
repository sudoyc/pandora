import { useEffect } from 'react';
import type { DownloadProgressItem, DownloadTaskSnapshot } from '../models';
import { useDownloads } from '../hooks/useWorkspaceData';
import { WorkspaceLayout, WorkspaceState } from './WorkspaceLayout';

type DownloadsPageProps = {
  liveItems: DownloadProgressItem[];
};

function taskProgress(task: DownloadTaskSnapshot): number {
  if (task.status === 'completed' || task.status === 'completed_with_errors') return 100;
  if (task.total_pages <= 0) return 0;
  return Math.min(100, Math.round((task.downloaded_pages / task.total_pages) * 100));
}

export function DownloadsPage({ liveItems }: DownloadsPageProps) {
  const { data, error, isLoading, mutate } = useDownloads();

  useEffect(() => {
    if (liveItems.length > 0) void mutate();
  }, [liveItems, mutate]);

  const tasks = data
    ?.slice()
    .sort((left, right) => right.created_at.localeCompare(left.created_at));
  const liveByGid = new Map(liveItems.map((item) => [item.gid, item]));

  return (
    <WorkspaceLayout
      title="Downloads"
      count={data?.length}
      onRefresh={() => void mutate()}
    >
      <WorkspaceState
        isLoading={isLoading}
        error={error}
        isEmpty={Boolean(data && data.length === 0)}
        emptyLabel="No downloads yet."
        errorLabel="Couldn't load downloads."
        onRetry={() => void mutate()}
      >
        <div className="workspace-list downloads-list">
          {tasks?.map((task) => {
            const live = liveByGid.get(task.gid);
            const progress = live?.progress ?? taskProgress(task);
            const status = live?.status ?? task.status;
            return (
              <article key={task.gid} className="download-detail-row">
                <div className="download-detail-heading">
                  <strong>{task.title}</strong>
                  <span className="download-status">{status}{live?.phase ? ` · ${live.phase}` : ''}</span>
                </div>
                <div className="download-detail-meta">
                  <span>{task.downloaded_pages}/{task.total_pages || '?'} pages</span>
                  <span>{progress}%</span>
                </div>
                <div
                  className="progress-track"
                  role="progressbar"
                  aria-label={`${progress}% complete`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={progress}
                >
                  <div className="progress-bar" style={{ width: `${progress}%` }} />
                </div>
                {(live?.error || task.error) && (
                  <span className="error-text">{live?.error ?? task.error}</span>
                )}
              </article>
            );
          })}
        </div>
      </WorkspaceState>
    </WorkspaceLayout>
  );
}
