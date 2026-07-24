import { RefreshCw } from 'lucide-react';
import type { ReactNode } from 'react';

type WorkspaceLayoutProps = {
  title: string;
  count?: number;
  onRefresh: () => void;
  children: ReactNode;
};

export function WorkspaceLayout({ title, count, onRefresh, children }: WorkspaceLayoutProps) {
  return (
    <section className="workspace-view">
      <header className="workspace-header">
        <div>
          <h1>{title}</h1>
          {count !== undefined && <div className="muted">{count} {count === 1 ? 'item' : 'items'}</div>}
        </div>
        <button type="button" className="workspace-refresh" onClick={onRefresh}>
          <RefreshCw size={16} aria-hidden="true" />
          Refresh
        </button>
      </header>
      {children}
    </section>
  );
}

type WorkspaceStateProps = {
  isLoading: boolean;
  error: unknown;
  isEmpty: boolean;
  emptyLabel: string;
  errorLabel: string;
  onRetry: () => void;
  children: ReactNode;
};

export function WorkspaceState({
  isLoading,
  error,
  isEmpty,
  emptyLabel,
  errorLabel,
  onRetry,
  children,
}: WorkspaceStateProps) {
  if (isLoading) {
    return <div className="workspace-state muted" role="status">Loading...</div>;
  }

  if (error) {
    return (
      <div className="workspace-state workspace-error" role="alert">
        <span>{errorLabel}</span>
        <button type="button" className="workspace-retry" onClick={onRetry}>
          <RefreshCw size={16} aria-hidden="true" />
          Retry
        </button>
      </div>
    );
  }

  if (isEmpty) return <div className="workspace-state muted">{emptyLabel}</div>;

  return <>{children}</>;
}
