import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useWebSocket } from './useWebSocket';

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];

  readonly url: string;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  emit(payload: object) {
    this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(payload) }));
  }
}

describe('useWebSocket', () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeWebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('reduces queued, progress, and terminal events for one download', () => {
    const { result, unmount } = renderHook(() => useWebSocket());
    const socket = FakeWebSocket.instances[0];

    expect(socket.url).toBe('ws://127.0.0.1:7860/ws');
    act(() => socket.emit({
      event: 'download_queued',
      gid: '123',
      title: 'Fixture Download',
    }));
    act(() => socket.emit({
      event: 'download_progress',
      gid: '123',
      phase: 'pages',
      page: 2,
      total: 4,
    }));

    expect(result.current).toEqual([
      {
        gid: '123',
        title: 'Fixture Download',
        status: 'downloading',
        phase: 'pages',
        progress: 50,
        error: undefined,
      },
    ]);

    act(() => socket.emit({ event: 'download_complete', gid: '123' }));
    expect(result.current[0]).toMatchObject({
      gid: '123',
      status: 'completed',
      progress: 100,
    });

    unmount();
    expect(socket.close).toHaveBeenCalledOnce();
  });
});
