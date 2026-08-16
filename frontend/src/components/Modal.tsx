import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { StatusIcon, type StatusType } from "./bits/StatusIcon";

export type ModalIntent = "info" | "success" | "warning" | "danger";

const INTENT_ICON: Record<ModalIntent, StatusType> = {
  info: "info",
  success: "success",
  warning: "warning",
  danger: "error",
};

const EXIT_MS = 190;

export function Modal({
  open,
  onClose,
  title,
  intent = "info",
  children,
  footer,
  maxWidth = "max-w-md",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  intent?: ModalIntent;
  children: ReactNode;
  footer?: ReactNode;
  maxWidth?: string;
}) {
  const [render, setRender] = useState(open);
  const [leaving, setLeaving] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (open) {
      setRender(true);
      setLeaving(false);
      previousFocus.current = document.activeElement as HTMLElement | null;
      document.body.style.overflow = "hidden";
    } else if (render) {
      setLeaving(true);
      const timer = setTimeout(() => {
        setRender(false);
        document.body.style.overflow = "";
        previousFocus.current?.focus?.();
      }, EXIT_MS);
      return () => clearTimeout(timer);
    }
  }, [open, render]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
      if (event.key !== "Tab" || !panelRef.current) return;
      const focusables = Array.from(
        panelRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((el) => !el.hasAttribute("disabled"));
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      const inside = active !== null && panelRef.current.contains(active);
      if (event.shiftKey) {
        if (!inside || active === first) {
          event.preventDefault();
          last.focus();
        }
      } else if (!inside || active === last) {
        event.preventDefault();
        first.focus();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  useEffect(() => {
    if (open && render) {
      // 若子节点自带 autoFocus（如重置密码输入框），保留其焦点，不抢焦点
      if (!panelRef.current?.querySelector("[autofocus]")) {
        panelRef.current?.focus();
      }
    }
  }, [open, render]);

  if (!render) return null;

  return createPortal(
    <div
      className={`modal-backdrop ${
        leaving ? "modal-backdrop-out" : "modal-backdrop-in"
      }`}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={`modal-panel modal-${intent} ${maxWidth} ${
          leaving ? "modal-panel-out" : "modal-panel-in"
        }`}
      >
        <div className="modal-accent" />
        <button
          type="button"
          aria-label="关闭弹窗"
          onClick={onClose}
          className="modal-close"
        >
          ×
        </button>
        <div className="px-5 pb-5 pt-5 sm:px-6 sm:pb-6 sm:pt-6">
          <div className="flex items-center gap-3 pr-6">
            <span className="modal-icon">
              <StatusIcon
                type={INTENT_ICON[intent]}
                className="h-5 w-5"
              />
            </span>
            <h3 className="text-base font-semibold text-foreground sm:text-lg">
              {title}
            </h3>
          </div>
          <div className="modal-body">{children}</div>
        </div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}
