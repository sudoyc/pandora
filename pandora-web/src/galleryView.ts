import type { SearchCriteria } from './search';

export type GalleryNavigationKind = 'homepage' | 'popular' | 'watched';
export type WorkspaceNavigationKind = 'favorites' | 'history' | 'downloads' | 'library';
export type AppNavigationKind = GalleryNavigationKind | WorkspaceNavigationKind;

export type GalleryView =
  | { kind: GalleryNavigationKind }
  | { kind: 'search'; criteria: SearchCriteria };

export type AppView = GalleryView | { kind: WorkspaceNavigationKind };

export const DEFAULT_GALLERY_VIEW: GalleryView = { kind: 'homepage' };

export function isGalleryView(view: AppView): view is GalleryView {
  return view.kind === 'homepage'
    || view.kind === 'popular'
    || view.kind === 'watched'
    || view.kind === 'search';
}

export function galleryViewTitle(view: GalleryView): string {
  if (view.kind === 'search') {
    return view.criteria.query ? `Search: ${view.criteria.query}` : 'Search Results';
  }
  if (view.kind === 'homepage') return 'Browse Index';
  return view.kind[0].toUpperCase() + view.kind.slice(1);
}
