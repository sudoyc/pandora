import './styles/variables.css';

function App() {
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
          {/* Gallery cards will go here */}
        </div>
      </main>
    </div>
  );
}

export default App;
