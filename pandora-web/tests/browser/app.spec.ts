import { expect, test } from '@playwright/test';
import type { Page, WebSocketRoute } from '@playwright/test';

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

async function mockGalleryBrowse(page: Page, item = gallery) {
  await page.route('http://127.0.0.1:7860/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/homepage' || path === '/api/search') {
      await route.fulfill({ json: [item] });
      return;
    }
    if (path === '/api/downloads') {
      await route.fulfill({ json: [] });
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
  await page.routeWebSocket('ws://127.0.0.1:7860/ws', () => {});
}

test('loads the feed and opens detail and reader views', async ({ page }) => {
  await page.route('http://127.0.0.1:7860/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/homepage' || path === '/api/search') {
      await route.fulfill({ json: [gallery] });
      return;
    }
    if (path === '/api/downloads') {
      await route.fulfill({ json: [] });
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
  await page.getByPlaceholder('Search galleries...').fill('  fixture query  ');
  await page.getByRole('button', { name: 'Search' }).click();
  await expect(page.getByRole('heading', { name: 'Search: fixture query' })).toBeVisible();
  await expect(page.getByText('Recent: fixture query')).toBeVisible();
  await page.getByRole('button', { name: 'Browse', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Gallery Feed' })).toBeVisible();
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

  await page.getByRole('button', { name: 'Exit reader' }).click();
  await expect(page.locator('.reader-shell')).toBeHidden();
});

test('keeps desktop and mobile layouts within their viewport', async ({ page }) => {
  const longTitle = `Fixture-${'unbroken-title-'.repeat(24)}`;
  await mockGalleryBrowse(page, { ...gallery, title: longTitle });
  await page.goto('/');

  for (const viewport of [
    { width: 1280, height: 800 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    await expect(page.getByRole('search', { name: 'Gallery search' })).toBeVisible();
    await expect(page.getByText(longTitle)).toBeVisible();

    const layout = await page.evaluate(() => {
      const sidebar = document.querySelector<HTMLElement>('.sidebar')!;
      const main = document.querySelector<HTMLElement>('.main-panel')!;
      const title = document.querySelector<HTMLElement>('.gallery-card__title')!;
      const sidebarRect = sidebar.getBoundingClientRect();
      const mainRect = main.getBoundingClientRect();

      return {
        documentWidth: [document.documentElement.scrollWidth, document.documentElement.clientWidth],
        mainWidth: [main.scrollWidth, main.clientWidth],
        titleWidth: [title.scrollWidth, title.clientWidth],
        sidebarRect: {
          right: sidebarRect.right,
          bottom: sidebarRect.bottom,
        },
        mainRect: {
          left: mainRect.left,
          top: mainRect.top,
        },
      };
    });

    expect(layout.documentWidth[0]).toBeLessThanOrEqual(layout.documentWidth[1]);
    expect(layout.mainWidth[0]).toBeLessThanOrEqual(layout.mainWidth[1]);
    expect(layout.titleWidth[0]).toBeLessThanOrEqual(layout.titleWidth[1]);
    if (viewport.width > 760) {
      expect(layout.sidebarRect.right).toBeLessThanOrEqual(layout.mainRect.left);
    } else {
      expect(layout.sidebarRect.bottom).toBeLessThanOrEqual(layout.mainRect.top);
    }
  }
});

test('contains and restores focus across the drawer and reader', async ({ page }) => {
  await mockGalleryBrowse(page);
  await page.goto('/');

  const galleryTrigger = page.getByRole('button', { name: /Fixture Browser Gallery/ });
  await galleryTrigger.focus();
  await expect(galleryTrigger).toBeFocused();
  await page.keyboard.press('Enter');

  const drawer = page.locator('.drawer-content');
  await expect(drawer).toBeVisible();
  await expect.poll(() => drawer.evaluate((element) => element.contains(document.activeElement))).toBe(true);

  const readButton = page.getByRole('button', { name: 'Read' });
  await readButton.click();

  const reader = page.getByRole('dialog', { name: 'Gallery reader' });
  const exitReader = page.getByRole('button', { name: 'Exit reader' });
  await expect(reader).toBeVisible();
  await expect(exitReader).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(exitReader).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(exitReader).toBeFocused();

  await page.keyboard.press('Escape');
  await expect(reader).toBeHidden();
  await expect(drawer).toBeVisible();
  await expect(readButton).toBeFocused();

  await page.keyboard.press('Escape');
  await expect(drawer).toBeHidden();
  await expect(galleryTrigger).toBeFocused();
});

test('reconciles download progress after a daemon restart', async ({ page }) => {
  const sockets: WebSocketRoute[] = [];
  let listRequests = 0;
  let downloadSnapshot = [{
    gid: '321',
    title: 'Restartable Download',
    total_pages: 4,
    status: 'downloading',
    downloaded_pages: 1,
    downloaded_thumbs: 4,
    cover_downloaded: true,
    metadata_saved: true,
    error: '',
    created_at: '2026-01-01T00:00:00Z',
    page_states: { 1: 'completed' },
    failed_pages: [],
  }];

  await page.route('http://127.0.0.1:7860/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/homepage') {
      await route.fulfill({ json: [] });
      return;
    }
    if (path === '/api/downloads') {
      listRequests += 1;
      await route.fulfill({ json: downloadSnapshot });
      return;
    }
    await route.fulfill({ status: 404, json: { detail: 'Fixture route missing' } });
  });
  await page.routeWebSocket('ws://127.0.0.1:7860/ws', (socket) => {
    sockets.push(socket);
  });

  await page.goto('/');

  const row = page.locator('.download-row').filter({ hasText: 'Restartable Download' });
  await expect(row).toContainText('downloading');
  await expect(row.locator('.progress-bar')).toHaveAttribute('style', 'width: 25%;');

  const socketsBeforeRestart = sockets.length;
  const requestsBeforeRestart = listRequests;
  downloadSnapshot = [{
    ...downloadSnapshot[0],
    status: 'queued',
    downloaded_pages: 2,
    page_states: { 1: 'completed', 2: 'completed' },
  }];
  await sockets[sockets.length - 1].close({ code: 1012, reason: 'daemon restart' });

  await expect.poll(() => sockets.length).toBeGreaterThan(socketsBeforeRestart);
  await expect.poll(() => listRequests).toBeGreaterThan(requestsBeforeRestart);
  await expect(row).toContainText('queued');
  await expect(row.locator('.progress-bar')).toHaveAttribute('style', 'width: 50%;');

  sockets[sockets.length - 1].send(JSON.stringify({ event: 'download_complete', gid: '321' }));
  await expect(row).toContainText('completed');
  await expect(row.locator('.progress-bar')).toHaveAttribute('style', 'width: 100%;');
});

test('navigates workspace views and reads a local library gallery', async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => consoleErrors.push(error.message));

  const workspaceGallery = {
    gid: '654',
    token: 'fedcba0123',
    title: 'Fixture Favorite Gallery',
    category: 'Manga',
    uploader: 'fixture-user',
    thumb_url: 'https://example.test/favorite.jpg',
    posted: '2026-01-01',
    rating: 4,
    pages: 2,
    rated: false,
    thumb_width: 250,
    thumb_height: 350,
  };

  await page.route('http://127.0.0.1:7860/api/**', async (route) => {
    const requestUrl = new URL(route.request().url());
    const path = requestUrl.pathname;
    if (path === '/api/homepage') {
      await route.fulfill({ json: [] });
      return;
    }
    if (path === '/api/downloads') {
      await route.fulfill({ json: [] });
      return;
    }
    if (path === '/api/favorites') {
      await route.fulfill({ json: {
        categories: [{ slot: 0, name: 'Archive', count: 1 }],
        galleries: [workspaceGallery],
      } });
      return;
    }
    if (path === '/api/history') {
      await route.fulfill({ json: [{
        gid: '777',
        title: 'Fixture History Gallery',
        title_jpn: null,
        category: 'Manga',
        uploader: 'fixture-user',
        thumb_url: '',
        posted: '2026-01-01',
        rating: 4,
        pages: 3,
        read_page: 1,
        time: 1767225600,
      }] });
      return;
    }
    if (path === '/api/library') {
      await route.fulfill({ json: [{
        gid: '888',
        title: 'Fixture Library Gallery',
        thumb_url: '/api/library/888/file?path=cover',
        pages: 2,
      }] });
      return;
    }
    if (path === '/api/library/888/file') {
      await route.fulfill({ status: 200, contentType: 'image/jpeg', body: '' });
      return;
    }
    if (path.startsWith('/api/image/proxy')) {
      await route.fulfill({ status: 200, contentType: 'image/jpeg', body: '' });
      return;
    }
    await route.fulfill({ status: 404, json: { detail: 'Fixture route missing' } });
  });
  await page.routeWebSocket('ws://127.0.0.1:7860/ws', () => {});

  await page.goto('/');
  await page.getByRole('button', { name: 'Favorites' }).click();
  await expect(page.getByRole('heading', { name: 'Favorites' })).toBeVisible();
  await expect(page.getByText('Fixture Favorite Gallery')).toBeVisible();

  await page.getByRole('button', { name: 'History' }).click();
  await expect(page.getByRole('heading', { name: 'History' })).toBeVisible();
  await expect(page.getByText('Fixture History Gallery')).toBeVisible();

  await page.getByRole('button', { name: 'Downloads' }).click();
  await expect(page.getByRole('heading', { name: 'Downloads' })).toBeVisible();
  await expect(page.getByText('No downloads yet.')).toBeVisible();

  await page.getByRole('button', { name: 'Library' }).click();
  await expect(page.getByRole('heading', { name: 'Library' })).toBeVisible();
  await page.getByRole('button', { name: 'Read Fixture Library Gallery' }).click();
  await expect(page.locator('.reader-shell')).toBeVisible();
  await expect(page.locator('.reader-page').first()).toHaveAttribute(
    'src',
    'http://127.0.0.1:7860/api/library/888/file?path=page/1',
  );
  await page.getByRole('button', { name: 'Exit reader' }).click();
  await expect(page.locator('.reader-shell')).toBeHidden();
  expect(consoleErrors).toEqual([]);
});
