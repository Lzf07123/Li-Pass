import "@testing-library/jest-dom/vitest";

/**
 * jsdom 不提供 IntersectionObserver；FadeIn 的视口渐显依赖它。
 * 这里提供最小实现并默认“立即可见”，保证测试中内容可查询。
 */
class IntersectionObserverMock implements IntersectionObserver {
  readonly root: Element | Document | null = null;
  readonly rootMargin: string = "0px";
  readonly scrollMargin: string = "0px";
  readonly thresholds: ReadonlyArray<number> = [0];

  private readonly callback: IntersectionObserverCallback;

  constructor(callback: IntersectionObserverCallback) {
    this.callback = callback;
  }

  observe(target: Element) {
    const entry: IntersectionObserverEntry = {
      boundingClientRect: target.getBoundingClientRect(),
      intersectionRatio: 1,
      intersectionRect: target.getBoundingClientRect(),
      isIntersecting: true,
      rootBounds: null,
      target,
      time: 0,
    };
    this.callback([entry], this as unknown as IntersectionObserver);
  }

  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
}

Object.defineProperty(globalThis, "IntersectionObserver", {
  writable: true,
  configurable: true,
  value: IntersectionObserverMock,
});

// 当前 jsdom 环境未暴露 window.localStorage；提供内存实现，
// 支撑「记住账号/密码」相关测试（生产环境使用浏览器真实 localStorage）。
if (typeof window.localStorage === "undefined") {
  class MemoryStorage implements Storage {
    private readonly store = new Map<string, string>();

    get length(): number {
      return this.store.size;
    }

    clear(): void {
      this.store.clear();
    }

    getItem(key: string): string | null {
      return this.store.has(key) ? (this.store.get(key) as string) : null;
    }

    key(index: number): string | null {
      return Array.from(this.store.keys())[index] ?? null;
    }

    removeItem(key: string): void {
      this.store.delete(key);
    }

    setItem(key: string, value: string): void {
      this.store.set(key, String(value));
    }
  }

  Object.defineProperty(window, "localStorage", {
    writable: true,
    configurable: true,
    value: new MemoryStorage(),
  });
}
