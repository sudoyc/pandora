import { Clock3, Compass, Download, Eye, Flame, Heart, Library } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { AppNavigationKind, AppView } from '../galleryView';
import type { DownloadProgressItem } from '../models';
import { DownloadProgressPanel } from './DownloadProgressPanel';

type AppSidebarProps = {
  activeView: AppView['kind'];
  downloads: DownloadProgressItem[];
  onNavigate: (kind: AppNavigationKind) => void;
};

const NAV_ITEMS: { kind: AppNavigationKind; label: string; icon: LucideIcon }[] = [
  { kind: 'homepage', label: 'Browse', icon: Compass },
  { kind: 'popular', label: 'Popular', icon: Flame },
  { kind: 'watched', label: 'Watched', icon: Eye },
  { kind: 'favorites', label: 'Favorites', icon: Heart },
  { kind: 'history', label: 'History', icon: Clock3 },
  { kind: 'downloads', label: 'Downloads', icon: Download },
  { kind: 'library', label: 'Library', icon: Library },
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
            aria-current={activeView === item.kind ? 'page' : undefined}
          >
            <item.icon size={17} aria-hidden="true" />
            {item.label}
          </button>
        ))}
      </nav>
      <DownloadProgressPanel items={downloads} />
    </aside>
  );
}
