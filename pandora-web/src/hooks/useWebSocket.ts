import { useEffect, useState } from 'react';
import { apiGet, DAEMON_URL } from '../api/client';
import type {
  DownloadEvent,
  DownloadProgressItem,
  DownloadTaskSnapshot,
  DownloadTaskStatus,
} from '../models';

const MAX_VISIBLE_DOWNLOADS = 8;
const RECONNECT_BASE_DELAY_MS = 500;
const RECONNECT_MAX_DELAY_MS = 5000;

const EVENT_STATUS: Record<DownloadEvent['event'], DownloadTaskStatus> = {
  download_queued: 'queued',
  download_progress: 'downloading',
  download_complete: 'completed',
  download_complete_with_errors: 'completed_with_errors',
  download_error: 'failed',
  download_cancelled: 'cancelled',
  download_paused: 'paused',
  download_auth_failed: 'failed',
};

function toWsUrl(baseUrl: string): string {
  return `${baseUrl.replace(/\/+$/, '').replace(/^http:/, 'ws:').replace(/^https:/, 'wss:')}/ws`;
}

function isDownloadEvent(value: unknown): value is DownloadEvent {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as { event?: unknown; gid?: unknown };
  return (
    typeof candidate.event === 'string'
    && Object.hasOwn(EVENT_STATUS, candidate.event)
    && typeof candidate.gid === 'string'
  );
}

function snapshotProgress(task: DownloadTaskSnapshot): number {
  if (task.status === 'completed' || task.status === 'completed_with_errors') return 100;
  if (task.total_pages <= 0) return 0;
  return Math.min(100, Math.round((task.downloaded_pages / task.total_pages) * 100));
}

function snapshotItems(tasks: DownloadTaskSnapshot[]): DownloadProgressItem[] {
  return tasks
    .slice()
    .sort((left, right) => right.created_at.localeCompare(left.created_at))
    .map((task) => ({
      gid: task.gid,
      title: task.title,
      status: task.status,
      progress: snapshotProgress(task),
      error: task.error || undefined,
    }))
    .slice(0, MAX_VISIBLE_DOWNLOADS);
}

function applyDownloadEvent(
  items: DownloadProgressItem[],
  data: DownloadEvent,
): DownloadProgressItem[] {
  const current = items.find((item) => item.gid === data.gid);
  const eventName = data.event;
  const progress =
    eventName === 'download_progress' && data.total && data.page
      ? Math.min(100, Math.round((data.page / data.total) * 100))
      : eventName === 'download_complete' || eventName === 'download_complete_with_errors'
        ? 100
        : current?.progress ?? 0;

  const next: DownloadProgressItem = {
    gid: data.gid,
    title: eventName === 'download_queued' ? data.title ?? current?.title : current?.title,
    status: EVENT_STATUS[eventName],
    phase: eventName === 'download_progress' ? data.phase : current?.phase,
    progress,
    error:
      eventName === 'download_error' || eventName === 'download_auth_failed'
        ? data.error
        : eventName === 'download_paused'
          ? data.reason
          : current?.error,
  };

  return [next, ...items.filter((item) => item.gid !== data.gid)].slice(
    0,
    MAX_VISIBLE_DOWNLOADS,
  );
}

export function useWebSocket(): DownloadProgressItem[] {
  const [messages, setMessages] = useState<DownloadProgressItem[]>([]);

  useEffect(() => {
    let disposed = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let reconnectAttempt = 0;
    let connectedOnce = false;
    let reconnectRequired = false;
    let reconcileGeneration = 0;
    let activeReconcile: { generation: number; events: DownloadEvent[] } | null = null;

    const reconcile = async (): Promise<boolean> => {
      const generation = ++reconcileGeneration;
      const pending = { generation, events: [] as DownloadEvent[] };
      activeReconcile = pending;

      try {
        const tasks = await apiGet<DownloadTaskSnapshot[]>('/downloads');
        if (disposed || generation !== reconcileGeneration) return false;

        const reconciled = pending.events.reduce(applyDownloadEvent, snapshotItems(tasks));
        setMessages(reconciled);
        return true;
      } catch (error) {
        if (!disposed && generation === reconcileGeneration) {
          console.error('Failed to reconcile downloads', error);
        }
        return false;
      } finally {
        if (activeReconcile?.generation === generation) activeReconcile = null;
      }
    };

    const initialReconcile = reconcile();

    function scheduleReconnect() {
      if (disposed || reconnectTimer !== undefined) return;
      reconnectRequired = true;
      const delay = Math.min(
        RECONNECT_BASE_DELAY_MS * (2 ** reconnectAttempt),
        RECONNECT_MAX_DELAY_MS,
      );
      reconnectAttempt += 1;
      reconnectTimer = setTimeout(() => {
        reconnectTimer = undefined;
        connect();
      }, delay);
    }

    function connect() {
      if (disposed) return;

      let nextSocket: WebSocket;
      try {
        nextSocket = new WebSocket(toWsUrl(DAEMON_URL));
      } catch (error) {
        console.error('WebSocket error:', error);
        scheduleReconnect();
        return;
      }
      socket = nextSocket;

      nextSocket.onopen = () => {
        if (disposed || socket !== nextSocket) return;
        reconnectAttempt = 0;

        if (connectedOnce || reconnectRequired) {
          reconnectRequired = false;
          void reconcile();
          connectedOnce = true;
          return;
        }

        connectedOnce = true;
        void initialReconcile.then((success) => {
          if (!success && !disposed && socket === nextSocket) void reconcile();
        });
      };

      nextSocket.onmessage = (event) => {
        try {
          const data: unknown = JSON.parse(event.data);
          if (!isDownloadEvent(data)) return;
          activeReconcile?.events.push(data);
          setMessages((current) => applyDownloadEvent(current, data));
        } catch (error) {
          console.error('Failed to parse WS message', error);
        }
      };

      nextSocket.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      nextSocket.onclose = () => {
        if (disposed || socket !== nextSocket) return;
        socket = null;
        scheduleReconnect();
      };
    }

    connect();

    return () => {
      disposed = true;
      reconcileGeneration += 1;
      if (reconnectTimer !== undefined) clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, []);

  return messages;
}
