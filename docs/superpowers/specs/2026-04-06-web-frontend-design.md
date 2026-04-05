# Pandora Web Frontend Design Specification

**Date:** 2026-04-06
**Status:** Approved

## 1. Objective
Design and implement a modern, high-performance web frontend for Pandora, providing a seamless browsing, searching, and reading experience for ExHentai content. The frontend will communicate exclusively with the local `pandora-daemon` via REST APIs and WebSockets.

## 2. Technical Stack
*   **Framework:** React 18+ with TypeScript.
*   **Build Tool:** Vite (for fast HMR and optimized builds).
*   **Component Primitives:** Radix UI (Headless UI components) to handle complex interactions (Drawers, Modals, Tabs, Tooltips) with full accessibility support, while remaining completely unstyled.
*   **Styling:** Vanilla CSS using CSS Modules. This ensures component scoping without the overhead of CSS-in-JS libraries, while maintaining the flexibility to implement custom themes via CSS Variables.
*   **State Management:** React Context + Hooks for global state (e.g., Theme, Current User Info) and SWR or React Query for data fetching and caching API responses.

## 3. Architecture & Data Flow
1.  **Backend Agnostic:** The frontend knows nothing about ExHentai directly. All requests target `http://127.0.0.1:7860`.
2.  **Image Proxying:** All image `src` attributes will point to the daemon's image proxy endpoints to utilize local caching and avoid rate limits.
3.  **Real-time Updates:** A persistent WebSocket connection to the daemon will listen for download progress and state changes, updating the UI reactively.

## 4. UI/UX Layout (Modern Desktop Style)
The application will adopt a modern desktop application layout, maximizing screen real estate and minimizing full-page navigations.

### 4.1. Left Sidebar (Navigation)
*   **Fixed position.**
*   **Primary Links:** Home, Popular, Toplist, Watched, Favorites, History, Downloads.
*   **Quick Search (Saved Searches):** Displays search presets saved in the daemon's SQLite database (`/api/quick-search`). Clicking a preset immediately applies the search.
*   **Status Indicator:** Daemon connection status and active download count.

### 4.2. Main Content Area (Gallery Grid)
*   **Display:** A responsive grid of gallery cards (Cover, Title, Rating, Uploader, Tags snippet).
*   **Pagination:** Implemented via **Infinite Scroll**. As the user scrolls near the bottom, the next page is fetched and appended seamlessly.
*   **Loading State:** Uses Skeleton loaders to prevent layout shift while data is being fetched.

### 4.3. Detail Drawer (Right Slide-out)
When a gallery card is clicked, a drawer slides out from the right side, covering a portion of the main grid (the grid remains visible but slightly dimmed in the background).
*   **Organization:** Uses **Tabs** to organize dense information:
    *   **Tab 1: Info:** Large cover image, full title (EN/JP), metadata (uploader, rating, pages, size), and categorized tag lists.
    *   **Tab 2: Previews:** A grid of thumbnails for the gallery pages.
    *   **Tab 3: Comments:** User comments.
*   **Actions:** Download button, Favorite toggle, Read button.

### 4.4. Fullscreen Reader Mode
Activated by clicking "Read" or a specific thumbnail.
*   **Immersive:** Hides all navigation and sidebars.
*   **View Modes:**
    1.  **Paged Mode:** Left/Right navigation, one or two pages at a time.
    2.  **Continuous Scroll (Webtoon Mode):** Vertical scrolling through all pages.
*   **Controls:** Floating control bar (auto-hides) for page navigation, mode switching, and exiting. Supports keyboard shortcuts (Arrow keys, WASD).

## 5. Visual Identity & Styling
*   **Theme:** **Modern Soft / Minimal**.
*   **Colors:** Soft dark grays (e.g., `#1e1e1e` for background, `#2d2d2d` for cards), rounded corners (`border-radius: 8px`), and subtle drop shadows for depth.
*   **Theming Engine:** All colors, spacing, and typography will be defined as CSS Variables attached to the `:root` element. This makes switching themes (e.g., to a "Deep Dark" or "Light" theme) trivial in the future.

## 6. Specific Features
*   **Search History:** Recent searches will be stored in the browser's `localStorage` for quick access, separate from the server-side "Quick Search" presets.
*   **Thumbnail Optimization:** The frontend must support the daemon's `gdtm` CSS sprite cropping for efficient thumbnail rendering.

## 7. Implementation Phasing
1.  **Phase 1: Foundation:** Project scaffold (Vite + React), CSS variable setup, basic layout skeleton (Sidebar + Main Area).
2.  **Phase 2: Core Browsing:** API integration for Home/Search, infinite scroll implementation, Gallery Card component.
3.  **Phase 3: Details & Interactivity:** Right Drawer implementation with Radix UI, Tabbed information display.
4.  **Phase 4: Reader:** Fullscreen image viewer with toggleable scroll/page modes.
5.  **Phase 5: Polish:** WebSocket download progress integration, Favorites management, and final styling adjustments.
