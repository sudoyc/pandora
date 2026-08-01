import { expect, test } from '@playwright/test';
import type { Page, WebSocketRoute } from '@playwright/test';

const fixturePng = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZQ9sAAAAASUVORK5CYII=',
  'base64',
);

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
    if (path === '/api/tags/suggest') {
      await route.fulfill({ json: { suggestions: [] } });
      return;
    }
    if (path === '/api/gallery/123/abcdef0123') {
      await route.fulfill({ json: detail });
      return;
    }
    if (path.startsWith('/api/image/proxy') || path.includes('/page/')) {
      await route.fulfill({ status: 200, contentType: 'image/png', body: fixturePng });
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
    if (path === '/api/tags/suggest') {
      await route.fulfill({ json: { suggestions: [] } });
      return;
    }
    if (path === '/api/gallery/123/abcdef0123') {
      await route.fulfill({ json: detail });
      return;
    }
    if (path.startsWith('/api/image/proxy') || path.includes('/page/')) {
      await route.fulfill({ status: 200, contentType: 'image/png', body: fixturePng });
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

  await expect(page.getByRole('heading', { name: 'Browse Index' })).toBeVisible();
  await expect(page.getByText('Fixture Browser Download')).toBeVisible();
  const thumbnail = page.locator('.gallery-card__thumb').first();
  await expect(thumbnail).toBeVisible();
  await expect.poll(() => thumbnail.evaluate((element) => {
    const image = element as HTMLImageElement;
    return image.complete && image.naturalWidth > 0 && image.naturalHeight > 0;
  })).toBe(true);
  await page.getByPlaceholder('Search galleries...').fill('  fixture query  ');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Search: fixture query' })).toBeVisible();
  await page.getByRole('button', { name: 'Browse', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Browse Index' })).toBeVisible();
  await page.getByPlaceholder('Search galleries...').focus();
  await expect(page.getByText('Recent searches')).toBeVisible();
  await expect(page.getByRole('button', { name: /fixture query.*Quick search/ })).toBeVisible();

  await page.getByRole('button', { name: 'List view' }).click();
  await expect(page.locator('.gallery-grid')).toHaveAttribute('data-layout', 'list');
  await page.getByRole('button', { name: 'Grid view' }).click();
  await page.getByRole('button', { name: 'Compact density' }).click();
  await expect(page.locator('.gallery-grid')).toHaveAttribute('data-density', 'compact');

  await page.getByRole('button', { name: /Color theme/ }).click();
  await page.getByRole('button', { name: 'Use Signal theme' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'signal');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'signal');
  await page.getByRole('button', { name: /Fixture Browser Gallery/ }).click();
  await expect(page.getByRole('heading', { name: 'Fixture Browser Gallery' })).toBeVisible();

  await page.getByRole('button', { name: 'Read' }).click();
  await expect(page.getByLabel('Page 1 of 2')).toBeVisible();
  await expect(page.locator('.reader-page')).toHaveCount(2);
  const readerBox = await page.getByRole('dialog', { name: 'Gallery reader' }).boundingBox();
  expect(readerBox?.x).toBe(0);
  expect(readerBox?.width).toBe(page.viewportSize()?.width);
  const layerOrder = await page.evaluate(() => ({
    drawer: Number(getComputedStyle(document.querySelector('.drawer-content')!).zIndex),
    sidebar: Number(getComputedStyle(document.querySelector('.sidebar')!).zIndex),
  }));
  expect(layerOrder.drawer).toBeGreaterThan(layerOrder.sidebar);
  await expect(page.locator('.reader-page').first()).toHaveAttribute(
    'src',
    'http://127.0.0.1:7860/api/gallery/123/abcdef0123/page/1',
  );
  await expect.poll(() => page.locator('.reader-page').first().evaluate((element) => {
    const image = element as HTMLImageElement;
    return image.complete && image.naturalWidth > 0 && image.naturalHeight > 0;
  })).toBe(true);

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
    await page.waitForFunction(() => document.getAnimations().every((animation) => animation.playState === 'finished'));

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
          top: sidebarRect.top,
          right: sidebarRect.right,
          bottom: sidebarRect.bottom,
        },
        sidebarPosition: getComputedStyle(sidebar).position,
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
      expect(layout.sidebarPosition).toBe('fixed');
      expect(layout.sidebarRect.top).toBeGreaterThanOrEqual(viewport.height - 65);
      expect(layout.sidebarRect.bottom).toBeLessThanOrEqual(viewport.height);
      await expect(page.locator('.sidebar-nav > .nav-item:visible')).toHaveCount(5);
    }
  }
});

test('keeps every color theme above AA text contrast', async ({ page }) => {
  await mockGalleryBrowse(page);
  await page.goto('/');
  await expect(page.locator('.gallery-card__meta')).toBeVisible();

  for (const theme of ['forest', 'signal', 'marine']) {
    const ratios = await page.evaluate((selectedTheme) => {
      document.documentElement.dataset.theme = selectedTheme;
      const luminance = (color: string) => {
        const channels = color.match(/[\d.]+/g)!.slice(0, 3).map(Number).map((value) => value / 255);
        const linear = channels.map((value) => value <= 0.04045
          ? value / 12.92
          : ((value + 0.055) / 1.055) ** 2.4);
        return (0.2126 * linear[0]) + (0.7152 * linear[1]) + (0.0722 * linear[2]);
      };
      const ratio = (foregroundSelector: string, backgroundSelector: string) => {
        const foreground = getComputedStyle(document.querySelector(foregroundSelector)!).color;
        const background = getComputedStyle(document.querySelector(backgroundSelector)!).backgroundColor;
        const foregroundLuminance = luminance(foreground);
        const backgroundLuminance = luminance(background);
        return (Math.max(foregroundLuminance, backgroundLuminance) + 0.05)
          / (Math.min(foregroundLuminance, backgroundLuminance) + 0.05);
      };
      return {
        metadata: ratio('.gallery-card__meta', 'body'),
        rail: ratio('.nav-item:not(.active)', '.sidebar'),
        activeNavigation: ratio('.nav-item.active', '.nav-item.active'),
        search: ratio('.search-form input', '.search-form input'),
      };
    }, theme);

    expect(Object.values(ratios).every((ratio) => ratio >= 4.5), `${theme}: ${JSON.stringify(ratios)}`).toBe(true);
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
  await expect(page.getByRole('slider', { name: 'Reader width' })).toBeFocused();
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

test('keeps the mobile theme, navigation, detail, and reader workflow usable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockGalleryBrowse(page);
  await page.goto('/');
  await page.waitForFunction(() => document.getAnimations().every((animation) => animation.playState === 'finished'));

  await expect(page.locator('.sidebar-nav > .nav-item:visible')).toHaveCount(5);
  const undersizedTargets = await page.locator(
    '.sidebar-nav > .nav-item:visible, .main-header button:visible, .main-header input:visible',
  ).evaluateAll((elements) => elements.map((element) => {
    const box = element.getBoundingClientRect();
    return { label: element.getAttribute('aria-label') ?? element.textContent, width: box.width, height: box.height };
  }).filter((box) => box.width < 44 || box.height < 44));
  expect(undersizedTargets).toEqual([]);

  await page.getByRole('button', { name: 'More' }).click();
  await expect(page.getByRole('region', { name: 'More navigation' })).toBeVisible();
  await page.getByRole('button', { name: 'Use Marine theme' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'marine');
  await page.getByRole('button', { name: 'Close more menu' }).last().click();

  await page.getByRole('button', { name: 'Search filters' }).click();
  await expect(page.getByRole('region', { name: 'Search filters' })).toBeVisible();
  const filterTargetSizes = await page.locator(
    '.search-panel button:visible, .search-panel input[type="number"]:visible, .search-panel label:visible',
  ).evaluateAll((elements) => elements.map((element) => {
    const box = element.getBoundingClientRect();
    return { label: element.textContent, width: box.width, height: box.height };
  }).filter((box) => box.width < 44 || box.height < 44));
  expect(filterTargetSizes).toEqual([]);
  const searchPanelWidth = await page.locator('.search-panel').evaluate((element) => ({
    scroll: element.scrollWidth,
    client: element.clientWidth,
  }));
  expect(searchPanelWidth.scroll).toBeLessThanOrEqual(searchPanelWidth.client);
  const actionBar = await page.locator('.search-panel__footer').boundingBox();
  const mobileNavigation = await page.locator('.sidebar').boundingBox();
  expect(actionBar?.y).toBeGreaterThanOrEqual(0);
  expect((actionBar?.y ?? 0) + (actionBar?.height ?? 0)).toBeLessThanOrEqual(mobileNavigation?.y ?? 0);
  await page.getByRole('button', { name: 'Close search filters' }).click();

  await page.getByRole('button', { name: /Open Fixture Browser Gallery/ }).click();
  const detailBox = await page.locator('.drawer-content').boundingBox();
  expect(detailBox?.x).toBe(0);
  expect(detailBox?.width).toBe(390);
  expect((detailBox?.y ?? 0) + (detailBox?.height ?? 0)).toBeLessThanOrEqual(844 - 64);

  await page.getByRole('button', { name: 'Read' }).click();
  const reader = page.getByRole('dialog', { name: 'Gallery reader' });
  const readerBox = await reader.boundingBox();
  expect(readerBox).toMatchObject({ x: 0, y: 0, width: 390, height: 844 });
  await expect(page.getByRole('slider', { name: 'Reader width' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Exit reader' }).click();

  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.reload();
  const reducedDuration = await page.locator('.gallery-card').first().evaluate((element) => {
    const value = getComputedStyle(element).animationDuration;
    return value.endsWith('ms') ? Number.parseFloat(value) : Number.parseFloat(value) * 1000;
  });
  expect(reducedDuration).toBeLessThanOrEqual(0.1);
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
      await route.fulfill({ status: 200, contentType: 'image/png', body: fixturePng });
      return;
    }
    if (path.startsWith('/api/image/proxy')) {
      await route.fulfill({ status: 200, contentType: 'image/png', body: fixturePng });
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
  await expect.poll(() => page.locator('.reader-page').first().evaluate((element) => {
    const image = element as HTMLImageElement;
    return image.complete && image.naturalWidth > 0 && image.naturalHeight > 0;
  })).toBe(true);
  await page.getByRole('button', { name: 'Exit reader' }).click();
  await expect(page.locator('.reader-shell')).toBeHidden();
  expect(consoleErrors).toEqual([]);
});

test('prefetches the next browse batch by cursor and stops after the empty batch', async ({ page }) => {
  const requestedCursors: Array<string | null> = [];
  const makeGallery = (gid: number) => ({
    ...gallery,
    gid: String(gid),
    token: `token${gid}`,
    title: `Paged Gallery ${gid}`,
  });

  await page.route('http://127.0.0.1:7860/api/**', async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === '/api/homepage') {
      const cursor = url.searchParams.get('next');
      requestedCursors.push(cursor);
      if (cursor === null) {
        await route.fulfill({ json: Array.from({ length: 24 }, (_, index) => makeGallery(index + 10)) });
      } else if (cursor === '33') {
        await route.fulfill({ json: [makeGallery(34), makeGallery(35)] });
      } else {
        await route.fulfill({ json: [] });
      }
      return;
    }
    if (url.pathname === '/api/search') {
      await route.fulfill({ json: url.searchParams.has('next') ? [] : [makeGallery(50)] });
      return;
    }
    if (url.pathname === '/api/downloads') {
      await route.fulfill({ json: [] });
      return;
    }
    if (url.pathname === '/api/tags/suggest') {
      await route.fulfill({ json: { suggestions: [] } });
      return;
    }
    if (url.pathname.startsWith('/api/image/proxy')) {
      await route.fulfill({ status: 200, contentType: 'image/png', body: fixturePng });
      return;
    }
    await route.fulfill({ status: 404, json: { detail: 'Fixture route missing' } });
  });
  await page.routeWebSocket('ws://127.0.0.1:7860/ws', () => {});

  await page.goto('/');
  await expect(page.getByText('Paged Gallery 10')).toBeVisible();

  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  await expect(page.getByText('Paged Gallery 35')).toBeVisible();
  await expect(page.locator('.gallery-card')).toHaveCount(26);
  await expect(page.getByText('End of results')).toBeVisible();
  expect(requestedCursors).toEqual([null, '33', '35']);

  await page.getByPlaceholder('Search galleries...').fill('fresh search');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
});

test('builds a search from tag suggestions and advanced filters', async ({ page }) => {
  const searchRequests: URL[] = [];
  await page.route('http://127.0.0.1:7860/api/**', async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === '/api/homepage' || url.pathname === '/api/search') {
      if (url.pathname === '/api/search') searchRequests.push(url);
      await route.fulfill({ json: [gallery] });
      return;
    }
    if (url.pathname === '/api/tags/suggest') {
      await route.fulfill({ json: { suggestions: [{
        namespace: 'female',
        tag: 'stockings',
        translation: 'Silk stockings',
      }] } });
      return;
    }
    if (url.pathname === '/api/downloads') {
      await route.fulfill({ json: [] });
      return;
    }
    if (url.pathname.startsWith('/api/image/proxy')) {
      await route.fulfill({ status: 200, contentType: 'image/png', body: fixturePng });
      return;
    }
    await route.fulfill({ status: 404, json: { detail: 'Fixture route missing' } });
  });
  await page.routeWebSocket('ws://127.0.0.1:7860/ws', () => {});

  await page.goto('/');
  const searchInput = page.getByPlaceholder('Search galleries...');
  await searchInput.fill('stock');
  await page.getByRole('option', { name: /female:stockings.*Silk stockings/ }).click();
  await expect(searchInput).toHaveValue('female:"stockings$" ');

  await page.getByRole('button', { name: /Search filters, 1 active/ }).click();
  await page.getByRole('checkbox', { name: 'Doujinshi' }).uncheck();
  await page.getByRole('button', { name: '4+' }).click();
  await page.getByRole('spinbutton', { name: 'Minimum' }).fill('10');
  await page.getByRole('spinbutton', { name: 'Maximum' }).fill('30');
  await page.getByRole('checkbox', { name: 'Gallery name' }).check();
  await page.getByRole('checkbox', { name: 'Any language' }).check();
  await page.getByRole('button', { name: 'Apply search' }).click();

  await expect(page.getByRole('heading', { name: 'Search: female:"stockings$"' })).toBeVisible();
  await expect.poll(() => searchRequests.length).toBeGreaterThan(0);
  const parameters = searchRequests.at(-1)!.searchParams;
  expect(parameters.get('keyword')).toBe('female:"stockings$"');
  expect(parameters.get('category')).toBe('1021');
  expect(parameters.get('min_rating')).toBe('4');
  expect(parameters.get('min_pages')).toBe('10');
  expect(parameters.get('max_pages')).toBe('30');
  expect(parameters.get('search_name')).toBe('true');
  expect(parameters.get('search_tags')).toBe('true');
  expect(parameters.get('disable_language_filter')).toBe('true');

  await page.getByRole('button', { name: 'Remove Rating 4+ filter' }).click();
  await expect.poll(() => searchRequests.at(-1)?.searchParams.has('min_rating')).toBe(false);
});
