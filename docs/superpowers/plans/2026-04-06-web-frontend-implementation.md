# Pandora Web Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a modern, feature-rich React web frontend for Pandora that interacts with the local daemon.

**Architecture:** A React SPA using Vite for building, Radix UI for accessible UI primitives, and CSS Modules for styling. Communication with the backend is via REST and WebSockets.

**Tech Stack:** React 18, TypeScript, Vite, Radix UI, Lucide React (icons), SWR (data fetching).

---

### Task 1: Project Scaffolding & Initial Setup

**Files:**
- Create: `pandora-web/package.json`
- Create: `pandora-web/tsconfig.json`
- Create: `pandora-web/vite.config.ts`
- Create: `pandora-web/src/main.tsx`
- Create: `pandora-web/src/App.tsx`
- Create: `pandora-web/src/styles/variables.css`

- [ ] **Step 1: Initialize Vite React project with TypeScript**

Run: `npm create vite@latest pandora-web -- --template react-ts`
Expected: Folder `pandora-web` created with boilerplate.

- [ ] **Step 2: Install core dependencies**

Run: `cd pandora-web && npm install @radix-ui/react-dialog @radix-ui/react-tabs @radix-ui/react-tooltip lucide-react swr clsx tailwind-merge`
Expected: Dependencies installed.

- [ ] **Step 3: Define global CSS variables for "Modern Soft" theme**

```css
/* pandora-web/src/styles/variables.css */
:root {
  --bg-app: #121212;
  --bg-card: #1e1e1e;
  --bg-sidebar: #181818;
  --bg-hover: #2a2a2a;
  --text-primary: #e0e0e0;
  --text-secondary: #aaaaaa;
  --accent: #00ffff;
  --border-radius: 8px;
  --sidebar-width: 240px;
  --drawer-width: 400px;
}

body {
  background-color: var(--bg-app);
  color: var(--text-primary);
  margin: 0;
  font-family: system-ui, -apple-system, sans-serif;
}
```

- [ ] **Step 4: Set up basic App shell with Sidebar and Main area**

```tsx
// pandora-web/src/App.tsx
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
```

- [ ] **Step 5: Commit initial scaffold**

```bash
git add pandora-web/
git commit -m "feat(web): initial react scaffold with styles and layout"
```

---

### Task 2: API Client & Data Fetching (Home/Search)

**Files:**
- Create: `pandora-web/src/api/client.ts`
- Create: `pandora-web/src/hooks/useGalleries.ts`
- Modify: `pandora-web/src/App.tsx`

- [ ] **Step 1: Create API client with base URL pointing to daemon**

```typescript
// pandora-web/src/api/client.ts
const BASE_URL = 'http://127.0.0.1:7860/api';

export const fetcher = (url: string) => fetch(`${BASE_URL}${url}`).then(res => res.json());
```

- [ ] **Step 2: Create hook for fetching galleries with infinite scroll support**

```typescript
// pandora-web/src/hooks/useGalleries.ts
import useSWRInfinite from 'swr/infinite';
import { fetcher } from '../api/client';

export const useGalleries = (mode: string = 'homepage', params: string = '') => {
  const getKey = (pageIndex: number, previousPageData: any) => {
    if (previousPageData && !previousPageData.length) return null;
    return `/${mode}?page=${pageIndex}${params}`;
  };

  const { data, size, setSize, error, isLoading } = useSWRInfinite(getKey, fetcher);
  
  const galleries = data ? data.flat() : [];
  const loadMore = () => setSize(size + 1);

  return { galleries, loadMore, isLoading, error };
};
```

- [ ] **Step 3: Update App.tsx to display gallery titles from API**

```tsx
// pandora-web/src/App.tsx (partial update)
import { useGalleries } from './hooks/useGalleries';

// inside App component:
const { galleries, loadMore, isLoading } = useGalleries();

// in the grid div:
{galleries.map((g: any) => (
  <div key={g.gid} style={{ background: 'var(--bg-card)', padding: '10px', borderRadius: 'var(--border-radius)' }}>
    <img src={`http://127.0.0.1:7860/proxy/image?url=${encodeURIComponent(g.thumb_url)}`} alt={g.title} style={{ width: '100%', borderRadius: '4px' }} />
    <div style={{ fontSize: '0.9rem', marginTop: '8px' }}>{g.title}</div>
  </div>
))}
{isLoading && <div>Loading...</div>}
<button onClick={loadMore}>Load More</button>
```

- [ ] **Step 4: Commit API integration**

```bash
git add pandora-web/src/api/ pandora-web/src/hooks/ pandora-web/src/App.tsx
git commit -m "feat(web): api integration for gallery list and image proxying"
```

---

### Task 3: Gallery Card & Detail Drawer (Radix UI Dialog)

**Files:**
- Create: `pandora-web/src/components/GalleryCard.tsx`
- Create: `pandora-web/src/components/GalleryDrawer.tsx`
- Modify: `pandora-web/src/App.tsx`

- [ ] **Step 1: Implement GalleryCard component**

```tsx
// pandora-web/src/components/GalleryCard.tsx
export const GalleryCard = ({ gallery, onClick }: { gallery: any, onClick: () => void }) => (
  <div onClick={onClick} style={{ cursor: 'pointer', background: 'var(--bg-card)', padding: '10px', borderRadius: 'var(--border-radius)' }}>
    <img src={`http://127.0.0.1:7860/proxy/image?url=${encodeURIComponent(gallery.thumb_url)}`} alt={gallery.title} style={{ width: '100%', aspectRatio: '2/3', objectFit: 'cover' }} />
    <div style={{ fontSize: '0.8rem', fontWeight: 'bold' }}>{gallery.title}</div>
    <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{gallery.uploader}</div>
  </div>
);
```

- [ ] **Step 2: Implement GalleryDrawer using Radix Dialog**

```tsx
// pandora-web/src/components/GalleryDrawer.tsx
import * as Dialog from '@radix-ui/react-dialog';
import * as Tabs from '@radix-ui/react-tabs';

export const GalleryDrawer = ({ open, onOpenChange, gid, token }: any) => {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)' }} />
        <Dialog.Content style={{ position: 'fixed', right: 0, top: 0, bottom: 0, width: 'var(--drawer-width)', background: 'var(--bg-sidebar)', padding: '20px' }}>
          <Tabs.Root defaultValue="info">
            <Tabs.List style={{ display: 'flex', gap: '20px', borderBottom: '1px solid #444' }}>
              <Tabs.Trigger value="info">Info</Tabs.Trigger>
              <Tabs.Trigger value="previews">Previews</Tabs.Trigger>
              <Tabs.Trigger value="comments">Comments</Tabs.Trigger>
            </Tabs.List>
            <Tabs.Content value="info">
               {/* Fetch and show detail here */}
               <Dialog.Close>Close</Dialog.Close>
            </Tabs.Content>
          </Tabs.Root>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
};
```

- [ ] **Step 3: Integrate Drawer into App.tsx**

```tsx
// pandora-web/src/App.tsx update
const [selectedGallery, setSelectedGallery] = useState<{gid: string, token: string} | null>(null);

// in grid:
<GalleryCard gallery={g} onClick={() => setSelectedGallery({gid: g.gid, token: g.token})} />

{selectedGallery && (
  <GalleryDrawer 
    open={!!selectedGallery} 
    onOpenChange={(open: boolean) => !open && setSelectedGallery(null)}
    gid={selectedGallery.gid}
    token={selectedGallery.token}
  />
)}
```

- [ ] **Step 4: Commit Drawer implementation**

```bash
git add pandora-web/src/components/
git commit -m "feat(web): gallery card and side drawer with tabs"
```

---

### Task 4: Fullscreen Reader Mode

**Files:**
- Create: `pandora-web/src/components/Reader.tsx`
- Modify: `pandora-web/src/components/GalleryDrawer.tsx`

- [ ] **Step 1: Implement Reader component with Paged/Scroll modes**

```tsx
// pandora-web/src/components/Reader.tsx
import { useState } from 'react';

export const Reader = ({ images, onClose }: { images: string[], onClose: () => void }) => {
  const [viewMode, setViewMode] = useState<'paged' | 'scroll'>('paged');
  const [currentPage, setCurrentPage] = useState(0);

  return (
    <div style={{ position: 'fixed', inset: 0, background: '#000', zIndex: 1000, overflowY: viewMode === 'scroll' ? 'auto' : 'hidden' }}>
      <div style={{ position: 'fixed', top: '10px', right: '10px', zIndex: 1001 }}>
        <button onClick={() => setViewMode(viewMode === 'paged' ? 'scroll' : 'paged')}>Toggle Mode</button>
        <button onClick={onClose}>Exit</button>
      </div>
      {viewMode === 'paged' ? (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
           <img src={images[currentPage]} style={{ maxHeight: '100%', maxWidth: '100%' }} />
           <div style={{ position: 'absolute', bottom: '20px' }}>{currentPage + 1} / {images.length}</div>
           {/* Add click handlers for prev/next */}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          {images.map((url, i) => <img key={i} src={url} style={{ maxWidth: '100%', marginBottom: '10px' }} />)}
        </div>
      )}
    </div>
  );
};
```

- [ ] **Step 2: Connect Reader to GalleryDrawer**

Add a "Read" button in the Drawer's Info tab that opens the Reader component.

- [ ] **Step 3: Commit Reader implementation**

```bash
git add pandora-web/src/components/Reader.tsx
git commit -m "feat(web): fullscreen reader with paged and continuous scroll modes"
```

---

### Task 5: WebSocket Download Progress & Polish

**Files:**
- Create: `pandora-web/src/hooks/useWebSocket.ts`
- Modify: `pandora-web/src/App.tsx`
- Modify: `pandora-web/src/styles/variables.css`

- [ ] **Step 1: Create WebSocket hook to listen for daemon events**

```typescript
// pandora-web/src/hooks/useWebSocket.ts
import { useEffect, useState } from 'react';

export const useWebSocket = () => {
  const [messages, setMessages] = useState<any[]>([]);

  useEffect(() => {
    const ws = new WebSocket('ws://127.0.0.1:7860/ws');
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'download_progress') {
        setMessages(prev => [...prev, data]);
      }
    };
    return () => ws.close();
  }, []);

  return messages;
};
```

- [ ] **Step 2: Add Search Bar and Sidebar navigation links**

Use `localStorage` for search history. Add links for Favorites, History, etc., in the Sidebar.

- [ ] **Step 3: Final styling polish**

Apply `backdrop-filter: blur(10px)` to the Sidebar if needed for C style, or stick to B style with clean shadows.

- [ ] **Step 4: Commit final polish**

```bash
git add .
git commit -m "feat(web): websocket integration and ui polish"
```
