import type { ReactNode } from "react";

import { APP_NAME, APP_TAGLINE } from "../lib/brand";
import { AuroraBackground } from "./bits/AuroraBackground";
import { BlurText } from "./bits/BlurText";
import { ShinyText } from "./bits/ShinyText";
import { Brand } from "./Brand";
import { SiteFooter } from "./SiteFooter";
import { ThemeToggle } from "./ThemeToggle";

export function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <main className="relative flex min-h-screen flex-col overflow-hidden bg-background px-4 py-10">
      {/* ReactBits 风格极光背景 */}
      <AuroraBackground />

      <div className="relative flex flex-1 items-center justify-center">
        <div className="w-full max-w-md">
          <div
            className="animate-fade-up-slow mb-8 flex flex-col items-center gap-3 text-center"
            style={{ animationDelay: "0.05s" }}
          >
            <Brand className="h-12 w-12 drop-shadow-sm" />
            <div>
              <BlurText
                text={title}
                className="text-[22px] font-semibold tracking-tight text-foreground"
              />
              {subtitle && <p className="mt-1.5 text-sm text-muted">{subtitle}</p>}
            </div>
          </div>

          <div className="animate-fade-up-slow" style={{ animationDelay: "0.18s" }}>
            <div className="card p-6 sm:p-8">{children}</div>
          </div>
        </div>
      </div>

      <div
        className="animate-fade-up-slow relative text-center"
        style={{ animationDelay: "0.32s" }}
      >
        <p className="text-xs text-muted">
          <ShinyText text={`${APP_NAME} · ${APP_TAGLINE}`} duration={7} />
        </p>
        <div className="mt-2">
          <SiteFooter compact />
        </div>
      </div>

      <div
        className="animate-fade-up-slow absolute right-4 top-4 sm:right-6 sm:top-6"
        style={{ animationDelay: "0.4s" }}
      >
        <ThemeToggle />
      </div>
    </main>
  );
}
