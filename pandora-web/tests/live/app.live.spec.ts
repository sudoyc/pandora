import { expect, test } from '@playwright/test';
import type { Locator } from '@playwright/test';

const daemonUrl = new URL(
  process.env.PANDORA_LIVE_DAEMON_URL ?? 'http://127.0.0.1:7860',
).origin;
const requestedSamples = Number.parseInt(process.env.PANDORA_LIVE_IMAGE_SAMPLES ?? '5', 10);
const imageSamples = Number.isFinite(requestedSamples) && requestedSamples > 0
  ? requestedSamples
  : 5;

function isDaemonImageRequest(rawUrl: string): boolean {
  const url = new URL(rawUrl);
  return url.origin === daemonUrl && (
    url.pathname === '/api/image/proxy'
    || /^\/api\/gallery\/[^/]+\/[^/]+\/page\/\d+$/.test(url.pathname)
  );
}

async function expectDecodedImage(image: Locator): Promise<void> {
  await image.scrollIntoViewIfNeeded();
  await expect(image).toBeVisible();
  await expect.poll(() => image.evaluate((element) => {
    const candidate = element as HTMLImageElement;
    return candidate.complete && candidate.naturalWidth > 0 && candidate.naturalHeight > 0;
  })).toBe(true);
}

test('live browse appends a distinct gallery batch with the upstream cursor', async ({ page }) => {
  const firstResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.origin === daemonUrl
      && url.pathname === '/api/homepage'
      && !url.searchParams.has('next');
  });
  const nextResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.origin === daemonUrl
      && url.pathname === '/api/homepage'
      && url.searchParams.has('next');
  });

  await page.goto('/');
  const firstResponse = await firstResponsePromise;
  const firstBatch = await firstResponse.json() as Array<{ gid: string }>;
  expect(firstBatch.length).toBeGreaterThan(0);

  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  const nextResponse = await nextResponsePromise;
  const nextBatch = await nextResponse.json() as Array<{ gid: string }>;
  expect(nextBatch.length).toBeGreaterThan(0);

  const nextUrl = new URL(nextResponse.url());
  expect(nextUrl.searchParams.get('next')).toBe(String(firstBatch.at(-1)!.gid));
  const firstIds = new Set(firstBatch.map((gallery) => String(gallery.gid)));
  expect(nextBatch.some((gallery) => firstIds.has(String(gallery.gid)))).toBe(false);

  const uniqueIds = new Set([
    ...firstBatch.map((gallery) => String(gallery.gid)),
    ...nextBatch.map((gallery) => String(gallery.gid)),
  ]);
  await expect.poll(() => page.locator('.gallery-card').count()).toBeGreaterThanOrEqual(uniqueIds.size);
});

test('live browse journey renders real thumbnail, cover, and reader pixels', async ({ page, request }) => {
  const readinessResponse = await request.get(`${daemonUrl}/api/readiness`);
  expect(readinessResponse.status(), 'daemon readiness endpoint must respond').toBe(200);
  const readiness = await readinessResponse.json();
  expect(readiness).toMatchObject({
    ready: true,
    session: 'valid',
    checks: {
      homepage: 'ok',
      search: 'ok',
      popular: 'ok',
      home: 'ok',
    },
  });

  const imageFailures: Array<{ path: string; status: number }> = [];
  const directUpstreamRequests: string[] = [];
  const runtimeErrors: string[] = [];
  page.on('request', (request) => {
    const hostname = new URL(request.url()).hostname;
    if ([
      'e-hentai.org',
      'exhentai.org',
      'ehgt.org',
      'hath.network',
    ].some((base) => hostname === base || hostname.endsWith(`.${base}`))) {
      directUpstreamRequests.push(hostname);
    }
  });
  page.on('response', (response) => {
    const url = new URL(response.url());
    if (isDaemonImageRequest(response.url()) && response.status() >= 400) {
      imageFailures.push({ path: url.pathname, status: response.status() });
    }
  });
  page.on('requestfailed', (request) => {
    if (isDaemonImageRequest(request.url())) {
      imageFailures.push({ path: new URL(request.url()).pathname, status: 0 });
    }
  });
  page.on('pageerror', (error) => runtimeErrors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text());
  });

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Browse Index' })).toBeVisible();

  const cards = page.locator('.gallery-card');
  await expect.poll(() => cards.count()).toBeGreaterThanOrEqual(imageSamples);
  const thumbnails = page.locator('.gallery-card__thumb');
  await expect.poll(() => thumbnails.count()).toBeGreaterThanOrEqual(imageSamples);
  for (let index = 0; index < imageSamples; index += 1) {
    await expectDecodedImage(thumbnails.nth(index));
  }

  const coldProbeSources: string[] = [];
  for (let index = 0; index < imageSamples; index += 1) {
    const proxySource = await thumbnails.nth(index).getAttribute('src');
    if (!proxySource) throw new Error(`live thumbnail ${index} has no proxy source`);
    const coldProxyUrl = new URL(proxySource);
    expect(coldProxyUrl.origin, 'the Web app must use the target daemon').toBe(daemonUrl);
    const upstreamSource = coldProxyUrl.searchParams.get('url');
    if (!upstreamSource) throw new Error(`live thumbnail ${index} has no upstream source`);
    const coldUpstreamUrl = new URL(upstreamSource);
    coldUpstreamUrl.hash = `pandora-live-${Date.now()}-${index}`;
    coldProxyUrl.searchParams.set('url', coldUpstreamUrl.toString());
    coldProbeSources.push(coldProxyUrl.toString());
  }
  const coldProbeDecoded = await page.evaluate((sources) => Promise.all(
    sources.map((src) => new Promise<boolean>((resolve) => {
      const image = new Image();
      const timeout = window.setTimeout(() => resolve(false), 20_000);
      image.onload = () => {
        window.clearTimeout(timeout);
        resolve(image.naturalWidth > 0 && image.naturalHeight > 0);
      };
      image.onerror = () => {
        window.clearTimeout(timeout);
        resolve(false);
      };
      image.src = src;
    })),
  ), coldProbeSources);
  expect(
    coldProbeDecoded.every(Boolean),
    'concurrent cache-miss image probes must decode',
  ).toBe(true);

  await cards.first().click();
  const drawer = page.locator('.drawer-content');
  await expect(drawer).toBeVisible();
  await expectDecodedImage(drawer.locator('.drawer-cover'));

  await drawer.getByRole('button', { name: 'Read' }).click();
  const reader = page.getByRole('dialog', { name: 'Gallery reader' });
  const readerBox = await reader.boundingBox();
  expect(readerBox?.x).toBe(0);
  expect(readerBox?.width).toBe(page.viewportSize()?.width);
  const firstReaderPage = page.locator('.reader-page').first();
  await expectDecodedImage(firstReaderPage);
  const readerSource = await firstReaderPage.getAttribute('src');
  if (!readerSource) throw new Error('first reader page has no source');
  expect(new URL(readerSource).origin, 'the reader must use the target daemon').toBe(daemonUrl);

  expect(imageFailures, 'all requested image endpoints must succeed').toEqual([]);
  expect(directUpstreamRequests, 'the browser must use the daemon for upstream images').toEqual([]);
  expect(runtimeErrors, 'the live browse journey must not emit browser errors').toEqual([]);
});
