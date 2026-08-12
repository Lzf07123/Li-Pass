import type { ReactNode } from "react";

import { Modal, type ModalIntent } from "./Modal";

export function ConfirmDialog({
  open,
  title,
  message,
  intent = "danger",
  confirmLabel = "确认",
  cancelLabel = "取消",
  busy = false,
  onConfirm,
  onCancel,
  children,
}: {
  open: boolean;
  title: string;
  message?: ReactNode;
  intent?: ModalIntent;
  confirmLabel?: string;
  cancelLabel?: string;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  children?: ReactNode;
}) {
  return (
    <Modal
      open={open}
      onClose={busy ? () => undefined : onCancel}
      title={title}
      intent={intent}
      footer={
        <>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onCancel}
            disabled={busy}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            className={`btn ${intent === "danger" ? "btn-danger" : "btn-primary"}`}
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? "处理中…" : confirmLabel}
          </button>
        </>
      }
    >
      {message && <div className="text-foreground">{message}</div>}
      {children}
    </Modal>
  );
}
