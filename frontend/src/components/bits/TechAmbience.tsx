import type { CSSProperties } from "react";

const DOTS: Array<{
  left: string;
  top: string;
  color: string;
  delay: string;
}> = [
  { left: "14%", top: "18%", color: "var(--portal-accent-ice)", delay: "0s" },
  { left: "84%", top: "16%", color: "var(--portal-accent-lilac)", delay: "2.3s" },
  { left: "9%", top: "70%", color: "var(--portal-accent-aqua)", delay: "4.3s" },
  { left: "78%", top: "72%", color: "var(--portal-accent-sage)", delay: "1.3s" },
  { left: "47%", top: "11%", color: "var(--portal-accent-mint)", delay: "5.7s" },
  { left: "36%", top: "86%", color: "var(--portal-accent-sand)", delay: "7s" },
  { left: "64%", top: "58%", color: "var(--portal-accent-aqua)", delay: "3.3s" },
  { left: "24%", top: "44%", color: "var(--portal-accent-ice)", delay: "8.3s" },
];

/**
 * 科技氛围层：缓移网格 + 周期性扫掠光束 + 呼吸光点。
 * 纯装饰、不拦截交互；soft 模式用于已登录页（用户中心），认证页用默认浓度。
 */
export function TechAmbience({ soft = false }: { soft?: boolean }) {
  return (
    <div
      aria-hidden="true"
      className={`tech-ambience${soft ? " tech-ambience--soft" : ""}`}
    >
      <div className="tech-grid" />
      <div className="tech-beam" />
      <div className="tech-beam tech-beam--violet" />
      <div className="tech-beam tech-beam--sage" />
      {DOTS.map((dot, index) => (
        <span
          key={index}
          className="tech-dot"
          style={
            {
              left: dot.left,
              top: dot.top,
              animationDelay: dot.delay,
              "--tech-dot-color": dot.color,
            } as CSSProperties
          }
        />
      ))}
    </div>
  );
}
