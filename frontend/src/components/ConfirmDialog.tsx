import type { ReactNode } from "react";

import type { AsyncStatus } from "../hooks/useAsyncAction";
import { AsyncButton } from "./AsyncButton";
import { Modal, type ModalIntent } from "./Modal";

export function ConfirmDialog({
  open,
  title,
  message,
  intent = "danger",
  confirmLabel = "确认",
  cancelLabel = "取消",
  busy = false,
  status,
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
  status?: AsyncStatus;
  onConfirm: () => void;
  onCancel: () => void;
  children?: ReactNode;
}) {
  return (
    <Modal
      open={open}
      onClose={busy || status === "pending" ? () => undefined : onCancel}
      title={title}
      intent={intent}
      footer={
        <>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onCancel}
            disabled={busy || status === "pending"}
          >
            {cancelLabel}
          </button>
          <AsyncButton
            type="button"
            status={status ?? (busy ? "pending" : "idle")}
            className={`btn ${
              intent === "danger" ? "btn-danger" : "btn-primary"
            }`}
            onClick={onConfirm}
            loadingLabel="处理中…"
          >
            {confirmLabel}
          </AsyncButton>
        </>
      }
    >
      {message && <div className="text-foreground">{message}</div>}
      {children}
    </Modal>
  );
}
