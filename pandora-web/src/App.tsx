import { useState } from 'react';
import './styles/variables.css';
import { AppSidebar } from './components/AppSidebar';
import { GalleryFeed } from './components/GalleryFeed';
import { GalleryHeader } from './components/GalleryHeader';
import { GalleryDrawer } from './components/GalleryDrawer';
import { useGalleryView } from './hooks/useGalleryView';
import { useWebSocket } from './hooks/useWebSocket';

function App() {
  const [selectedGallery, setSelectedGallery] = useState<{ gid: string; token: string } | null>(null);
  const { view, searchHistory, navigate, search } = useGalleryView();
  const downloadMessages = useWebSocket();

  return (
    <div className="app-shell">
      <AppSidebar
        activeView={view.kind}
        downloads={downloadMessages}
        onNavigate={navigate}
      />

      <main className="main-panel">
        <GalleryHeader view={view} searchHistory={searchHistory} onSearch={search} />
        <GalleryFeed
          view={view}
          onSelect={(gallery) => setSelectedGallery({ gid: gallery.gid, token: gallery.token })}
        />
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
