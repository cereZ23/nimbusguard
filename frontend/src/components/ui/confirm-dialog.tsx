"use client";

import Modal from "./modal";
import Button from "./button";

type ConfirmVariant = "danger" | "primary";

interface ConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmLabel?: string;
  variant?: ConfirmVariant;
  loading?: boolean;
}

export default function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = "Delete",
  variant = "danger",
  loading = false,
}: ConfirmDialogProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title} size="sm">
      <p className="text-sm text-gray-500 dark:text-gray-400">{message}</p>

      <div className="mt-6 flex justify-end gap-3">
        <Button variant="secondary" size="md" onClick={onClose}>
          Cancel
        </Button>
        <Button
          variant={variant}
          size="md"
          onClick={onConfirm}
          loading={loading}
        >
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}
