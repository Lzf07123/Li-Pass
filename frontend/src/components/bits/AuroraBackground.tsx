/**
 * ReactBits Aurora 思路的纯 CSS 轻量版：
 * 三层弥散光斑缓慢漂移，不引入 WebGL 依赖。
 * prefers-reduced-motion 由全局样式统一关闭。
 */
export function AuroraBackground({ className = "" }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={`pointer-events-none absolute inset-0 overflow-hidden ${className}`}
    >
      <div className="aurora-blob aurora-blob-1" />
      <div className="aurora-blob aurora-blob-2" />
      <div className="aurora-blob aurora-blob-3" />
      <div className="aurora-blob aurora-blob-4" />
    </div>
  );
}
