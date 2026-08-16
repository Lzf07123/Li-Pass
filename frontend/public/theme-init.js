// 在首帧渲染前应用主题，避免明暗闪烁。
// 保持为外链脚本：生产 CSP 为 default-src 'self'（无 unsafe-inline），
// 内联脚本会被拦截；Vite 会把 public/ 原样拷入构建产物根目录。
(function () {
  try {
    var stored = localStorage.getItem("portal-theme");
    var dark = stored
      ? stored === "dark"
      : window.matchMedia("(prefers-color-scheme: dark)").matches;
    if (dark) {
      document.documentElement.classList.add("dark");
    }
  } catch {
    /* 隐私模式等 localStorage 不可用时静默降级 */
  }
})();
