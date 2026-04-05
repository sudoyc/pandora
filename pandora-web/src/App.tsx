import { useState, useEffect } from 'react';
import './styles/variables.css';
import { useGalleries } from './hooks/useGalleries';
import type { GalleryListItem } from './models';
import { GalleryCard } from './components/GalleryCard';
import { GalleryDrawer } from './components/GalleryDrawer';
import { useWebSocket } from './hooks/useWebSocket';

function App() {
  const { galleries, loadMore, isLoading } = useGalleries();
  const [selectedGallery, setSelectedGallery] = useState<{gid: string, token: string} | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [searchHistory, setSearchHistory] = useState<string[]>([]);
  const downloadMessages = useWebSocket();

  useEffect(() => {
    const history = JSON.parse(localStorage.getItem('searchHistory') || '[]');
    setSearchHistory(history);
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchTerm.trim()) return;
    
    const newHistory = [searchTerm, ...searchHistory.filter(s => s !== searchTerm)].slice(0, 10);
    setSearchHistory(newHistory);
    localStorage.setItem('searchHistory', JSON.stringify(newHistory));
    // Trigger actual search logic if needed, or just log for now
    console.log('Searching for:', searchTerm);
  };

  return (
    <div style={{ display: 'flex', height: '100vh' }}>
      <aside style={{ 
        width: 'var(--sidebar-width)', 
        backgroundColor: 'var(--glass-bg)', 
        backdropFilter: 'var(--glass-blur)',
        borderRight: '1px solid #333',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 10
      }}>
        <nav style={{ flex: 1 }}>
          <div style={{ padding: '20px', fontWeight: 'bold', fontSize: '1.2rem', color: 'var(--accent)' }}>Pandora</div>
          <ul style={{ listStyle: 'none', padding: '0 20px', margin: 0 }}>
            <li style={{ padding: '10px 0', cursor: 'pointer', color: 'var(--accent)' }}>Browse</li>
            <li style={{ padding: '10px 0', cursor: 'pointer' }}>Favorites</li>
            <li style={{ padding: '10px 0', cursor: 'pointer' }}>History</li>
            <li style={{ padding: '10px 0', cursor: 'pointer' }}>Downloads</li>
          </ul>
        </nav>
        
        <div style={{ padding: '20px', borderTop: '1px solid #333' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '10px' }}>Active Downloads</div>
          {downloadMessages.map(msg => (
            <div key={msg.gid} style={{ fontSize: '0.7rem', marginBottom: '5px' }}>
              <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{msg.gid}</div>
              <div style={{ height: '4px', backgroundColor: '#333', marginTop: '2px' }}>
                <div style={{ height: '100%', backgroundColor: 'var(--accent)', width: `${msg.progress}%` }} />
              </div>
            </div>
          ))}
        </div>
      </aside>
      <main style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
        <header style={{ marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1>Gallery Feed</h1>
          <form onSubmit={handleSearch} style={{ display: 'flex', gap: '10px' }}>
            <input 
              type="text" 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search galleries..."
              style={{ 
                padding: '8px 12px', 
                borderRadius: 'var(--border-radius)', 
                border: '1px solid #333',
                backgroundColor: 'var(--bg-card)',
                color: 'var(--text-primary)',
                width: '300px'
              }}
            />
            <button type="submit" style={{ 
              padding: '8px 16px', 
              borderRadius: 'var(--border-radius)', 
              border: 'none', 
              backgroundColor: 'var(--accent)', 
              color: '#000',
              fontWeight: 'bold',
              cursor: 'pointer'
            }}>Search</button>
          </form>
        </header>
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
