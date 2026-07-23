export const DAEMON_URL = import.meta.env.VITE_PANDORA_DAEMON_URL ?? 'http://127.0.0.1:7860';
export const API_BASE_URL = `${DAEMON_URL}/api`;

export async function fetcher<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function imageProxyUrl(url: string): string {
  return `${API_BASE_URL}/image/proxy?url=${encodeURIComponent(url)}`;
}

export function galleryPageUrl(gid: string, token: string, page: number): string {
  return `${API_BASE_URL}/gallery/${gid}/${token}/page/${page}`;
}
