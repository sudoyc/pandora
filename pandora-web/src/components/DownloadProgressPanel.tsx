import type { DownloadProgressItem } from '../models';

type DownloadProgressPanelProps = {
  items: DownloadProgressItem[];
};

export function DownloadProgressPanel({ items }: DownloadProgressPanelProps) {
  return (
    <div className="downloads-panel">
      <div className="panel-title">Recent Downloads</div>
      {items.length === 0 && <div className="muted">No events yet</div>}
      {items.map((item) => (
        <div key={item.gid} className="download-row">
          <div className="download-title">{item.title ?? item.gid}</div>
          <div className="download-status">
            {item.status}{item.phase ? ` · ${item.phase}` : ''}
          </div>
          <div className="progress-track">
            <div className="progress-bar" style={{ width: `${item.progress}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}
