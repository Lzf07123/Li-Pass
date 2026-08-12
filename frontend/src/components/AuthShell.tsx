import type { ReactNode } from "react";

import { Brand } from "./Brand";
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
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4 py-10">
      {/* 装饰性背景光晕 */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <div className="absolute -top-40 left-1/2 h-96 w-[44rem] -translate-x-1/2 rounded-full bg-primary/10 blur-3xl dark:bg-primary/10" />
        <div className="absolute -bottom-32 -right-24 h-80 w-80 rounded-full bg-success/5 blur-3xl" />
        <div className="absolute -left-24 top-1/3 h-64 w-64 rounded-full bg-primary/5 blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        <div className="animate-fade-up mb-8 flex flex-col items-center gap-3 text-center">
          <Brand className="h-12 w-12 drop-shadow-sm" />
          <div>
            <h1 className="text-[22px] font-semibold tracking-tight text-foreground">
              {title}
            </h1>
            {subtitle && <p className="mt-1.5 text-sm text-muted">{subtitle}</p>}
          </div>
        </div>

        <div className="animate-fade-up [animation-delay:70ms]">
          <div className="card p-6 sm:p-8">{children}</div>
        </div>

        <p className="animate-fade-in mt-6 text-center text-xs text-muted [animation-delay:140ms]">
          一次注册，通行所有授权网站
        </p>
      </div>

      <ThemeToggle className="animate-fade-in absolute right-4 top-4 sm:right-6 sm:top-6 [animation-delay:180ms]" />
    </main>
  );
}
