import type { GalleryNavigationKind, GalleryView } from '../galleryView';
import type { DownloadProgressItem } from '../models';
import { DownloadProgressPanel } from './DownloadProgressPanel';

type AppSidebarProps = {
  activeView: GalleryView['kind'];
  downloads: DownloadProgressItem[];
  onNavigate: (kind: GalleryNavigationKind) => void;
};

const NAV_ITEMS: { kind: GalleryNavigationKind; label: string }[] = [
  { kind: 'homepage', label: 'Browse' },
  { kind: 'popular', label: 'Popular' },
  { kind: 'watched', label: 'Watched' },
];

export function AppSidebar({ activeView, downloads, onNavigate }: AppSidebarProps) {
  return (
    <aside className="sidebar">
      <nav className="sidebar-nav">
        <div className="brand">Pandora</div>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.kind}
            type="button"
            className={activeView === item.kind ? 'nav-item active' : 'nav-item'}
            onClick={() => onNavigate(item.kind)}
          >
            {item.label}
          </button>
        ))}
      </nav>
      <DownloadProgressPanel items={downloads} />
    </aside>
  );
}
