import { vi } from 'vitest';

/** Radix tips measure their box with ResizeObserver, which jsdom lacks. Call in `beforeEach`: mockApi unstubs all globals after each test. */
export function stubResizeObserver() {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
}
