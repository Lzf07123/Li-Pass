import type { ElementType } from "react";

const EASE_CSS = "cubic-bezier(0.25, 0.1, 0.25, 1)";

type BlurTextProps = {
  text: string;
  /** 渲染标签，保持语义（默认 h1） */
  as?: ElementType;
  className?: string;
  /** 相邻字/词间隔（毫秒） */
  delay?: number;
  /** 单个字/词动画时长（秒） */
  stepDuration?: number;
  animateBy?: "words" | "letters";
};

/**
 * ReactBits BlurText 思路的轻量版：
 * 按字/词错峰入场，伴随轻微模糊与位移，只动 transform/filter/opacity。
 */
export function BlurText({
  text,
  as: Tag = "h1",
  className = "",
  delay = 50,
  stepDuration = 0.32,
  animateBy = "words",
}: BlurTextProps) {
  const elements =
    animateBy === "words" ? text.split(" ") : Array.from(text);

  return (
    <Tag className={className}>
      {elements.map((segment, index) => (
        // 动画结束后立即释放 will-change，避免每个字长期占用独立合成层。
        <span
          key={`${index}-${segment}`}
          className="inline-block"
          style={{
            animation: `portal-blur-in ${stepDuration}s ${EASE_CSS} both`,
            animationDelay: `${(index * delay) / 1000}s`,
            willChange: "transform, filter, opacity",
          }}
          onAnimationEnd={(event) => {
            event.currentTarget.style.willChange = "auto";
          }}
        >
          {segment === " " ? "\u00A0" : segment}
          {animateBy === "words" && index < elements.length - 1
            ? "\u00A0"
            : ""}
        </span>
      ))}
    </Tag>
  );
}
