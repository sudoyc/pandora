import { useState } from 'react';
import './styles/variables.css';
import { AppSidebar } from './components/AppSidebar';
import { GalleryFeed } from './components/GalleryFeed';
import { GalleryHeader } from './components/GalleryHeader';
import { GalleryDrawer } from './components/GalleryDrawer';
import { WorkspaceView } from './components/WorkspaceView';
import { isGalleryView } from './galleryView';
import type { GalleryDensity, GalleryLayout } from './galleryDisplay';
import { useGalleryView } from './hooks/useGalleryView';
import { useTheme } from './hooks/useTheme';
import { useWebSocket } from './hooks/useWebSocket';
import { searchCriteriaKey } from './search';

type ViewTransitionDocument = Document & {
  startViewTransition?: (update: () => void) => void;
};

function runDisplayTransition(update: () => void) {
  const documentWithTransitions = document as ViewTransitionDocument;
  if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches
    && documentWithTransitions.startViewTransition) {
    documentWithTransitions.startViewTransition(update);
    return;
  }
  update();
}

function App() {
  const [selectedGallery, setSelectedGallery] = useState<{ gid: string; token: string } | null>(null);
  const [galleryLayout, setGalleryLayout] = useState<GalleryLayout>('grid');
  const [galleryDensity, setGalleryDensity] = useState<GalleryDensity>('cozy');
  const { view, searchHistory, navigate, search, removeSearchHistory } = useGalleryView();
  const { theme, setTheme } = useTheme();
  const downloadMessages = useWebSocket();
  const galleryView = isGalleryView(view);

  const handleNavigate = (kind: Parameters<typeof navigate>[0]) => {
    setSelectedGallery(null);
    navigate(kind);
  };

  return (
    <div className={selectedGallery ? 'app-shell has-inspector' : 'app-shell'}>
      <AppSidebar
        activeView={view.kind}
        downloads={downloadMessages}
        theme={theme}
        onNavigate={handleNavigate}
        onThemeChange={setTheme}
      />

      <main className="main-panel">
        {galleryView ? (
          <>
            <GalleryHeader
              key={view.kind === 'search' ? searchCriteriaKey(view.criteria) : view.kind}
              view={view}
              searchHistory={searchHistory}
              layout={galleryLayout}
              density={galleryDensity}
              onSearch={search}
              onClearSearch={() => handleNavigate('homepage')}
              onRemoveSearchHistory={removeSearchHistory}
              onLayoutChange={(layout) => runDisplayTransition(() => setGalleryLayout(layout))}
              onDensityChange={(density) => runDisplayTransition(() => setGalleryDensity(density))}
            />
            <GalleryFeed
              view={view}
              layout={galleryLayout}
              density={galleryDensity}
              onSelect={(gallery) => setSelectedGallery({ gid: gallery.gid, token: gallery.token })}
            />
          </>
        ) : (
          <WorkspaceView
            kind={view.kind}
            liveDownloads={downloadMessages}
            onSelectGallery={(gallery) => setSelectedGallery({ gid: gallery.gid, token: gallery.token })}
          />
        )}
      </main>

      {selectedGallery && (
        <GalleryDrawer
          open={!!selectedGallery}
          onOpenChange={(open: boolean) => !open && setSelectedGallery(null)}
          gid={selectedGallery.gid}
          token={selectedGallery.token}
        />
      )}
    </div>
  );
}

export default App;
