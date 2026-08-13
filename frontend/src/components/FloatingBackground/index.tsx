import { useRef } from "react";

import {
  useFloatingBackground,
  type FloatingBackgroundOptions,
} from "../../hooks/useFloatingBackground";

// Next.js（App Router）项目请在文件首行添加 'use client'; 指令。
// 本仓库为 Vite + React 纯客户端渲染，无需该指令。

/** 组件 Props：在 Hook 配置基础上增加 className，便于与布局配合 */
export interface FloatingBackgroundProps extends FloatingBackgroundOptions {
  /** 附加给 <canvas> 的 className；父容器需为定位元素（如 relative） */
  className?: string;
}

/**
 * 循环飘动背景组件。
 * 铺满父容器（absolute + inset-0），pointer-events 已禁用，不干扰前景交互。
 *
 * 使用示例：
 * ```tsx
 * <div className="relative h-screen">
 *   <FloatingBackground theme="dark" shapeCount={7} opacity={1} speed={1} />
 *   <div className="relative z-10">前景内容</div>
 * </div>
 * ```
 */
export function FloatingBackground({
  theme = "dark",
  opacity = 1,
  speed = 1,
  shapeCount = 7,
  transparent = false,
  calm = false,
  scrollWind = false,
  adaptive = true,
  className = "",
}: FloatingBackgroundProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // 把最新配置交给 Hook；动画循环内部通过 ref 实时读取
  useFloatingBackground(canvasRef, {
    theme,
    opacity,
    speed,
    shapeCount,
    transparent,
    calm,
    scrollWind,
    adaptive,
  });

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className={`pointer-events-none absolute inset-0 z-0 block h-full w-full ${className}`.trim()}
    />
  );
}
