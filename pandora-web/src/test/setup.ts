import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

afterEach(cleanup);

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

globalThis.ResizeObserver = ResizeObserverStub;

const storage = new Map<string, string>();
const localStorageStub: Storage = {
  get length() {
    return storage.size;
  },
  clear() {
    storage.clear();
  },
  getItem(key) {
    return storage.get(String(key)) ?? null;
  },
  key(index) {
    return Array.from(storage.keys())[index] ?? null;
  },
  removeItem(key) {
    storage.delete(String(key));
  },
  setItem(key, value) {
    storage.set(String(key), String(value));
  },
};
Object.defineProperty(globalThis, 'localStorage', {
  configurable: true,
  value: localStorageStub,
});

Object.defineProperty(window, 'matchMedia', {
  configurable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener() {},
    removeListener() {},
    addEventListener() {},
    removeEventListener() {},
    dispatchEvent: () => false,
  }),
});
