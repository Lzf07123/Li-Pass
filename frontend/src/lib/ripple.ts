const RIPPLE_CLASS = "btn-ripple";

function createRipple(event: PointerEvent): void {
  const target = event.target as Element | null;
  if (!target) return;
  const btn = target.closest<HTMLElement>(".btn");
  if (!btn) return;
  if (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  ) {
    return;
  }

  const rect = btn.getBoundingClientRect();
  const size = Math.max(rect.width, rect.height) * 2;
  btn.querySelector(`.${RIPPLE_CLASS}`)?.remove();

  const ripple = document.createElement("span");
  ripple.className = RIPPLE_CLASS;
  ripple.style.width = `${size}px`;
  ripple.style.height = `${size}px`;
  ripple.style.left = `${event.clientX - rect.left - size / 2}px`;
  ripple.style.top = `${event.clientY - rect.top - size / 2}px`;
  ripple.addEventListener("animationend", () => ripple.remove(), { once: true });
  btn.appendChild(ripple);
}

let initialized = false;
let handler: ((event: PointerEvent) => void) | null = null;

export function initRipple(): void {
  if (initialized || typeof document === "undefined") return;
  initialized = true;
  handler = createRipple;
  document.addEventListener("pointerdown", handler, { passive: true });
}

/** 仅测试用：移除监听并重置初始化状态。 */
export function resetRippleForTests(): void {
  if (handler && typeof document !== "undefined") {
    document.removeEventListener("pointerdown", handler);
  }
  handler = null;
  initialized = false;
}
