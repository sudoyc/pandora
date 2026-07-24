import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { useGalleries } from './hooks/useGalleries';
import { useWebSocket } from './hooks/useWebSocket';
import type { GalleryListItem } from './models';

vi.mock('./hooks/useGalleries', () => ({ useGalleries: vi.fn() }));
vi.mock('./hooks/useWebSocket', () => ({ useWebSocket: vi.fn() }));
vi.mock('./components/GalleryDrawer', () => ({
  GalleryDrawer: ({ open, gid }: { open: boolean; gid: string }) =>
    open ? <div>Fixture drawer {gid}</div> : null,
}));

const gallery: GalleryListItem = {
  gid: '123',
  token: 'abcdef0123',
  title: 'Fixture Feed Gallery',
  category: 'Manga',
  uploader: 'fixture-user',
  thumb_url: 'https://example.test/thumb.jpg',
  posted: '2026-01-01',
  rating: 4.5,
  pages: 2,
  rated: false,
  thumb_width: 250,
  thumb_height: 350,
};

describe('App gallery feed', () => {
  const loadMore = vi.fn();

  beforeEach(() => {
    localStorage.clear();
    vi.mocked(useGalleries).mockReturnValue({
      galleries: [gallery],
      loadMore,
      hasMore: true,
      isLoading: false,
      error: undefined,
      mutate: vi.fn(),
    } as ReturnType<typeof useGalleries>);
    vi.mocked(useWebSocket).mockReturnValue([]);
  });

  it('renders the feed, opens a gallery, and loads another page', async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(screen.getByRole('heading', { name: 'Gallery Feed' })).toBeVisible();
    await user.click(screen.getByRole('button', { name: /Fixture Feed Gallery/ }));
    expect(screen.getByText('Fixture drawer 123')).toBeVisible();

    await user.click(screen.getByRole('button', { name: 'Load More' }));
    expect(loadMore).toHaveBeenCalledOnce();
  });

  it('normalizes a search and persists recent history', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByPlaceholderText('Search galleries...'), '  fixture query  ');
    await user.click(screen.getByRole('button', { name: 'Search' }));

    expect(screen.getByRole('heading', { name: 'Search: fixture query' })).toBeVisible();
    expect(vi.mocked(useGalleries)).toHaveBeenLastCalledWith({
      kind: 'search',
      query: 'fixture query',
    });
    expect(JSON.parse(localStorage.getItem('searchHistory') ?? '[]')).toEqual([
      'fixture query',
    ]);
  });

  it('switches the feed with a typed navigation view', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', { name: 'Popular' }));

    expect(screen.getByRole('heading', { name: 'popular' })).toBeVisible();
    expect(vi.mocked(useGalleries)).toHaveBeenLastCalledWith({ kind: 'popular' });
  });
});
