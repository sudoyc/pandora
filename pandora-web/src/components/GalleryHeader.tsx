import { useState } from 'react';
import type { FormEvent } from 'react';
import { galleryViewTitle, type GalleryView } from '../galleryView';

type GalleryHeaderProps = {
  view: GalleryView;
  searchHistory: string[];
  onSearch: (query: string) => void;
};

export function GalleryHeader({ view, searchHistory, onSearch }: GalleryHeaderProps) {
  const [searchTerm, setSearchTerm] = useState('');

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    onSearch(searchTerm);
  };

  return (
    <header className="main-header">
      <div>
        <h1>{galleryViewTitle(view)}</h1>
        {searchHistory.length > 0 && (
          <div className="muted">Recent: {searchHistory.slice(0, 3).join(' · ')}</div>
        )}
      </div>
      <form onSubmit={handleSubmit} className="search-form" role="search" aria-label="Gallery search">
        <input
          type="text"
          value={searchTerm}
          onChange={(event) => setSearchTerm(event.target.value)}
          placeholder="Search galleries..."
        />
        <button type="submit">Search</button>
      </form>
    </header>
  );
}
