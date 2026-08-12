import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { APP_NAME } from "../lib/brand";
import { ShinyText } from "./bits/ShinyText";
import { Brand } from "./Brand";
import { ThemeToggle } from "./ThemeToggle";

export function AppHeader({
  title,
  actions,
}: {
  title: string;
  actions?: ReactNode;
}) {
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-surface/85 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-5xl items-center gap-3 px-4 sm:px-6">
        <Link
          to="/"
          className="flex shrink-0 items-center gap-2.5 rounded-lg"
          aria-label={`${APP_NAME} 首页`}
        >
          <Brand className="h-8 w-8" />
          <ShinyText
            text={APP_NAME}
            className="text-[15px] font-semibold tracking-tight text-foreground"
            duration={6}
          />
        </Link>
        <span className="hidden truncate text-sm text-muted sm:inline">{title}</span>
        <div className="ml-auto flex items-center gap-2">{actions}</div>
        <ThemeToggle />
      </div>
    </header>
  );
}
