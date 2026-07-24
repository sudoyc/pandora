import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Reader } from './Reader';

describe('Reader', () => {
  it('renders daemon-backed page URLs and closes on command', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <Reader gid="123" token="abcdef0123" pages={3} onClose={onClose} />,
    );

    const pages = screen.getAllByRole('img', { name: /Page/ });
    expect(pages).toHaveLength(3);
    expect(pages[0]).toHaveAttribute(
      'src',
      'http://127.0.0.1:7860/api/gallery/123/abcdef0123/page/1',
    );
    expect(pages[0]).toHaveAttribute('loading', 'eager');
    expect(pages[2]).toHaveAttribute('loading', 'lazy');

    await user.click(screen.getByRole('button', { name: 'Exit reader' }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
