import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiGet, libraryFileUrl } from './client';

describe('apiGet', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('returns typed JSON from the daemon API', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ ok: true }),
      { status: 200, headers: { 'content-type': 'application/json' } },
    ));
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiGet<{ ok: boolean }>('/health')).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:7860/api/health');
  });

  it('throws a typed error for a structured daemon failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ error: 'session', detail: 'Upstream session is invalid' }),
      { status: 401, headers: { 'content-type': 'application/json' } },
    )));

    const request = apiGet('/gallery/123/token');
    await expect(request).rejects.toBeInstanceOf(ApiError);
    await expect(request).rejects.toMatchObject({
      status: 401,
      code: 'session',
      message: 'Upstream session is invalid',
    });
  });

  it('uses response text when an error is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      'Gateway unavailable',
      { status: 503 },
    )));

    await expect(apiGet('/homepage')).rejects.toMatchObject({
      status: 503,
      code: undefined,
      message: 'Gateway unavailable',
    });
  });

  it('builds a daemon URL for local library files', () => {
    expect(libraryFileUrl('123', 'page/4')).toBe(
      'http://127.0.0.1:7860/api/library/123/file?path=page/4',
    );
  });
});
