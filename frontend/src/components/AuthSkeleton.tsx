import { AuroraBackground } from "./bits/AuroraBackground";

/**
 * 认证页加载骨架：与 AuthShell 的布局逐区块对齐
 * （品牌区 → 标题/副标题 → 单卡片表单 → 页脚 → 主题切换），
 * 避免路由懒加载/登录态检查时出现与真实页面不对应的小占位块。
 */
export function AuthSkeleton() {
  return (
    <div
      aria-busy="true"
      aria-label="正在加载页面"
      className="relative flex min-h-screen flex-col overflow-hidden bg-background"
    >
      <AuroraBackground />

      <div className="relative flex flex-1 flex-col items-center justify-center px-4 py-10">
        <div className="w-full max-w-md">
          <div
            className="animate-fade-up-slow mb-8 flex flex-col items-center gap-3 text-center"
            style={{ animationDelay: "0.05s" }}
          >
            <div className="shimmer h-12 w-12 rounded-full" />
            <div className="space-y-2">
              <div className="shimmer mx-auto h-11 w-56 rounded-md" />
              <div className="shimmer mx-auto h-4 w-56 rounded-md" />
            </div>
          </div>

          <div
            className="animate-fade-up-slow"
            style={{ animationDelay: "0.18s" }}
          >
            <div className="card p-6 sm:p-8">
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <div className="shimmer h-3.5 w-14 rounded" />
                  <div className="shimmer h-11 w-full rounded-lg" />
                </div>
                <div className="space-y-1.5">
                  <div className="shimmer h-3.5 w-14 rounded" />
                  <div className="shimmer h-11 w-full rounded-lg" />
                </div>
                <div className="space-y-1.5">
                  <div className="shimmer h-3.5 w-14 rounded" />
                  <div className="shimmer h-11 w-full rounded-lg" />
                </div>
                <div className="shimmer h-12 w-full rounded-lg" />
                <div className="shimmer mx-auto h-4 w-44 rounded" />
              </div>
            </div>
          </div>
        </div>
        <div className="mt-8">
          <div className="shimmer mx-auto h-3.5 w-56 rounded" />
        </div>
      </div>

      <div
        className="animate-fade-up-slow relative"
        style={{ animationDelay: "0.32s" }}
      >
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

      <div
        className="animate-fade-up-slow absolute right-4 top-4 sm:right-6 sm:top-6"
        style={{ animationDelay: "0.4s" }}
      >
        <div className="shimmer h-9 w-9 rounded-full" />
      </div>
    </div>
  );
}
