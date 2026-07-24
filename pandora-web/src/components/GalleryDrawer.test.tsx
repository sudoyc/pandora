import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import useSWR from 'swr';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { GalleryDetail } from '../models';
import { GalleryDrawer } from './GalleryDrawer';

vi.mock('swr', () => ({ default: vi.fn() }));

const detail: GalleryDetail = {
  gid: '123',
  title: 'Fixture Gallery Detail',
  title_jpn: null,
  category: 'Manga',
  uploader: 'fixture-user',
  cover_url: 'https://example.test/cover.jpg',
  tags: { artist: ['fixture-tag'] },
  pages: 2,
  size: '1 MB',
  posted: '2026-01-01',
  favorite_slot: null,
  preview_pages: 1,
  rating: 4,
  rating_count: 3,
  favorite_count: 1,
  torrent_count: 0,
  comments: [],
  comments_has_more: false,
  url: 'https://example.test/g/123/abcdef0123/',
};

describe('GalleryDrawer', () => {
  beforeEach(() => {
    vi.mocked(useSWR).mockReturnValue({
      data: detail,
      error: undefined,
      isLoading: false,
    } as ReturnType<typeof useSWR>);
  });

  it('shows detail tabs and opens the reader', async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    render(
      <GalleryDrawer
        open
        onOpenChange={onOpenChange}
        gid="123"
        token="abcdef0123"
      />,
    );

    expect(screen.getByRole('heading', { name: 'Fixture Gallery Detail' })).toBeVisible();
    await user.click(screen.getByRole('tab', { name: 'Tags' }));
    expect(screen.getByText('fixture-tag')).toBeVisible();

    await user.click(screen.getByRole('tab', { name: 'Info' }));
    await user.click(screen.getByRole('button', { name: 'Read' }));
    expect(screen.getByText('2 pages')).toBeVisible();
    expect(screen.getAllByRole('img', { name: /Page/ })).toHaveLength(2);

    await user.click(screen.getByRole('button', { name: 'Exit reader' }));
    expect(screen.queryByText('2 pages')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Close gallery details' }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it.each([
    ['loading', { data: undefined, error: undefined, isLoading: true }],
    ['error', { data: undefined, error: new Error('fixture failure'), isLoading: false }],
  ])('keeps the drawer close control available while %s', async (_state, response) => {
    vi.mocked(useSWR).mockReturnValue(response as ReturnType<typeof useSWR>);
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    render(
      <GalleryDrawer
        open
        onOpenChange={onOpenChange}
        gid="123"
        token="abcdef0123"
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Close gallery details' }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
