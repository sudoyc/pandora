import { useEffect, useState } from 'react';
import { DAEMON_URL } from '../api/client';
import type { DownloadEvent, DownloadProgressItem } from '../models';

const TERMINAL_STATUS: Record<string, string> = {
  download_complete: 'completed',
  download_complete_with_errors: 'completed_with_errors',
  download_error: 'failed',
  download_cancelled: 'cancelled',
  download_paused: 'paused',
  download_auth_failed: 'auth_failed',
};

function toWsUrl(baseUrl: string): string {
  return `${baseUrl.replace(/\/+$/, '').replace(/^http:/, 'ws:').replace(/^https:/, 'wss:')}/ws`;
}

export function useWebSocket(): DownloadProgressItem[] {
  const [messages, setMessages] = useState<DownloadProgressItem[]>([]);

  useEffect(() => {
    const ws = new WebSocket(toWsUrl(DAEMON_URL));

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as DownloadEvent;
        const eventName = data.event;
        if (!eventName || !data.gid) return;

        setMessages((prev) => {
          const current = prev.find((item) => item.gid === data.gid);
          const progress =
            eventName === 'download_progress' && data.total && data.page
              ? Math.min(100, Math.round((data.page / data.total) * 100))
              : eventName === 'download_complete' || eventName === 'download_complete_with_errors'
                ? 100
                : current?.progress ?? 0;

          const next: DownloadProgressItem = {
            gid: data.gid,
            title: eventName === 'download_queued' ? data.title : current?.title,
            status:
              eventName === 'download_progress'
                ? 'downloading'
                : TERMINAL_STATUS[eventName] ?? eventName.replace(/^download_/, ''),
            phase: eventName === 'download_progress' ? data.phase : current?.phase,
            progress,
            error:
              eventName === 'download_error' || eventName === 'download_auth_failed'
                ? data.error
                : eventName === 'download_paused'
                  ? data.reason
                  : current?.error,
          };

          const others = prev.filter((item) => item.gid !== data.gid);
          return [next, ...others].slice(0, 8);
        });
      } catch (error) {
        console.error('Failed to parse WS message', error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    return () => ws.close();
  }, []);

  return messages;
}
