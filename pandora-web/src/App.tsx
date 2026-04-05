import './styles/variables.css';
import { useGalleries } from './hooks/useGalleries';
import type { GalleryListItem } from './models';

function App() {
  const { galleries, loadMore, isLoading } = useGalleries();

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
            <div key={g.gid} style={{ background: 'var(--bg-card)', padding: '10px', borderRadius: 'var(--border-radius)' }}>
              <img src={`http://127.0.0.1:7860/proxy/image?url=${encodeURIComponent(g.thumb_url)}`} alt={g.title} style={{ width: '100%', borderRadius: '4px' }} />
              <div style={{ fontSize: '0.9rem', marginTop: '8px' }}>{g.title}</div>
            </div>
          ))}
          {isLoading && <div>Loading...</div>}
        </div>
        <button onClick={loadMore} style={{ marginTop: '20px' }}>Load More</button>
      </main>
    </div>
  );
}

export default App;
