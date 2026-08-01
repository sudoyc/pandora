import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { GalleryListItem } from '../models';
import { GalleryCard } from './GalleryCard';

const gallery: GalleryListItem = {
  gid: '123',
  token: 'abcdef0123',
  title: 'Fixture Gallery',
  category: 'Manga',
  uploader: 'fixture-user',
  thumb_url: 'https://example.test/thumb.webp',
  posted: '2026-01-01',
  rating: 4.5,
  pages: 12,
  rated: false,
  thumb_width: 250,
  thumb_height: 350,
};

describe('GalleryCard', () => {
  it('replaces a failed thumbnail with a visible fallback', () => {
    render(<GalleryCard gallery={gallery} onClick={vi.fn()} />);

    fireEvent.error(document.querySelector('.gallery-card__thumb')!);

    expect(screen.getByText('Preview unavailable')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Open Fixture Gallery' })).toBeVisible();
    expect(screen.getByText('Manga')).toBeVisible();
  });
});
