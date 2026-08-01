import { useState } from 'react';
import type { GalleryListItem } from '../models';
import { useFavorites } from '../hooks/useWorkspaceData';
import { GalleryCard } from './GalleryCard';
import { WorkspaceLayout, WorkspaceState } from './WorkspaceLayout';

type FavoritesPageProps = {
  onSelect: (gallery: GalleryListItem) => void;
};

export function FavoritesPage({ onSelect }: FavoritesPageProps) {
  const [slot, setSlot] = useState(-1);
  const { data, error, isLoading, mutate } = useFavorites(slot);
  const categories = data
    ? [
      { slot: -1, name: 'All', count: data.galleries.length },
      ...data.categories.filter((category) => category.slot !== -1),
    ]
    : [];

  return (
    <WorkspaceLayout
      title="Favorites"
      count={data?.galleries.length}
      onRefresh={() => void mutate()}
    >
      {categories.length > 0 && (
        <div className="workspace-segmented" role="group" aria-label="Favorite categories">
          {categories.map((category) => (
            <button
              key={category.slot}
              type="button"
              className={slot === category.slot ? 'segment active' : 'segment'}
              aria-pressed={slot === category.slot}
              onClick={() => setSlot(category.slot)}
            >
              {category.name} <span>{category.count}</span>
            </button>
          ))}
        </div>
      )}
      <WorkspaceState
        isLoading={isLoading}
        error={error}
        isEmpty={Boolean(data && data.galleries.length === 0)}
        emptyLabel="No favorites yet."
        errorLabel="Couldn't load favorites."
        onRetry={() => void mutate()}
      >
        <div className="gallery-grid" data-layout="grid" data-density="cozy">
          {data?.galleries.map((gallery) => (
            <GalleryCard key={gallery.gid} gallery={gallery} onClick={() => onSelect(gallery)} />
          ))}
        </div>
      </WorkspaceState>
    </WorkspaceLayout>
  );
}
