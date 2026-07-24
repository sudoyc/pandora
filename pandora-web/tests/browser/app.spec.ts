import { expect, test } from '@playwright/test';

const gallery = {
  gid: '123',
  token: 'abcdef0123',
  title: 'Fixture Browser Gallery',
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

const detail = {
  ...gallery,
  title_jpn: null,
  cover_url: 'https://example.test/cover.jpg',
  tags: { artist: ['fixture-tag'] },
  size: '1 MB',
  favorite_slot: null,
  preview_pages: 1,
  rating_count: 3,
  favorite_count: 1,
  torrent_count: 0,
  comments: [],
  comments_has_more: false,
  url: 'https://example.test/g/123/abcdef0123/',
};

test('loads the feed and opens detail and reader views', async ({ page }) => {
  await page.route('http://127.0.0.1:7860/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/homepage') {
      await route.fulfill({ json: [gallery] });
      return;
    }
    if (path === '/api/gallery/123/abcdef0123') {
      await route.fulfill({ json: detail });
      return;
    }
    if (path.startsWith('/api/image/proxy') || path.includes('/page/')) {
      await route.fulfill({ status: 200, contentType: 'image/jpeg', body: '' });
      return;
    }
    await route.fulfill({ status: 404, json: { detail: 'Fixture route missing' } });
  });
  await page.routeWebSocket('ws://127.0.0.1:7860/ws', (socket) => {
    socket.send(JSON.stringify({
      event: 'download_queued',
      gid: '999',
      title: 'Fixture Browser Download',
    }));
  });

  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Gallery Feed' })).toBeVisible();
  await expect(page.getByText('Fixture Browser Download')).toBeVisible();
  await page.getByRole('button', { name: /Fixture Browser Gallery/ }).click();
  await expect(page.getByRole('heading', { name: 'Fixture Browser Gallery' })).toBeVisible();

  await page.getByRole('button', { name: 'Read' }).click();
  await expect(page.getByText('2 pages')).toBeVisible();
  await expect(page.locator('.reader-page')).toHaveCount(2);
  const layerOrder = await page.evaluate(() => ({
    drawer: Number(getComputedStyle(document.querySelector('.drawer-content')!).zIndex),
    sidebar: Number(getComputedStyle(document.querySelector('.sidebar')!).zIndex),
  }));
  expect(layerOrder.drawer).toBeGreaterThan(layerOrder.sidebar);
  await expect(page.locator('.reader-page').first()).toHaveAttribute(
    'src',
    'http://127.0.0.1:7860/api/gallery/123/abcdef0123/page/1',
  );

  await page.getByRole('button', { name: 'Exit' }).click();
  await expect(page.locator('.reader-shell')).toBeHidden();
});
