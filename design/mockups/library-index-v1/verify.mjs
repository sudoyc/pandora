import { chromium } from '../../../pandora-web/node_modules/@playwright/test/index.mjs';
import { fileURLToPath } from 'node:url';

const mockupUrl = new URL('./index.html', import.meta.url).href;
const outputDir = fileURLToPath(new URL('.', import.meta.url));
const browser = await chromium.launch({ executablePath: '/usr/bin/chromium' });

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function openPage(viewport, options = {}) {
  const page = await browser.newPage({ viewport, ...options });
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  await page.goto(mockupUrl, { waitUntil: 'load' });
  await page.locator('img').evaluateAll((images) => Promise.all(images.map((image) => {
    image.loading = 'eager';
    if (image.complete) return image.naturalWidth > 0;
    return new Promise((resolve) => {
      image.addEventListener('load', () => resolve(image.naturalWidth > 0), { once: true });
      image.addEventListener('error', () => resolve(false), { once: true });
    });
  })));
  const decoded = await page.locator('img').evaluateAll(
    (images) => images.every((image) => image.complete && image.naturalWidth > 0),
  );
  const metrics = await page.evaluate(() => ({
    width: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    cards: document.querySelectorAll('.gallery-card').length,
    icons: document.querySelectorAll('svg.lucide').length,
  }));
  assert(metrics.scrollWidth <= metrics.width, `horizontal overflow: ${JSON.stringify(metrics)}`);
  assert(decoded, 'one or more mockup images failed to decode');
  assert(metrics.cards === 10, `expected 10 cards: ${JSON.stringify(metrics)}`);
  assert(metrics.icons >= 20, `icons did not render: ${JSON.stringify(metrics)}`);
  assert(errors.length === 0, `browser errors: ${errors.join(' | ')}`);
  return page;
}

try {
  const desktop = await openPage({ width: 1440, height: 900 });
  const entranceAnimation = await desktop.locator('.gallery-card').first().evaluate((element) => ({
    name: getComputedStyle(element).animationName,
    duration: getComputedStyle(element).animationDuration,
  }));
  assert(
    entranceAnimation.name === 'card-enter' && entranceAnimation.duration === '0.42s',
    `gallery entrance animation is missing: ${JSON.stringify(entranceAnimation)}`,
  );
  const contrastRatios = await desktop.evaluate(() => {
    const luminance = (color) => {
      const channels = color.match(/[\d.]+/g).slice(0, 3).map((channel) => Number(channel) / 255);
      const linear = channels.map((channel) => channel <= 0.04045
        ? channel / 12.92
        : ((channel + 0.055) / 1.055) ** 2.4);
      return (0.2126 * linear[0]) + (0.7152 * linear[1]) + (0.0722 * linear[2]);
    };
    const ratio = (foregroundSelector, backgroundSelector) => {
      const foreground = getComputedStyle(document.querySelector(foregroundSelector)).color;
      const background = getComputedStyle(document.querySelector(backgroundSelector)).backgroundColor;
      const foregroundLuminance = luminance(foreground);
      const backgroundLuminance = luminance(background);
      return (Math.max(foregroundLuminance, backgroundLuminance) + 0.05)
        / (Math.min(foregroundLuminance, backgroundLuminance) + 0.05);
    };
    return {
      metadata: ratio('.card-meta', 'body'),
      primaryAction: ratio('.primary-action', '.primary-action'),
      activeNavigation: ratio('.rail-button[aria-current="page"]', '.rail-button[aria-current="page"]'),
    };
  });
  assert(
    Object.values(contrastRatios).every((ratio) => ratio >= 4.5),
    `text contrast below WCAG AA: ${JSON.stringify(contrastRatios)}`,
  );
  await desktop.waitForTimeout(700);
  await desktop.screenshot({ path: `${outputDir}/preview-desktop.png` });
  await desktop.locator('#search-input').fill('moss');
  await desktop.waitForFunction(() => document.querySelectorAll('.gallery-card').length === 1);
  assert(await desktop.locator('.gallery-card').count() === 1, 'search did not filter the gallery');
  await desktop.locator('#search-input').fill('');
  await desktop.waitForFunction(() => document.querySelectorAll('.gallery-card').length === 10);
  await desktop.locator('[data-filter="artist-cg"]').click();
  await desktop.waitForFunction(() => document.querySelectorAll('.gallery-card').length === 3);
  assert(await desktop.locator('.gallery-card').count() === 3, 'category filter returned the wrong count');
  await desktop.locator('[data-filter="all"]').click();
  await desktop.locator('button[data-density="compact"]').click();
  await desktop.waitForFunction(() => document.querySelector('#gallery')?.dataset.density === 'compact');
  assert(await desktop.locator('#gallery').getAttribute('data-density') === 'compact', 'compact density did not activate');
  await desktop.locator('button[data-density="cozy"]').click();
  await desktop.waitForFunction(() => document.querySelector('#gallery')?.dataset.density === 'cozy');
  await desktop.locator('.gallery-card').nth(3).locator('.card-main').click();
  await desktop.locator('#inspector-title').filter({ hasText: 'Moss Bloom' }).waitFor();
  await desktop.locator('[data-tab="tags"]').click();
  assert(await desktop.locator('#panel-tags').isVisible(), 'tags panel did not open');
  await desktop.locator('[data-tab="info"]').click();
  await desktop.locator('#download-button').click();
  await desktop.locator('#toast.is-visible').waitFor({ state: 'visible' });
  assert(await desktop.locator('#toast.is-visible').isVisible(), 'download feedback did not appear');
  assert(await desktop.locator('#rail-progress').evaluate((element) => element.style.width) === '64%', 'queue progress did not update');
  await desktop.locator('button[data-mode="list"]').click();
  await desktop.waitForFunction(() => document.querySelector('#gallery')?.dataset.mode === 'list');
  assert(await desktop.locator('#gallery').getAttribute('data-mode') === 'list', 'list mode did not activate');
  await desktop.locator('button[data-mode="grid"]').click();
  await desktop.waitForFunction(() => document.querySelector('#gallery')?.dataset.mode === 'grid');
  await desktop.locator('#toast').waitFor({ state: 'hidden' });
  await desktop.locator('#read-button').click();
  await desktop.locator('#reader:not([hidden])').waitFor();
  await desktop.waitForTimeout(400);
  await desktop.screenshot({ path: `${outputDir}/preview-reader.png` });
  await desktop.locator('#reader-close').click();
  await desktop.close();

  const mobile = await openPage({ width: 390, height: 844 });
  await mobile.waitForFunction(() => document.getAnimations().every((animation) => animation.playState === 'finished'));
  const undersizedTouchTargets = await mobile.locator(
    '.filter-chip, .save-button, .top-actions button, .mobile-nav button',
  ).evaluateAll((elements) => elements.map((element) => {
    const box = element.getBoundingClientRect();
    return { label: element.getAttribute('aria-label') || element.textContent.trim(), width: box.width, height: box.height };
  }).filter((box) => box.width > 0 && box.height > 0 && (box.width < 44 || box.height < 44)));
  assert(
    undersizedTouchTargets.length === 0,
    `mobile touch targets below 44px: ${JSON.stringify(undersizedTouchTargets)}`,
  );
  await mobile.screenshot({ path: `${outputDir}/preview-mobile.png` });
  await mobile.locator('.gallery-card').nth(1).locator('.card-main').click();
  await mobile.locator('#inspector.is-open').waitFor();
  await mobile.waitForTimeout(320);
  const detailBox = await mobile.locator('#inspector').boundingBox();
  assert(
    detailBox && detailBox.x >= 0 && detailBox.width <= 390,
    `mobile detail outside viewport: ${JSON.stringify(detailBox)}`,
  );
  await mobile.screenshot({ path: `${outputDir}/preview-mobile-detail.png` });
  await mobile.locator('#read-button').click();
  await mobile.locator('#reader:not([hidden])').waitFor();
  const readerMetrics = await mobile.evaluate(() => ({
    width: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    imageWidth: document.querySelector('#reader-page-one')?.getBoundingClientRect().width,
  }));
  assert(
    readerMetrics.scrollWidth <= readerMetrics.width && readerMetrics.imageWidth > 0,
    `mobile reader invalid: ${JSON.stringify(readerMetrics)}`,
  );
  await mobile.close();

  const reducedMotion = await openPage(
    { width: 1440, height: 900 },
    { reducedMotion: 'reduce' },
  );
  const reducedMotionDurations = await reducedMotion.locator('.gallery-card').first().evaluate((element) => {
    const style = getComputedStyle(element);
    const toMilliseconds = (value) => value.endsWith('ms')
      ? Number.parseFloat(value)
      : Number.parseFloat(value) * 1000;
    return {
      animation: toMilliseconds(style.animationDuration),
      transition: toMilliseconds(style.transitionDuration),
    };
  });
  assert(
    reducedMotionDurations.animation <= 0.1 && reducedMotionDurations.transition <= 0.1,
    `reduced motion was not respected: ${JSON.stringify(reducedMotionDurations)}`,
  );
  await reducedMotion.close();
} finally {
  await browser.close();
}

console.log('mockup browser audit passed');
