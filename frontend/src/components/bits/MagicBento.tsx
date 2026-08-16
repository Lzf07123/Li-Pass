import { useCallback, useEffect, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { gsap } from "gsap";
import { Link } from "react-router-dom";

import { useTheme } from "../../hooks/useTheme";
import "./MagicBento.css";

const DEFAULT_PARTICLE_COUNT = 12;
const DEFAULT_SPOTLIGHT_RADIUS = 300;
const DEFAULT_GLOW_LIGHT = "47, 127, 116";
const DEFAULT_GLOW_DARK = "127, 212, 198";
const MOBILE_BREAKPOINT = 768;

export type MagicBentoItem = {
  label: string;
  /** 数值/主文案：可以是字符串或任意节点（如 CountUp） */
  title: ReactNode;
  description: string;
  /** 数值/主文案加粗放大（适合统计数字） */
  emphasize?: boolean;
  /** 标签前的图标（SVG 节点） */
  icon?: ReactNode;
  /** 卡片底部的扩展内容（如迷你趋势图、进度条） */
  footer?: ReactNode;
  /** 内部路由地址：传入后整卡渲染为可点击链接 */
  href?: string;
  /** 卡片级强调色：rgb 为辉光/粒子用的 RGB 三元组，hex 为标签/图标文字色 */
  accent?: { rgb: string; hex: string };
};

export type MagicBentoProps = {
  items: MagicBentoItem[];
  textAutoHide?: boolean;
  enableStars?: boolean;
  enableSpotlight?: boolean;
  enableBorderGlow?: boolean;
  disableAnimations?: boolean;
  spotlightRadius?: number;
  particleCount?: number;
  enableTilt?: boolean;
  glowColor?: string;
  clickEffect?: boolean;
  enableMagnetism?: boolean;
  className?: string;
  /** 紧凑模式：等宽 3 列、降低卡片高度，适合嵌入页面顶部概览区 */
  compact?: boolean;
};

function createParticleElement(
  x: number,
  y: number,
  color: string,
): HTMLDivElement {
  const el = document.createElement("div");
  el.className = "particle";
  el.style.cssText = `
    position: absolute;
    width: 4px;
    height: 4px;
    border-radius: 50%;
    background: rgba(${color}, 1);
    box-shadow: 0 0 6px rgba(${color}, 0.6);
    pointer-events: none;
    z-index: 100;
    left: ${x}px;
    top: ${y}px;
  `;
  return el;
}

function calculateSpotlightValues(radius: number) {
  return { proximity: radius * 0.5, fadeDistance: radius * 0.75 };
}

function updateCardGlowProperties(
  card: HTMLElement,
  mouseX: number,
  mouseY: number,
  glow: number,
  radius: number,
) {
  const rect = card.getBoundingClientRect();
  const relativeX = ((mouseX - rect.left) / rect.width) * 100;
  const relativeY = ((mouseY - rect.top) / rect.height) * 100;

  card.style.setProperty("--glow-x", `${relativeX}%`);
  card.style.setProperty("--glow-y", `${relativeY}%`);
  card.style.setProperty("--glow-intensity", glow.toString());
  card.style.setProperty("--glow-radius", `${radius}px`);
}

type ParticleCardProps = {
  children: ReactNode;
  className?: string;
  disableAnimations?: boolean;
  style?: CSSProperties;
  particleCount?: number;
  glowColor?: string;
  enableTilt?: boolean;
  clickEffect?: boolean;
  enableMagnetism?: boolean;
  href?: string;
};

function ParticleCard({
  children,
  className = "",
  disableAnimations = false,
  style,
  particleCount = DEFAULT_PARTICLE_COUNT,
  glowColor = DEFAULT_GLOW_LIGHT,
  enableTilt = false,
  clickEffect = false,
  enableMagnetism = false,
  href,
}: ParticleCardProps) {
  const cardRef = useRef<HTMLElement | null>(null);
  const particlesRef = useRef<HTMLDivElement[]>([]);
  const timeoutsRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const isHoveredRef = useRef(false);
  const memoizedParticles = useRef<HTMLDivElement[]>([]);
  const particlesInitialized = useRef(false);
  const magnetismTweenRef = useRef<ReturnType<typeof gsap.to> | null>(null);

  const initializeParticles = useCallback(() => {
    if (particlesInitialized.current || !cardRef.current) return;

    const { width, height } = cardRef.current.getBoundingClientRect();
    memoizedParticles.current = Array.from({ length: particleCount }, () =>
      createParticleElement(
        Math.random() * width,
        Math.random() * height,
        glowColor,
      ),
    );
    particlesInitialized.current = true;
  }, [particleCount, glowColor]);

  const clearAllParticles = useCallback(() => {
    timeoutsRef.current.forEach(clearTimeout);
    timeoutsRef.current = [];
    magnetismTweenRef.current?.kill();

    particlesRef.current.forEach((particle) => {
      gsap.to(particle, {
        scale: 0,
        opacity: 0,
        duration: 0.3,
        ease: "back.in(1.7)",
        onComplete: () => {
          particle.parentNode?.removeChild(particle);
        },
      });
    });
    particlesRef.current = [];
  }, []);

  const animateParticles = useCallback(() => {
    if (!cardRef.current || !isHoveredRef.current) return;

    if (!particlesInitialized.current) {
      initializeParticles();
    }

    memoizedParticles.current.forEach((particle, index) => {
      const timeoutId = setTimeout(() => {
        if (!isHoveredRef.current || !cardRef.current) return;

        const clone = particle.cloneNode(true) as HTMLDivElement;
        cardRef.current.appendChild(clone);
        particlesRef.current.push(clone);

        gsap.fromTo(
          clone,
          { scale: 0, opacity: 0 },
          { scale: 1, opacity: 1, duration: 0.3, ease: "back.out(1.7)" },
        );

        gsap.to(clone, {
          x: (Math.random() - 0.5) * 100,
          y: (Math.random() - 0.5) * 100,
          rotation: Math.random() * 360,
          duration: 2 + Math.random() * 2,
          ease: "none",
          repeat: -1,
          yoyo: true,
        });

        gsap.to(clone, {
          opacity: 0.3,
          duration: 1.5,
          ease: "power2.inOut",
          repeat: -1,
          yoyo: true,
        });
      }, index * 100);

      timeoutsRef.current.push(timeoutId);
    });
  }, [initializeParticles]);

  useEffect(() => {
    if (disableAnimations || !cardRef.current) return;

    const element = cardRef.current;

    const handleMouseEnter = () => {
      isHoveredRef.current = true;
      animateParticles();

      if (enableTilt) {
        gsap.to(element, {
          rotateX: 5,
          rotateY: 5,
          duration: 0.3,
          ease: "power2.out",
          transformPerspective: 1000,
        });
      }
    };

    const handleMouseLeave = () => {
      isHoveredRef.current = false;
      clearAllParticles();

      if (enableTilt) {
        gsap.to(element, {
          rotateX: 0,
          rotateY: 0,
          duration: 0.3,
          ease: "power2.out",
        });
      }

      if (enableMagnetism) {
        gsap.to(element, { x: 0, y: 0, duration: 0.3, ease: "power2.out" });
      }
    };

    const handleMouseMove = (event: MouseEvent) => {
      if (!enableTilt && !enableMagnetism) return;

      const rect = element.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;

      if (enableTilt) {
        const rotateX = ((y - centerY) / centerY) * -10;
        const rotateY = ((x - centerX) / centerX) * 10;
        gsap.to(element, {
          rotateX,
          rotateY,
          duration: 0.1,
          ease: "power2.out",
          transformPerspective: 1000,
        });
      }

      if (enableMagnetism) {
        const magnetX = (x - centerX) * 0.05;
        const magnetY = (y - centerY) * 0.05;
        magnetismTweenRef.current = gsap.to(element, {
          x: magnetX,
          y: magnetY,
          duration: 0.3,
          ease: "power2.out",
        });
      }
    };

    const handleClick = (event: MouseEvent) => {
      if (!clickEffect) return;

      const rect = element.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const maxDistance = Math.max(
        Math.hypot(x, y),
        Math.hypot(x - rect.width, y),
        Math.hypot(x, y - rect.height),
        Math.hypot(x - rect.width, y - rect.height),
      );

      const ripple = document.createElement("div");
      ripple.style.cssText = `
        position: absolute;
        width: ${maxDistance * 2}px;
        height: ${maxDistance * 2}px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(${glowColor}, 0.4) 0%, rgba(${glowColor}, 0.2) 30%, transparent 70%);
        left: ${x - maxDistance}px;
        top: ${y - maxDistance}px;
        pointer-events: none;
        z-index: 1000;
      `;
      element.appendChild(ripple);

      gsap.fromTo(
        ripple,
        { scale: 0, opacity: 1 },
        {
          scale: 1,
          opacity: 0,
          duration: 0.8,
          ease: "power2.out",
          onComplete: () => ripple.remove(),
        },
      );
    };

    element.addEventListener("mouseenter", handleMouseEnter);
    element.addEventListener("mouseleave", handleMouseLeave);
    element.addEventListener("mousemove", handleMouseMove);
    element.addEventListener("click", handleClick);

    return () => {
      isHoveredRef.current = false;
      element.removeEventListener("mouseenter", handleMouseEnter);
      element.removeEventListener("mouseleave", handleMouseLeave);
      element.removeEventListener("mousemove", handleMouseMove);
      element.removeEventListener("click", handleClick);
      clearAllParticles();
    };
  }, [
    animateParticles,
    clearAllParticles,
    disableAnimations,
    enableTilt,
    enableMagnetism,
    clickEffect,
    glowColor,
  ]);

  const cardClassName = `${className} particle-container`.trim();
  const cardStyle = {
    ...style,
    position: "relative",
    overflow: "hidden",
  } as CSSProperties;
  const refCallback = (node: HTMLElement | null) => {
    cardRef.current = node;
  };

  if (href) {
    return (
      <Link
        to={href}
        ref={refCallback}
        className={cardClassName}
        style={cardStyle}
      >
        {children}
      </Link>
    );
  }

  return (
    <div ref={refCallback} className={cardClassName} style={cardStyle}>
      {children}
    </div>
  );
}

type GlobalSpotlightProps = {
  gridRef: React.RefObject<HTMLDivElement | null>;
  disableAnimations?: boolean;
  enabled?: boolean;
  spotlightRadius?: number;
  glowColor?: string;
};

function GlobalSpotlight({
  gridRef,
  disableAnimations = false,
  enabled = true,
  spotlightRadius = DEFAULT_SPOTLIGHT_RADIUS,
  glowColor = DEFAULT_GLOW_LIGHT,
}: GlobalSpotlightProps) {
  const spotlightRef = useRef<HTMLDivElement | null>(null);
  const isInsideSection = useRef(false);

  useEffect(() => {
    if (disableAnimations || !gridRef?.current || !enabled) return;

    const spotlight = document.createElement("div");
    spotlight.className = "global-spotlight";
    spotlight.style.cssText = `
      position: fixed;
      width: 800px;
      height: 800px;
      border-radius: 50%;
      pointer-events: none;
      background: radial-gradient(circle,
        rgba(${glowColor}, 0.15) 0%,
        rgba(${glowColor}, 0.08) 15%,
        rgba(${glowColor}, 0.04) 25%,
        rgba(${glowColor}, 0.02) 40%,
        rgba(${glowColor}, 0.01) 65%,
        transparent 70%
      );
      z-index: 200;
      opacity: 0;
      transform: translate(-50%, -50%);
      mix-blend-mode: screen;
    `;
    document.body.appendChild(spotlight);
    spotlightRef.current = spotlight;

    const handleMouseMove = (event: MouseEvent) => {
      if (!spotlightRef.current || !gridRef.current) return;

      const section = gridRef.current.closest(".bento-section");
      const rect = section?.getBoundingClientRect();
      const mouseInside =
        !!rect &&
        event.clientX >= rect.left &&
        event.clientX <= rect.right &&
        event.clientY >= rect.top &&
        event.clientY <= rect.bottom;

      isInsideSection.current = mouseInside;
      const cards = gridRef.current.querySelectorAll<HTMLElement>(
        ".magic-bento-card",
      );

      if (!mouseInside) {
        gsap.to(spotlightRef.current, {
          opacity: 0,
          duration: 0.3,
          ease: "power2.out",
        });
        cards.forEach((card) => {
          card.style.setProperty("--glow-intensity", "0");
        });
        return;
      }

      const { proximity, fadeDistance } =
        calculateSpotlightValues(spotlightRadius);
      let minDistance = Infinity;

      cards.forEach((card) => {
        const cardRect = card.getBoundingClientRect();
        const centerX = cardRect.left + cardRect.width / 2;
        const centerY = cardRect.top + cardRect.height / 2;
        const distance =
          Math.hypot(event.clientX - centerX, event.clientY - centerY) -
          Math.max(cardRect.width, cardRect.height) / 2;
        const effectiveDistance = Math.max(0, distance);
        minDistance = Math.min(minDistance, effectiveDistance);

        let glowIntensity = 0;
        if (effectiveDistance <= proximity) {
          glowIntensity = 1;
        } else if (effectiveDistance <= fadeDistance) {
          glowIntensity =
            (fadeDistance - effectiveDistance) / (fadeDistance - proximity);
        }

        updateCardGlowProperties(
          card,
          event.clientX,
          event.clientY,
          glowIntensity,
          spotlightRadius,
        );
      });

      gsap.to(spotlightRef.current, {
        left: event.clientX,
        top: event.clientY,
        duration: 0.1,
        ease: "power2.out",
      });

      const targetOpacity =
        minDistance <= proximity
          ? 0.8
          : minDistance <= fadeDistance
            ? ((fadeDistance - minDistance) / (fadeDistance - proximity)) * 0.8
            : 0;

      gsap.to(spotlightRef.current, {
        opacity: targetOpacity,
        duration: targetOpacity > 0 ? 0.2 : 0.5,
        ease: "power2.out",
      });
    };

    const handleMouseLeave = () => {
      isInsideSection.current = false;
      gridRef.current
        ?.querySelectorAll<HTMLElement>(".magic-bento-card")
        .forEach((card) => {
          card.style.setProperty("--glow-intensity", "0");
        });
      if (spotlightRef.current) {
        gsap.to(spotlightRef.current, {
          opacity: 0,
          duration: 0.3,
          ease: "power2.out",
        });
      }
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseleave", handleMouseLeave);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseleave", handleMouseLeave);
      spotlightRef.current?.parentNode?.removeChild(spotlightRef.current);
    };
  }, [gridRef, disableAnimations, enabled, spotlightRadius, glowColor]);

  return null;
}

function useMobileDetection() {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => window.innerWidth <= MOBILE_BREAKPOINT;
    const onResize = () => setIsMobile(checkMobile());
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  return isMobile;
}

/**
 * React Bits MagicBento 的 TypeScript 移植版：数据驱动的 Bento 卡片网格，
 * 支持光标跟随聚光、粒子星点、边框辉光、3D 倾斜与磁性吸附。
 * 默认光色跟随明暗主题的品牌主色，可用 glowColor 覆盖（RGB 三元组字符串）。
 */
export function MagicBento({
  items,
  textAutoHide = true,
  enableStars = true,
  enableSpotlight = true,
  enableBorderGlow = true,
  disableAnimations = false,
  spotlightRadius = DEFAULT_SPOTLIGHT_RADIUS,
  particleCount = DEFAULT_PARTICLE_COUNT,
  enableTilt = false,
  glowColor,
  clickEffect = true,
  enableMagnetism = true,
  className = "",
  compact = false,
}: MagicBentoProps) {
  const gridRef = useRef<HTMLDivElement | null>(null);
  const isMobile = useMobileDetection();
  const [theme] = useTheme();

  const reducedMotion =
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const shouldDisableAnimations =
    disableAnimations || isMobile || reducedMotion;
  const resolvedGlowColor =
    glowColor ?? (theme === "dark" ? DEFAULT_GLOW_DARK : DEFAULT_GLOW_LIGHT);

  return (
    <div
      className={`magic-bento${compact ? " magic-bento--compact" : ""} ${className}`.trim()}
    >
      {enableSpotlight && (
        <GlobalSpotlight
          gridRef={gridRef}
          disableAnimations={shouldDisableAnimations}
          enabled={enableSpotlight}
          spotlightRadius={spotlightRadius}
          glowColor={resolvedGlowColor}
        />
      )}

      <div className="card-grid bento-section" ref={gridRef}>
        {items.map((card, index) => {
          const baseClassName = `magic-bento-card ${
            textAutoHide ? "magic-bento-card--text-autohide" : ""
          } ${enableBorderGlow ? "magic-bento-card--border-glow" : ""}`.trim();
          const cardAccent = card.accent;
          const cardGlow = cardAccent?.rgb ?? resolvedGlowColor;
          const cardStyle = {
            "--glow-color": cardGlow,
            ...(cardAccent?.hex ? { "--bento-label": cardAccent.hex } : {}),
          } as CSSProperties;

          const content = (
            <>
              <div className="magic-bento-card__header">
                {card.icon && (
                  <span className="magic-bento-card__icon" aria-hidden="true">
                    {card.icon}
                  </span>
                )}
                <div className="magic-bento-card__label">{card.label}</div>
              </div>
              <div className="magic-bento-card__content">
                <h2
                  className={`magic-bento-card__title${
                    card.emphasize ? " magic-bento-card__title--emphasize" : ""
                  }`}
                >
                  {card.title}
                </h2>
                <p className="magic-bento-card__description">
                  {card.description}
                </p>
                {card.footer && (
                  <div className="magic-bento-card__footer">{card.footer}</div>
                )}
              </div>
            </>
          );

          if (enableStars) {
            return (
              <ParticleCard
                key={index}
                className={baseClassName}
                style={cardStyle}
                disableAnimations={shouldDisableAnimations}
                particleCount={particleCount}
                glowColor={cardGlow}
                enableTilt={enableTilt}
                clickEffect={clickEffect}
                enableMagnetism={enableMagnetism}
                href={card.href}
              >
                {content}
              </ParticleCard>
            );
          }

          const refCallback = (el: HTMLElement | null) => {
            if (!el) return;

            const handleMouseMove = (event: MouseEvent) => {
              if (shouldDisableAnimations) return;

              const rect = el.getBoundingClientRect();
              const x = event.clientX - rect.left;
              const y = event.clientY - rect.top;
              const centerX = rect.width / 2;
              const centerY = rect.height / 2;

              if (enableTilt) {
                const rotateX = ((y - centerY) / centerY) * -10;
                const rotateY = ((x - centerX) / centerX) * 10;
                gsap.to(el, {
                  rotateX,
                  rotateY,
                  duration: 0.1,
                  ease: "power2.out",
                  transformPerspective: 1000,
                });
              }

              if (enableMagnetism) {
                const magnetX = (x - centerX) * 0.05;
                const magnetY = (y - centerY) * 0.05;
                gsap.to(el, {
                  x: magnetX,
                  y: magnetY,
                  duration: 0.3,
                  ease: "power2.out",
                });
              }
            };

            const handleMouseLeave = () => {
              if (shouldDisableAnimations) return;

              if (enableTilt) {
                gsap.to(el, {
                  rotateX: 0,
                  rotateY: 0,
                  duration: 0.3,
                  ease: "power2.out",
                });
              }
              if (enableMagnetism) {
                gsap.to(el, {
                  x: 0,
                  y: 0,
                  duration: 0.3,
                  ease: "power2.out",
                });
              }
            };

            el.addEventListener("mousemove", handleMouseMove);
            el.addEventListener("mouseleave", handleMouseLeave);

            return () => {
              el.removeEventListener("mousemove", handleMouseMove);
              el.removeEventListener("mouseleave", handleMouseLeave);
            };
          };

          if (card.href) {
            return (
              <Link
                key={index}
                to={card.href}
                ref={refCallback}
                className={baseClassName}
                style={cardStyle}
              >
                {content}
              </Link>
            );
          }

          return (
            <div
              key={index}
              ref={refCallback}
              className={baseClassName}
              style={cardStyle}
            >
              {content}
            </div>
          );
        })}
      </div>
    </div>
  );
}
