import '@testing-library/jest-dom/vitest';

// jsdom does not implement IntersectionObserver, but framer-motion's
// `whileInView` calls it unguarded on mount. Provide a minimal no-op stub.
class IntersectionObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
}
globalThis.IntersectionObserver = IntersectionObserverStub as unknown as typeof IntersectionObserver;

// jsdom also lacks matchMedia, which useReducedMotion() (and other
// media-query-based hooks) rely on.
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener() {},
      removeEventListener() {},
      addListener() {},
      removeListener() {},
      dispatchEvent() {
        return false;
      },
    }) as unknown as MediaQueryList;
}
