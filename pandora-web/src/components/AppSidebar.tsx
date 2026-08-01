import { Clock3, Compass, Download, Eye, Flame, Heart, Library, Menu, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import type { AppNavigationKind, AppView } from '../galleryView';
import type { DownloadProgressItem } from '../models';
import type { ThemeName } from '../theme';
import { DownloadProgressPanel } from './DownloadProgressPanel';
import { ThemeSwitcher } from './ThemeSwitcher';

type AppSidebarProps = {
  activeView: AppView['kind'];
  downloads: DownloadProgressItem[];
  theme: ThemeName;
  onNavigate: (kind: AppNavigationKind) => void;
  onThemeChange: (theme: ThemeName) => void;
};

const NAV_ITEMS: {
  kind: AppNavigationKind;
  label: string;
  icon: LucideIcon;
  mobile: 'primary' | 'secondary';
}[] = [
  { kind: 'homepage', label: 'Browse', icon: Compass, mobile: 'primary' },
  { kind: 'popular', label: 'Popular', icon: Flame, mobile: 'secondary' },
  { kind: 'watched', label: 'Watched', icon: Eye, mobile: 'secondary' },
  { kind: 'favorites', label: 'Favorites', icon: Heart, mobile: 'primary' },
  { kind: 'history', label: 'History', icon: Clock3, mobile: 'secondary' },
  { kind: 'downloads', label: 'Downloads', icon: Download, mobile: 'primary' },
  { kind: 'library', label: 'Library', icon: Library, mobile: 'primary' },
];

export function AppSidebar({
  activeView,
  downloads,
  theme,
  onNavigate,
  onThemeChange,
}: AppSidebarProps) {
  const [moreOpen, setMoreOpen] = useState(false);
  const secondaryActive = NAV_ITEMS.some(
    (item) => item.mobile === 'secondary' && item.kind === activeView,
  );

  useEffect(() => {
    if (!moreOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMoreOpen(false);
    };
    document.addEventListener('keydown', closeOnEscape);
    return () => document.removeEventListener('keydown', closeOnEscape);
  }, [moreOpen]);

  const handleNavigate = (kind: AppNavigationKind) => {
    setMoreOpen(false);
    onNavigate(kind);
  };

  return (
    <aside className="sidebar" aria-label="Primary navigation">
      <div className="brand" aria-label="Pandora"><span>PAN</span><span>DORA</span></div>
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.kind}
            type="button"
            className={`nav-item nav-item--${item.mobile}${activeView === item.kind ? ' active' : ''}`}
            onClick={() => handleNavigate(item.kind)}
            aria-current={activeView === item.kind ? 'page' : undefined}
          >
            <item.icon size={19} aria-hidden="true" />
            <span>{item.label}</span>
          </button>
        ))}
        <button
          type="button"
          className={`nav-item mobile-more${moreOpen || secondaryActive ? ' active' : ''}`}
          aria-expanded={moreOpen}
          aria-controls="mobile-more-panel"
          onClick={() => setMoreOpen((current) => !current)}
        >
          <Menu size={19} aria-hidden="true" />
          <span>More</span>
        </button>
      </nav>

      <div className="sidebar-footer">
        <ThemeSwitcher theme={theme} onThemeChange={onThemeChange} />
        <DownloadProgressPanel items={downloads} />
      </div>

      {moreOpen && (
        <>
          <button
            type="button"
            className="mobile-more-scrim"
            aria-label="Close more menu"
            onClick={() => setMoreOpen(false)}
          />
          <section className="mobile-more-panel" id="mobile-more-panel" aria-label="More navigation">
            <header>
              <strong>More</strong>
              <button type="button" aria-label="Close more menu" onClick={() => setMoreOpen(false)}>
                <X size={20} aria-hidden="true" />
              </button>
            </header>
            <nav>
              {NAV_ITEMS.filter((item) => item.mobile === 'secondary').map((item) => (
                <button
                  key={item.kind}
                  type="button"
                  className={activeView === item.kind ? 'mobile-more-link active' : 'mobile-more-link'}
                  onClick={() => handleNavigate(item.kind)}
                >
                  <item.icon size={18} aria-hidden="true" />
                  <span>{item.label}</span>
                </button>
              ))}
            </nav>
            <ThemeSwitcher theme={theme} onThemeChange={onThemeChange} expanded />
          </section>
        </>
      )}
    </aside>
  );
}
