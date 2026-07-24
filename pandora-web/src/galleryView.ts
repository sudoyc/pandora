export type GalleryNavigationKind = 'homepage' | 'popular' | 'watched';

export type GalleryView =
  | { kind: GalleryNavigationKind }
  | { kind: 'search'; query: string };

export const DEFAULT_GALLERY_VIEW: GalleryView = { kind: 'homepage' };

export function galleryViewTitle(view: GalleryView): string {
  if (view.kind === 'search') return `Search: ${view.query}`;
  if (view.kind === 'homepage') return 'Gallery Feed';
  return view.kind;
}
