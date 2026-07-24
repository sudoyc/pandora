import type { WorkspaceNavigationKind } from '../galleryView';
import type { DownloadProgressItem, GalleryListItem } from '../models';
import { DownloadsPage } from './DownloadsPage';
import { FavoritesPage } from './FavoritesPage';
import { HistoryPage } from './HistoryPage';
import { LibraryPage } from './LibraryPage';

type WorkspaceViewProps = {
  kind: WorkspaceNavigationKind;
  liveDownloads: DownloadProgressItem[];
  onSelectGallery: (gallery: GalleryListItem) => void;
};

export function WorkspaceView({ kind, liveDownloads, onSelectGallery }: WorkspaceViewProps) {
  switch (kind) {
    case 'favorites':
      return <FavoritesPage onSelect={onSelectGallery} />;
    case 'history':
      return <HistoryPage />;
    case 'downloads':
      return <DownloadsPage liveItems={liveDownloads} />;
    case 'library':
      return <LibraryPage />;
  }
}
