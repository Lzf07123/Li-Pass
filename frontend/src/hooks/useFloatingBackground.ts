import { useCallback, useEffect, useRef } from "react";
import type { RefObject } from "react";

/**
 * 循环飘动背景 Hook —— 纯 Canvas 实现，不依赖任何第三方库。
 *
 * 设计要点：
 * - 三种几何形状（Z 形 / 正方形 / 平行四边形）做「水平匀速漂移 + 垂直正弦摆动」的复合运动；
 * - 元素透明度极低、速度极慢，形成“环境呼吸感”而非抢戏的动画；
 * - 全程只做 Canvas 位图绘制，不触碰 DOM 布局，天然不触发回流；
 * - 时间步长归一化到 60fps 基准，在 120Hz 高刷屏上不会加速、掉帧时不会变慢；
 * - 支持焦点减速（calm）、滚动风速（scrollWind）、移动端自动减量（adaptive）。
 */

/** 主题类型：深色 / 浅色 / 自动（跟随 html.dark 类，与站点的类主题保持同步） */
export type FloatingBackgroundTheme = "dark" | "light" | "auto";

/** Hook 的配置项（与组件 Props 保持一致） */
export interface FloatingBackgroundOptions {
  /** 主题，默认 "dark"；"auto" 会跟随 <html> 上的 dark 类自动切换 */
  theme?: FloatingBackgroundTheme;
  /** 全局透明度倍率（默认 1）：与每个形状自身透明度相乘 */
  opacity?: number;
  /** 全局速度倍率（默认 1）：与每个形状自身速度相乘 */
  speed?: number;
  /** 漂浮形状数量，默认 7（建议 3~20，内部会夹取到 3~40） */
  shapeCount?: number;
  /** 透明画布（默认 false）：true 时不绘制背景色、只清除像素，让站点自身背景透出 */
  transparent?: boolean;
  /** 焦点减速（默认 false）：true 时整体速度平滑降为 0.5 倍，用于表单聚焦时降低干扰 */
  calm?: boolean;
  /** 滚动风速（默认 false）：静止时 0.5 倍速慢呼吸，快速滚动时最高 1.5 倍速，模拟“风吹数据流” */
  scrollWind?: boolean;
  /** 移动端自动减量（默认 true）：<768px 时形状数 ≤6、速度 ×2/3、透明度 ×0.5 */
  adaptive?: boolean;
}

/** 几何形状种类 */
type ShapeKind = "z" | "square" | "parallelogram";

/** 单个漂浮形状的运行时状态 */
interface FloatShape {
  kind: ShapeKind;
  /** 归一化横坐标（0~1），绘制时乘以画布宽度得到像素值；越界后在边缘回绕 */
  x: number;
  /** 归一化纵坐标（中心点，0.08~0.92），绘制时乘以画布高度 */
  y: number;
  /** 形状边长（px），按「近大远小」分层分配 */
  size: number;
  /** 元素自身透明度（0.04~0.15），再乘全局 opacity 属性 */
  alpha: number;
  /** 水平速度基准（px/帧，60fps 基准） */
  speed: number;
  /** 水平方向：1 向右、-1 向左，混合方向更自然 */
  direction: 1 | -1;
  /** 正弦波振幅（px）：垂直摆动的最大偏移 */
  amplitude: number;
  /** 正弦波频率（rad/帧，60fps 基准） */
  frequency: number;
  /** 正弦波初始相位（rad），用于让各元素错峰、避免同频共振 */
  phase: number;
  /** 描边宽度（px） */
  lineWidth: number;
}

/** 主题调色板（RGB 分量拆分存储，便于主题切换时逐通道平滑过渡） */
interface ThemeColors {
  background: readonly [number, number, number];
  stroke: readonly [number, number, number];
  strokeAlpha: number;
  fillAlpha: number;
}

/** 深色 / 浅色主题调色板 */
const THEME_COLORS: Record<"dark" | "light", ThemeColors> = {
  dark: {
    background: [58, 63, 69], // #3A3F45（D1 雾灰夜色）
    stroke: [196, 203, 208], // 雾灰描边
    strokeAlpha: 0.55, // 描边自身透明度（与形状整体透明度相乘）
    fillAlpha: 0.04, // 填充自身透明度（极淡的填充）
  },
  light: {
    background: [246, 251, 249], // #F6FBF9（海玻璃）
    stroke: [90, 105, 100], // 浅色背景改用雾绿灰描边
    strokeAlpha: 0.5,
    fillAlpha: 0.05,
  },
};

/** 运行时调色板（可被主题过渡插值，因此是可变的） */
interface Palette {
  background: [number, number, number];
  stroke: [number, number, number];
  strokeAlpha: number;
  fillAlpha: number;
}

/** 形状种类轮换表：按顺序均匀分配三种形状 */
const SHAPE_KINDS: ShapeKind[] = ["z", "square", "parallelogram"];

/** 区间随机数 */
function rand(min: number, max: number): number {
  return min + Math.random() * (max - min);
}

/** 数值夹取到 [min, max] */
function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/** 线性插值 */
function lerp(from: number, to: number, amount: number): number {
  return from + (to - from) * amount;
}

/** 把 RGB 分量与透明度拼成 rgba() 颜色串 */
function rgba(rgb: readonly number[], alpha: number): string {
  return `rgba(${Math.round(rgb[0])}, ${Math.round(rgb[1])}, ${Math.round(rgb[2])}, ${alpha})`;
}

/** 读取当前是否为深色：以 <html> 的 dark 类为唯一事实源（SSR 安全） */
function isDarkDocument(): boolean {
  return (
    typeof document !== "undefined" &&
    document.documentElement.classList.contains("dark")
  );
}

/** 把 "auto" 主题解析为具体的 "dark" / "light" */
function resolveTheme(theme: FloatingBackgroundTheme): "dark" | "light" {
  if (theme === "auto") return isDarkDocument() ? "dark" : "light";
  return theme;
}

/** 把主题调色板整体写入运行时调色板（用于无动画循环时的瞬时切换） */
function applyThemeColors(palette: Palette, colors: ThemeColors): void {
  for (let channel = 0; channel < 3; channel++) {
    palette.background[channel] = colors.background[channel];
    palette.stroke[channel] = colors.stroke[channel];
  }
  palette.strokeAlpha = colors.strokeAlpha;
  palette.fillAlpha = colors.fillAlpha;
}

/**
 * 生成单个漂浮形状。
 * 按 index % 3 分三层：远景（大、淡、慢）、中景（中等）、近景（小、更明显、稍快），
 * 形成「近大远小」的空间纵深，而不是等大元素的平铺。
 */
function createShape(kind: ShapeKind, index: number): FloatShape {
  const layer = index % 3;
  const sizeRange =
    layer === 0 ? [80, 120] : layer === 1 ? [45, 80] : [30, 45];
  const alphaRange =
    layer === 0 ? [0.04, 0.07] : layer === 1 ? [0.07, 0.11] : [0.11, 0.15];
  const speedRange =
    layer === 0 ? [0.15, 0.2] : layer === 1 ? [0.2, 0.28] : [0.28, 0.35];

  return {
    kind,
    x: Math.random(),
    y: rand(0.08, 0.92),
    size: rand(sizeRange[0], sizeRange[1]),
    alpha: rand(alphaRange[0], alphaRange[1]),
    speed: rand(speedRange[0], speedRange[1]),
    direction: Math.random() < 0.5 ? 1 : -1,
    amplitude: rand(20, 50),
    frequency: rand(0.005, 0.015),
    phase: rand(0, Math.PI * 2),
    lineWidth: rand(1, 1.5),
  };
}

/**
 * 绑定一个 <canvas> 作为循环飘动背景。
 *
 * @param canvasRef 指向 <canvas> 元素的 ref
 * @param options   主题 / 透明度 / 速度 / 数量等配置（后续变化会实时生效）
 */
export function useFloatingBackground(
  canvasRef: RefObject<HTMLCanvasElement | null>,
  options: FloatingBackgroundOptions = {},
): void {
  const {
    theme = "dark",
    opacity = 1,
    speed = 1,
    shapeCount = 7,
    transparent = false,
    calm = false,
    scrollWind = false,
    adaptive = true,
  } = options;

  // 动画循环内只读取 ref，不依赖闭包捕获的旧 props，保证配置变化实时生效
  const optionsRef = useRef({
    theme,
    opacity,
    speed,
    shapeCount,
    transparent,
    calm,
    scrollWind,
    adaptive,
  });
  useEffect(() => {
    optionsRef.current = {
      theme,
      opacity,
      speed,
      shapeCount,
      transparent,
      calm,
      scrollWind,
      adaptive,
    };
  });

  // 形状数组：仅在数量或移动端断点变化时重建，其他配置变化不打断运动状态
  const shapesRef = useRef<FloatShape[]>([]);
  const rebuildShapes = useCallback(
    (count: number, mobile: boolean, adaptiveOn: boolean) => {
      const base = clamp(Math.floor(count), 3, 40);
      const limit = adaptiveOn && mobile ? Math.min(base, 6) : base;
      shapesRef.current = Array.from({ length: limit }, (_, index) =>
        createShape(SHAPE_KINDS[index % SHAPE_KINDS.length], index),
      );
    },
    [],
  );

  // 移动端断点：<768px 视为移动端（与设计报告的降级阈值一致）
  const mobileRef = useRef(false);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const query = window.matchMedia("(max-width: 767px)");
    mobileRef.current = query.matches;
    const handleChange = (event: MediaQueryListEvent) => {
      mobileRef.current = event.matches;
      rebuildShapes(
        optionsRef.current.shapeCount,
        event.matches,
        optionsRef.current.adaptive,
      );
    };
    query.addEventListener("change", handleChange);
    return () => query.removeEventListener("change", handleChange);
  }, [rebuildShapes]);

  useEffect(() => {
    rebuildShapes(shapeCount, mobileRef.current, adaptive);
  }, [shapeCount, adaptive, rebuildShapes]);

  // 焦点减速系数：目标 0.5（聚焦）或 1（失焦），逐帧平滑逼近避免速度突变
  const calmFactorRef = useRef(calm ? 0.5 : 1);
  // 滚动风速状态：velocity 为瞬时滚动幅度，逐帧指数衰减
  const windRef = useRef({ velocity: 0 });

  // 滚动联动：仅在开启 scrollWind 时监听，静止时速度自然衰减回 0.5 倍慢呼吸
  useEffect(() => {
    if (!scrollWind) return;
    let lastY = window.scrollY;
    const handleScroll = () => {
      const delta = Math.abs(window.scrollY - lastY);
      lastY = window.scrollY;
      if (delta > 0) {
        windRef.current.velocity = Math.max(
          windRef.current.velocity,
          Math.min(delta, 30),
        );
      }
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, [scrollWind]);

  // 调色板：初始化为当前主题，动画循环中每帧向目标主题颜色平滑插值
  const initialColors = THEME_COLORS[resolveTheme(optionsRef.current.theme)];
  const paletteRef = useRef<Palette>({
    background: [
      initialColors.background[0],
      initialColors.background[1],
      initialColors.background[2],
    ],
    stroke: [
      initialColors.stroke[0],
      initialColors.stroke[1],
      initialColors.stroke[2],
    ],
    strokeAlpha: initialColors.strokeAlpha,
    fillAlpha: initialColors.fillAlpha,
  });
  // "auto" 主题下的深色状态：由 MutationObserver 跟随 html.dark 类更新
  const autoDarkRef = useRef(isDarkDocument());

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    let width = 0;
    let height = 0;
    let dpr = 1;
    let animationFrameId = 0;
    let resizeTimer: number | undefined;
    // jsdom / 老旧环境下可能没有 rAF：此时只绘制静态帧，不做动画循环
    const supportsRaf = typeof window.requestAnimationFrame === "function";

    // 系统「减弱动态效果」偏好：命中时只渲染一帧静态画面，不启动动画循环
    const motionQuery =
      typeof window.matchMedia === "function"
        ? window.matchMedia("(prefers-reduced-motion: reduce)")
        : null;
    let reducedMotion = motionQuery?.matches ?? false;

    /**
     * 绘制一帧：先清屏（可选填充背景色），再逐个绘制形状。
     * 所有绘制都在 Canvas 位图内完成，不触碰 DOM，因此不会引发回流。
     */
    const drawFrame = (): void => {
      if (width === 0 || height === 0) return;
      const palette = paletteRef.current;
      // 整体透明度 = 形状自身透明度 × 全局 opacity × 移动端减量（0.5）
      const mobileOpacity =
        optionsRef.current.adaptive && mobileRef.current ? 0.5 : 1;
      const opacityFactor =
        clamp(optionsRef.current.opacity, 0, 1) * mobileOpacity;

      context.clearRect(0, 0, width, height);
      if (!optionsRef.current.transparent) {
        context.fillStyle = rgba(palette.background, 1);
        context.fillRect(0, 0, width, height);
      }

      for (const shape of shapesRef.current) {
        // 水平位置来自归一化坐标；垂直位置叠加正弦波：水平匀速 + 垂直摆动
        const x = shape.x * width;
        const y =
          shape.y * height + Math.sin(shape.phase) * shape.amplitude;
        const half = shape.size / 2;
        const globalAlpha = clamp(shape.alpha * opacityFactor, 0, 1);
        if (globalAlpha < 0.005) continue; // 过淡则跳过绘制，节省开销

        context.save();
        context.globalAlpha = globalAlpha;
        context.lineWidth = shape.lineWidth;
        context.strokeStyle = rgba(palette.stroke, palette.strokeAlpha);
        context.fillStyle = rgba(palette.stroke, palette.fillAlpha);
        context.beginPath();

        switch (shape.kind) {
          case "z":
            // Z 形：上横、斜线、下横
            context.moveTo(x - half, y - half);
            context.lineTo(x + half, y - half);
            context.lineTo(x - half, y + half);
            context.lineTo(x + half, y + half);
            break;
          case "square":
            context.rect(x - half, y - half, shape.size, shape.size);
            break;
          case "parallelogram":
            // 平行四边形：上半部分整体向右偏移 skew，形成倾斜
            {
              const skew = shape.size * 0.4;
              context.moveTo(x - half + skew, y - half);
              context.lineTo(x + half + skew, y - half);
              context.lineTo(x + half, y + half);
              context.lineTo(x - half, y + half);
              context.closePath();
            }
            break;
        }

        // Z 形为开放折线，不填充；正方形与平行四边形填充极淡底色
        if (shape.kind !== "z") context.fill();
        context.stroke();
        context.restore();
      }
    };

    /** Retina 适配：按 devicePixelRatio 放大画布位图，坐标仍使用 CSS 像素 */
    const resizeCanvas = (): void => {
      dpr = Math.min(window.devicePixelRatio || 1, 2); // DPR 封顶 2，避免超高倍屏过度开销
      width = canvas.clientWidth;
      height = canvas.clientHeight;
      const targetWidth = Math.round(width * dpr);
      const targetHeight = Math.round(height * dpr);
      if (canvas.width !== targetWidth || canvas.height !== targetHeight) {
        canvas.width = targetWidth;
        canvas.height = targetHeight;
      }
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      drawFrame(); // 尺寸变化后立即重绘，避免露出空白
    };

    /** 窗口 resize 防抖：停止调整 200ms 后才真正重建画布 */
    const handleResize = (): void => {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(resizeCanvas, 200);
    };

    let lastFrameTime = performance.now();

    /**
     * 动画主循环。
     * dt 归一化为「60fps 帧单位」：所有速度参数保持 px/帧、rad/帧 的直观语义，
     * 同时保证不同刷新率显示器上运动速度一致。
     */
    const frame = (now: number): void => {
      animationFrameId = requestAnimationFrame(frame);
      // 后台标签页切回时 dt 可能很大，夹取到 100ms 防止形状瞬间跳变
      const dt = Math.min(now - lastFrameTime, 100);
      lastFrameTime = now;

      if (!reducedMotion && width > 0) {
        const frameUnits = (dt / 1000) * 60; // 当前帧换算为 60fps 下的帧数

        // 焦点减速：目标 0.5 / 1，按 300ms 时间常数平滑逼近
        const calmTarget = optionsRef.current.calm ? 0.5 : 1;
        calmFactorRef.current = lerp(
          calmFactorRef.current,
          calmTarget,
          1 - Math.exp(-dt / 300),
        );

        // 滚动风速：静止衰减回 0.5x，快速滚动最高 1.5x
        windRef.current.velocity *= Math.exp(-dt / 250);
        const windFactor = optionsRef.current.scrollWind
          ? clamp(0.5 + windRef.current.velocity / 30, 0.5, 1.5)
          : 1;

        // 移动端：周期 ×1.5 即速度 ×2/3
        const mobileSpeed =
          optionsRef.current.adaptive && mobileRef.current ? 1 / 1.5 : 1;

        const speedFactor =
          optionsRef.current.speed *
          calmFactorRef.current *
          windFactor *
          mobileSpeed *
          frameUnits;

        for (const shape of shapesRef.current) {
          // 相位推进（正弦波摆动）
          shape.phase += shape.frequency * frameUnits;
          // 水平匀速推进；x 为归一化坐标，除以宽度得到归一化速度
          shape.x += (shape.speed * shape.direction * speedFactor) / width;

          // 边缘回绕：越出边界后从另一侧进入，实现无限循环穿行
          const halfBuffer = shape.size / width; // 半宽缓冲，形状完全出界后再回绕
          if (shape.x > 1 + halfBuffer) {
            shape.x -= 1 + halfBuffer * 2;
          } else if (shape.x < -halfBuffer) {
            shape.x += 1 + halfBuffer * 2;
          }
        }
      }

      // 主题切换：逐通道向目标颜色插值，约 400ms 完成平滑过渡
      const resolved = resolveTheme(optionsRef.current.theme);
      const target = THEME_COLORS[resolved];
      const blend = Math.min(1, dt / 400);
      const palette = paletteRef.current;
      for (let channel = 0; channel < 3; channel++) {
        palette.background[channel] = lerp(
          palette.background[channel],
          target.background[channel],
          blend,
        );
        palette.stroke[channel] = lerp(
          palette.stroke[channel],
          target.stroke[channel],
          blend,
        );
      }
      palette.strokeAlpha = lerp(palette.strokeAlpha, target.strokeAlpha, blend);
      palette.fillAlpha = lerp(palette.fillAlpha, target.fillAlpha, blend);

      drawFrame();
    };

    /** 系统减弱动效偏好变化时，启动 / 停止动画循环 */
    const handleMotionChange = (event: MediaQueryListEvent): void => {
      reducedMotion = event.matches;
      if (reducedMotion) {
        if (supportsRaf) cancelAnimationFrame(animationFrameId);
        drawFrame();
      } else if (supportsRaf) {
        lastFrameTime = performance.now();
        animationFrameId = requestAnimationFrame(frame);
      }
    };

    // "auto" 主题：监听 html.dark 类变化。无动画循环（减弱动效/无 rAF）时
    // 直接快照目标调色板并重绘一帧，保证静态画面也能跟随主题。
    const themeObserver =
      typeof MutationObserver === "function"
        ? new MutationObserver(() => {
            autoDarkRef.current = isDarkDocument();
            if (reducedMotion || !supportsRaf) {
              applyThemeColors(
                paletteRef.current,
                THEME_COLORS[resolveTheme(optionsRef.current.theme)],
              );
              drawFrame();
            }
          })
        : null;
    themeObserver?.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });

    // 初始化尺寸并启动
    resizeCanvas();
    if (supportsRaf && !reducedMotion) {
      lastFrameTime = performance.now();
      animationFrameId = requestAnimationFrame(frame);
    }
    window.addEventListener("resize", handleResize);
    motionQuery?.addEventListener("change", handleMotionChange);

    // 卸载清理：取消动画帧、解绑监听、断开观察器、清掉防抖定时器，防止内存泄漏
    return () => {
      if (supportsRaf) cancelAnimationFrame(animationFrameId);
      themeObserver?.disconnect();
      window.removeEventListener("resize", handleResize);
      motionQuery?.removeEventListener("change", handleMotionChange);
      window.clearTimeout(resizeTimer);
    };
  }, [canvasRef]);
}
