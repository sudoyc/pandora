export const DAEMON_URL = import.meta.env.VITE_PANDORA_DAEMON_URL ?? 'http://127.0.0.1:7860';
export const API_BASE_URL = `${DAEMON_URL}/api`;

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    const body = await response.text();
    let message = body || `HTTP ${response.status}`;
    let code: string | undefined;

    try {
      const payload = JSON.parse(body) as Record<string, unknown>;
      if (typeof payload.detail === 'string') message = payload.detail;
      if (typeof payload.error === 'string') code = payload.error;
    } catch {
      // Keep the response text fallback for non-JSON errors.
    }

    throw new ApiError(response.status, message, code);
  }
  return response.json() as Promise<T>;
}

export const fetcher = apiGet;

export function imageProxyUrl(url: string): string {
  return `${API_BASE_URL}/image/proxy?url=${encodeURIComponent(url)}`;
}

export function galleryPageUrl(gid: string, token: string, page: number): string {
  return `${API_BASE_URL}/gallery/${gid}/${token}/page/${page}`;
}

export function libraryFileUrl(gid: string | number, path: 'cover' | `thumb/${number}` | `page/${number}`): string {
  const encodedPath = path.split('/').map(encodeURIComponent).join('/');
  return `${API_BASE_URL}/library/${encodeURIComponent(String(gid))}/file?path=${encodedPath}`;
}
