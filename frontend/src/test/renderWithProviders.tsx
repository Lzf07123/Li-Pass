import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { render } from "@testing-library/react";

import { ToastProvider } from "../components/ToastProvider";

/**
 * 页面组件测试统一入口：自动提供 ToastProvider 与 MemoryRouter，
 * 与 main.tsx 中真实应用的 Provider 层级保持一致。
 */
export function renderWithProviders(
  ui: ReactElement,
  initialEntries: string[] = ["/"]
) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <ToastProvider>{ui}</ToastProvider>
    </MemoryRouter>
  );
}
