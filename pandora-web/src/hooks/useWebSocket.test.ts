import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiGet } from '../api/client';
import type { DownloadTaskSnapshot } from '../models';
import { useWebSocket } from './useWebSocket';

vi.mock('../api/client', () => ({
  DAEMON_URL: 'http://127.0.0.1:7860',
  apiGet: vi.fn(),
}));

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];

  readonly url: string;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  open() {
    this.onopen?.(new Event('open'));
  }

  emit(payload: object) {
    this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(payload) }));
  }

  disconnect() {
    this.onclose?.(new CloseEvent('close'));
  }

  fail() {
    this.onerror?.(new Event('error'));
  }
}

function task(overrides: Partial<DownloadTaskSnapshot> = {}): DownloadTaskSnapshot {
  return {
    gid: '123',
    title: 'Fixture Download',
    total_pages: 4,
    status: 'downloading',
    downloaded_pages: 1,
    error: '',
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

describe('useWebSocket', () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.mocked(apiGet).mockReset().mockResolvedValue([]);
    vi.stubGlobal('WebSocket', FakeWebSocket);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('reconciles the initial snapshot and applies known live events', async () => {
    vi.mocked(apiGet).mockResolvedValue([task()]);
    const { result, unmount } = renderHook(() => useWebSocket());

    await waitFor(() => expect(result.current[0]).toMatchObject({
      gid: '123',
      title: 'Fixture Download',
      status: 'downloading',
      progress: 25,
    }));
    expect(apiGet).toHaveBeenCalledWith('/downloads');

    const socket = FakeWebSocket.instances[0];
    expect(socket.url).toBe('ws://127.0.0.1:7860/ws');
    act(() => socket.open());
    act(() => socket.emit({
      event: 'download_progress',
      gid: '123',
      phase: 'pages',
      page: 2,
      total: 4,
    }));

    expect(result.current[0]).toMatchObject({
      gid: '123',
      status: 'downloading',
      phase: 'pages',
      progress: 50,
    });

    act(() => socket.emit({ event: 'future_nonterminal_event', gid: '123' }));
    expect(result.current[0].progress).toBe(50);

    act(() => socket.emit({ event: 'download_complete', gid: '123' }));
    expect(result.current[0]).toMatchObject({
      gid: '123',
      status: 'completed',
      progress: 100,
    });

    unmount();
    expect(socket.close).toHaveBeenCalledOnce();
  });

  it('ignores a socket error emitted after effect cleanup', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { unmount } = renderHook(() => useWebSocket());
    const socket = FakeWebSocket.instances[0];

    unmount();
    act(() => socket.fail());

    expect(consoleError).not.toHaveBeenCalled();
  });

  it('reconnects and replaces stale state with the restarted daemon snapshot', async () => {
    vi.mocked(apiGet)
      .mockResolvedValueOnce([task()])
      .mockResolvedValueOnce([task({
        gid: '456',
        title: 'Recovered Download',
        status: 'queued',
        downloaded_pages: 2,
      })]);
    const { result } = renderHook(() => useWebSocket());

    await waitFor(() => expect(result.current[0]?.progress).toBe(25));
    const firstSocket = FakeWebSocket.instances[0];
    act(() => firstSocket.open());

    vi.useFakeTimers();
    act(() => firstSocket.disconnect());
    act(() => vi.advanceTimersByTime(499));
    expect(FakeWebSocket.instances).toHaveLength(1);
    act(() => vi.advanceTimersByTime(1));
    expect(FakeWebSocket.instances).toHaveLength(2);

    await act(async () => {
      FakeWebSocket.instances[1].open();
      await Promise.resolve();
    });

    expect(apiGet).toHaveBeenCalledTimes(2);
    expect(result.current).toHaveLength(1);
    expect(result.current[0]).toMatchObject({
      gid: '456',
      title: 'Recovered Download',
      status: 'queued',
      progress: 50,
    });
  });

  it('replays live events that arrive while a snapshot is pending', async () => {
    let resolveSnapshot!: (tasks: DownloadTaskSnapshot[]) => void;
    vi.mocked(apiGet).mockReturnValue(new Promise((resolve) => {
      resolveSnapshot = resolve;
    }));
    const { result } = renderHook(() => useWebSocket());
    const socket = FakeWebSocket.instances[0];

    act(() => socket.emit({
      event: 'download_progress',
      gid: '123',
      phase: 'pages',
      page: 2,
      total: 4,
    }));
    expect(result.current[0]?.progress).toBe(50);

    await act(async () => resolveSnapshot([task()]));

    expect(result.current[0]).toMatchObject({
      gid: '123',
      title: 'Fixture Download',
      phase: 'pages',
      progress: 50,
    });
  });
});
