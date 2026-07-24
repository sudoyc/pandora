import { useState } from 'react';
import './styles/variables.css';
import { AppSidebar } from './components/AppSidebar';
import { GalleryFeed } from './components/GalleryFeed';
import { GalleryHeader } from './components/GalleryHeader';
import { GalleryDrawer } from './components/GalleryDrawer';
import { WorkspaceView } from './components/WorkspaceView';
import { isGalleryView } from './galleryView';
import { useGalleryView } from './hooks/useGalleryView';
import { useWebSocket } from './hooks/useWebSocket';

function App() {
  const [selectedGallery, setSelectedGallery] = useState<{ gid: string; token: string } | null>(null);
  const { view, searchHistory, navigate, search } = useGalleryView();
  const downloadMessages = useWebSocket();
  const galleryView = isGalleryView(view);

  const handleNavigate = (kind: Parameters<typeof navigate>[0]) => {
    setSelectedGallery(null);
    navigate(kind);
  };

  return (
    <div className="app-shell">
      <AppSidebar
        activeView={view.kind}
        downloads={downloadMessages}
        onNavigate={handleNavigate}
      />

      <main className="main-panel">
        {galleryView ? (
          <>
            <GalleryHeader view={view} searchHistory={searchHistory} onSearch={search} />
            <GalleryFeed
              view={view}
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
