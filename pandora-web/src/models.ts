export interface GalleryListItem {
  gid: string;
  token: string;
  title: string;
  category: string;
  uploader: string;
  thumb_url: string;
  posted: string;
  rating: number;
  pages: number;
  rated: boolean;
  thumb_width: number;
  thumb_height: number;
  url?: string;
}

export interface GalleryComment {
  id: number;
  user: string;
  comment: string;
  score: number;
  time: string;
  is_uploader: boolean;
  vote_up_able: boolean;
  vote_down_able: boolean;
  vote_up_ed: boolean;
  vote_down_ed: boolean;
  editable: boolean;
  last_edited: string | null;
}

export interface GalleryDetail {
  gid: string;
  title: string;
  title_jpn?: string | null;
  category: string;
  uploader: string;
  cover_url: string;
  tags: Record<string, string[]>;
  pages: number;
  size: string;
  posted: string;
  favorite_slot: number | null;
  preview_pages: number;
  rating: number;
  rating_count: number;
  favorite_count: number;
  torrent_count: number;
  comments: GalleryComment[];
  comments_has_more: boolean;
  url: string;
}

export type DownloadEvent =
  | { event: 'download_queued'; gid: string; title?: string }
  | { event: 'download_progress'; gid: string; phase: string; page?: number; total?: number }
  | { event: 'download_complete'; gid: string }
  | { event: 'download_complete_with_errors'; gid: string; failed_pages?: number[] }
  | { event: 'download_error'; gid: string; error?: string }
  | { event: 'download_cancelled'; gid: string }
  | { event: 'download_paused'; gid: string; reason?: string }
  | { event: 'download_auth_failed'; gid: string; error?: string };

export interface DownloadProgressItem {
  gid: string;
  title?: string;
  status: string;
  phase?: string;
  progress: number;
  error?: string;
}
