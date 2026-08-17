/**
 * 已登录/后台页加载骨架：与 AppHeader + max-w-7xl 内容区 + SiteFooter
 * 的布局逐区块对齐，替代路由懒加载时的小占位块。
 */
export function PageSkeleton({ title = "" }: { title?: string }) {
  return (
    <div
      aria-busy="true"
      aria-label="正在加载页面"
      className="flex min-h-screen flex-col bg-background"
    >
      <header className="sticky top-0 z-20 border-b border-border bg-surface/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-4 sm:px-6 lg:px-8">
          <div className="shimmer h-8 w-8 rounded-lg" />
          <div className="shimmer h-4 w-24 rounded" />
          {title && (
            <span className="hidden truncate text-sm text-muted sm:inline">
              {title}
            </span>
          )}
          <div className="ml-auto flex items-center gap-2">
            <div className="shimmer h-9 w-20 rounded-lg" />
            <div className="shimmer h-9 w-9 rounded-full" />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 space-y-6 px-4 py-8 sm:px-6 lg:px-8">
        <div className="card p-6 sm:p-8">
          <div className="space-y-4">
            <div className="shimmer h-5 w-40 rounded" />
            <div className="shimmer h-4 w-full rounded" />
            <div className="shimmer h-4 w-3/4 rounded" />
            <div className="shimmer h-11 w-full rounded-lg" />
            <div className="shimmer h-11 w-full rounded-lg" />
          </div>
        </div>
      </main>

      <footer className="border-t border-border/60 bg-surface/60">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-center gap-x-2 gap-y-1 px-4 py-5 lg:px-8">
          <div className="shimmer h-3.5 w-40 rounded" />
          <div className="shimmer h-3.5 w-28 rounded" />
          <div className="shimmer h-3.5 w-16 rounded" />
          <div className="shimmer h-3.5 w-16 rounded" />
          <div className="shimmer h-3.5 w-14 rounded" />
          <div className="shimmer h-3.5 w-14 rounded" />
        </div>
      </footer>
    </div>
  );
}
