import { useState } from 'react';
import './styles/variables.css';
import { useGalleries } from './hooks/useGalleries';
import type { GalleryListItem } from './models';
import { GalleryCard } from './components/GalleryCard';
import { GalleryDrawer } from './components/GalleryDrawer';

function App() {
  const { galleries, loadMore, isLoading } = useGalleries();
  const [selectedGallery, setSelectedGallery] = useState<{gid: string, token: string} | null>(null);

  return (
    <div style={{ display: 'flex', height: '100vh' }}>
      <aside style={{ width: 'var(--sidebar-width)', backgroundColor: 'var(--bg-sidebar)', borderRight: '1px solid #333' }}>
        <nav>
          <div style={{ padding: '20px', fontWeight: 'bold', fontSize: '1.2rem' }}>Pandora</div>
          {/* Nav links will go here */}
        </nav>
      </aside>
      <main style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
        <h1>Gallery Feed</h1>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '20px' }}>
          {galleries.map((g: GalleryListItem) => (
            <GalleryCard 
              key={g.gid} 
              gallery={g} 
              onClick={() => setSelectedGallery({gid: g.gid, token: g.token})} 
            />
          ))}
          {isLoading && <div>Loading...</div>}
        </div>
        <button onClick={loadMore} style={{ marginTop: '20px' }}>Load More</button>
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
