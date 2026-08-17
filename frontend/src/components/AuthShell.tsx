import { useState } from "react";
import type { ReactNode } from "react";

import { APP_NAME, APP_TAGLINE } from "../lib/brand";
import { AuroraBackground } from "./bits/AuroraBackground";
import { BlurText } from "./bits/BlurText";
import { ShinyText } from "./bits/ShinyText";
import { Brand } from "./Brand";
import { FloatingBackground } from "./FloatingBackground";
import { SiteFooter } from "./SiteFooter";
import { ThemeToggle } from "./ThemeToggle";
import { TechAmbience } from "./bits/TechAmbience";

export function AuthShell({
  title,
  subtitle,
  ambientShapeCount = 10,
  children,
}: {
  title: string;
  subtitle?: string;
  /** 背景层漂浮形状数量：认证页默认 10（最丰富），授权确认等信任时刻应调低 */
  ambientShapeCount?: number;
  children: ReactNode;
}) {
  // 表单聚焦时减速：让“环境呼吸”在用户输入时退为背景音，失焦后恢复
  const [focusing, setFocusing] = useState(false);

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-background">
      {/* 环境呼吸层：几何形状无限循环飘动（透明画布，自动跟随明暗主题） */}
      <FloatingBackground
        theme="auto"
        transparent
        calm={focusing}
        shapeCount={ambientShapeCount}
      />
      {/* ReactBits 风格极光背景（位于几何形状之上，作为第二层氛围） */}
      <AuroraBackground />
      {/* 科技氛围层：缓移网格 + 扫掠光束 + 呼吸光点（主界面光效） */}
      <TechAmbience />

      <div className="relative flex flex-1 flex-col items-center justify-center px-4 py-10">
        <div className="w-full max-w-md">
          <div
            className="animate-fade-up-slow mb-8 flex w-full flex-col items-center gap-3 text-center"
            style={{ animationDelay: "0.05s" }}
          >
            <Brand className="brand-halo h-12 w-12" />
            <div>
              <h1>
                <BlurText
                  as="span"
                  text={title}
                  className="justify-center text-[34px] font-bold leading-tight tracking-normal"
                  animateBy="words"
                  direction="top"
                  delay={120}
                  stepDuration={0.35}
                />
              </h1>
              {subtitle && <p className="mt-1.5 text-sm text-muted">{subtitle}</p>}
            </div>
          </div>

          <div
            className="animate-fade-up-slow"
            style={{ animationDelay: "0.18s" }}
            onFocusCapture={() => setFocusing(true)}
            onBlurCapture={(event) => {
              // 焦点仍在卡片内部时不解除减速，避免逐字段聚焦来回切换速度
              const next = event.relatedTarget;
              if (!(next instanceof Node) || !event.currentTarget.contains(next)) {
                setFocusing(false);
              }
            }}
          >
            <div className="card card-halo card-signature p-6 sm:p-8">
              {children}
            </div>
          </div>
        </div>
        <p className="mt-8 text-center text-xs text-muted">
          <ShinyText text={`${APP_NAME} · ${APP_TAGLINE}`} duration={7} />
        </p>
      </div>

      <div
        className="animate-fade-up-slow relative"
        style={{ animationDelay: "0.32s" }}
      >
        <SiteFooter />
      </div>

      <div
        className="animate-fade-up-slow absolute right-4 top-4 sm:right-6 sm:top-6"
        style={{ animationDelay: "0.4s" }}
      >
        <ThemeToggle />
      </div>
    </div>
  );
}
