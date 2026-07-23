import { useState } from 'react';
import type { FormEvent } from 'react';
import './styles/variables.css';
import { useGalleries } from './hooks/useGalleries';
import type { GalleryListItem } from './models';
import { GalleryCard } from './components/GalleryCard';
import { GalleryDrawer } from './components/GalleryDrawer';
import { useWebSocket } from './hooks/useWebSocket';

type GalleryMode = 'homepage' | 'search' | 'popular' | 'watched';

function App() {
  const [mode, setMode] = useState<GalleryMode>('homepage');
  const [query, setQuery] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedGallery, setSelectedGallery] = useState<{ gid: string; token: string } | null>(null);
  const [searchHistory, setSearchHistory] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem('searchHistory') || '[]') as string[];
    } catch {
      return [];
    }
  });
  const { galleries, loadMore, hasMore, isLoading, error } = useGalleries(mode, query);
  const downloadMessages = useWebSocket();

  const handleSearch = (event: FormEvent) => {
    event.preventDefault();
    const nextQuery = searchTerm.trim();
    if (!nextQuery) return;

    const newHistory = [nextQuery, ...searchHistory.filter((item) => item !== nextQuery)].slice(0, 10);
    setSearchHistory(newHistory);
    localStorage.setItem('searchHistory', JSON.stringify(newHistory));
    setQuery(nextQuery);
    setMode('search');
  };

  const switchMode = (nextMode: GalleryMode) => {
    setMode(nextMode);
    if (nextMode !== 'search') setQuery('');
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <nav className="sidebar-nav">
          <div className="brand">Pandora</div>
          <button type="button" className={mode === 'homepage' ? 'nav-item active' : 'nav-item'} onClick={() => switchMode('homepage')}>Browse</button>
          <button type="button" className={mode === 'popular' ? 'nav-item active' : 'nav-item'} onClick={() => switchMode('popular')}>Popular</button>
          <button type="button" className={mode === 'watched' ? 'nav-item active' : 'nav-item'} onClick={() => switchMode('watched')}>Watched</button>
        </nav>

        <div className="downloads-panel">
          <div className="panel-title">Recent Downloads</div>
          {downloadMessages.length === 0 && <div className="muted">No events yet</div>}
          {downloadMessages.map((msg) => (
            <div key={msg.gid} className="download-row">
              <div className="download-title">{msg.title ?? msg.gid}</div>
              <div className="download-status">{msg.status}{msg.phase ? ` · ${msg.phase}` : ''}</div>
              <div className="progress-track">
                <div className="progress-bar" style={{ width: `${msg.progress}%` }} />
              </div>
            </div>
          ))}
        </div>
      </aside>

      <main className="main-panel">
        <header className="main-header">
          <div>
            <h1>{mode === 'search' ? `Search: ${query}` : mode === 'homepage' ? 'Gallery Feed' : mode}</h1>
            {searchHistory.length > 0 && <div className="muted">Recent: {searchHistory.slice(0, 3).join(' · ')}</div>}
          </div>
          <form onSubmit={handleSearch} className="search-form">
            <input
              type="text"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Search galleries..."
            />
            <button type="submit">Search</button>
          </form>
        </header>

        {error && <div className="error-text">Failed to load galleries: {String(error)}</div>}
        <div className="gallery-grid">
          {galleries.map((gallery: GalleryListItem) => (
            <GalleryCard
              key={gallery.gid}
              gallery={gallery}
              onClick={() => setSelectedGallery({ gid: gallery.gid, token: gallery.token })}
            />
          ))}
          {isLoading && <div className="muted">Loading...</div>}
        </div>
        {hasMore && (
          <button type="button" className="load-more" onClick={loadMore} disabled={isLoading}>Load More</button>
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
