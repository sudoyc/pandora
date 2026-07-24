import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { GalleryListItem } from '../models';
import {
  useDownloads,
  useFavorites,
  useHistory,
  useLibrary,
} from '../hooks/useWorkspaceData';
import { WorkspaceView } from './WorkspaceView';

vi.mock('../hooks/useWorkspaceData', () => ({
  useDownloads: vi.fn(),
  useFavorites: vi.fn(),
  useHistory: vi.fn(),
  useLibrary: vi.fn(),
}));

const gallery: GalleryListItem = {
  gid: '123',
  token: 'abcdef0123',
  title: 'Fixture Favorite',
  category: 'Manga',
  uploader: 'fixture-user',
  thumb_url: '',
  posted: '2026-01-01',
  rating: 4,
  pages: 2,
  rated: false,
  thumb_width: 250,
  thumb_height: 350,
};

const mutate = vi.fn();

describe('WorkspaceView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useFavorites).mockReturnValue({
      data: { categories: [{ slot: 1, name: 'Archive', count: 1 }], galleries: [gallery] },
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate,
    } as ReturnType<typeof useFavorites>);
    vi.mocked(useHistory).mockReturnValue({
      data: [{
        gid: '456',
        title: 'Fixture History',
        title_jpn: null,
        category: 'Manga',
        uploader: 'fixture-user',
        thumb_url: '',
        posted: '2026-01-01',
        rating: 4,
        pages: 5,
        read_page: 2,
        time: 1767225600,
      }],
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate,
    } as ReturnType<typeof useHistory>);
    vi.mocked(useDownloads).mockReturnValue({
      data: [{
        gid: '789',
        title: 'Fixture Download',
        total_pages: 4,
        status: 'downloading',
        downloaded_pages: 1,
        error: '',
        created_at: '2026-01-01T00:00:00Z',
      }],
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate,
    } as ReturnType<typeof useDownloads>);
    vi.mocked(useLibrary).mockReturnValue({
      data: [{ gid: '321', title: 'Fixture Library', thumb_url: '/api/library/321/file?path=cover', pages: 2 }],
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate,
    } as ReturnType<typeof useLibrary>);
  });

  it('renders favorites and opens a selected gallery', async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<WorkspaceView kind="favorites" liveDownloads={[]} onSelectGallery={onSelect} />);

    expect(screen.getByRole('heading', { name: 'Favorites' })).toBeVisible();
    await user.click(screen.getByRole('button', { name: /Fixture Favorite/ }));
    expect(onSelect).toHaveBeenCalledWith(gallery);

    await user.click(screen.getByRole('button', { name: /Archive/ }));
    expect(vi.mocked(useFavorites)).toHaveBeenLastCalledWith(1);
  });

  it('exposes retry for a failed history request', async () => {
    const user = userEvent.setup();
    vi.mocked(useHistory).mockReturnValue({
      data: undefined,
      error: new Error('fixture failure'),
      isLoading: false,
      isValidating: false,
      mutate,
    } as ReturnType<typeof useHistory>);
    render(<WorkspaceView kind="history" liveDownloads={[]} onSelectGallery={vi.fn()} />);

    expect(screen.getByRole('alert')).toHaveTextContent("Couldn't load history.");
    await user.click(screen.getByRole('button', { name: /Retry/ }));
    expect(mutate).toHaveBeenCalledOnce();
  });

  it('renders download snapshots with live progress', () => {
    render(<WorkspaceView
      kind="downloads"
      liveDownloads={[{ gid: '789', title: 'Fixture Download', status: 'downloading', progress: 50, phase: 'pages' }]}
      onSelectGallery={vi.fn()}
    />);
    expect(screen.getByText('downloading · pages')).toBeVisible();
    expect(screen.getByLabelText('50% complete')).toBeVisible();
  });

  it('opens local library pages in the reader', async () => {
    const user = userEvent.setup();
    render(<WorkspaceView kind="library" liveDownloads={[]} onSelectGallery={vi.fn()} />);
    await user.click(screen.getByRole('button', { name: /Read Fixture Library/ }));
    expect(screen.getByRole('img', { name: 'Page 1' })).toHaveAttribute(
      'src',
      'http://127.0.0.1:7860/api/library/321/file?path=page/1',
    );
  });

  it.each([
    ['favorites', 'No favorites yet.'],
    ['history', 'No browsing history yet.'],
    ['downloads', 'No downloads yet.'],
    ['library', 'No downloaded galleries yet.'],
  ] as const)('distinguishes an empty %s response', (kind, emptyLabel) => {
    if (kind === 'favorites') {
      vi.mocked(useFavorites).mockReturnValue({
        data: { categories: [], galleries: [] }, error: undefined, isLoading: false, isValidating: false, mutate,
      } as ReturnType<typeof useFavorites>);
    } else if (kind === 'history') {
      vi.mocked(useHistory).mockReturnValue({
        data: [], error: undefined, isLoading: false, isValidating: false, mutate,
      } as ReturnType<typeof useHistory>);
    } else if (kind === 'downloads') {
      vi.mocked(useDownloads).mockReturnValue({
        data: [], error: undefined, isLoading: false, isValidating: false, mutate,
      } as ReturnType<typeof useDownloads>);
    } else {
      vi.mocked(useLibrary).mockReturnValue({
        data: [], error: undefined, isLoading: false, isValidating: false, mutate,
      } as ReturnType<typeof useLibrary>);
    }

    render(<WorkspaceView kind={kind} liveDownloads={[]} onSelectGallery={vi.fn()} />);
    expect(screen.getByText(emptyLabel)).toBeVisible();
  });

  it('shows a loading status while a workspace request is pending', () => {
    vi.mocked(useLibrary).mockReturnValue({
      data: undefined, error: undefined, isLoading: true, isValidating: true, mutate,
    } as ReturnType<typeof useLibrary>);
    render(<WorkspaceView kind="library" liveDownloads={[]} onSelectGallery={vi.fn()} />);
    expect(screen.getByRole('status')).toHaveTextContent('Loading...');
  });
});
