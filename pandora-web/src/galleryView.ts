export type GalleryNavigationKind = 'homepage' | 'popular' | 'watched';
export type WorkspaceNavigationKind = 'favorites' | 'history' | 'downloads' | 'library';
export type AppNavigationKind = GalleryNavigationKind | WorkspaceNavigationKind;

export type GalleryView =
  | { kind: GalleryNavigationKind }
  | { kind: 'search'; query: string };

export type AppView = GalleryView | { kind: WorkspaceNavigationKind };

export const DEFAULT_GALLERY_VIEW: GalleryView = { kind: 'homepage' };

export function isGalleryView(view: AppView): view is GalleryView {
  return view.kind === 'homepage'
    || view.kind === 'popular'
    || view.kind === 'watched'
    || view.kind === 'search';
}

export function galleryViewTitle(view: GalleryView): string {
  if (view.kind === 'search') return `Search: ${view.query}`;
  if (view.kind === 'homepage') return 'Gallery Feed';
  return view.kind;
}
