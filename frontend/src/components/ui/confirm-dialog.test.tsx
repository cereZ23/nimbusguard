import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ConfirmDialog from "./confirm-dialog";

describe("ConfirmDialog", () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    onConfirm: vi.fn(),
    title: "Confirm Deletion",
    message: "Are you sure you want to delete this item?",
  };

  it("renders title and message when open", () => {
    render(<ConfirmDialog {...defaultProps} />);
    expect(screen.getByText("Confirm Deletion")).toBeInTheDocument();
    expect(
      screen.getByText("Are you sure you want to delete this item?"),
    ).toBeInTheDocument();
  });

  it("does not render when isOpen is false", () => {
    render(<ConfirmDialog {...defaultProps} isOpen={false} />);
    expect(screen.queryByText("Confirm Deletion")).not.toBeInTheDocument();
  });

  it("calls onConfirm when confirm button is clicked", () => {
    const onConfirm = vi.fn();
    render(<ConfirmDialog {...defaultProps} onConfirm={onConfirm} />);
    fireEvent.click(screen.getByRole("button", { name: /delete/i }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("calls onClose when cancel button is clicked", () => {
    const onClose = vi.fn();
    render(<ConfirmDialog {...defaultProps} onClose={onClose} />);
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("shows custom confirmLabel", () => {
    render(<ConfirmDialog {...defaultProps} confirmLabel="Remove" />);
    expect(screen.getByRole("button", { name: /remove/i })).toBeInTheDocument();
  });

  it("shows default confirmLabel as Delete", () => {
    render(<ConfirmDialog {...defaultProps} />);
    expect(screen.getByRole("button", { name: /delete/i })).toBeInTheDocument();
  });

  it("shows loading state on confirm button", () => {
    render(<ConfirmDialog {...defaultProps} loading />);
    const confirmBtn = screen.getByRole("button", { name: /delete/i });
    expect(confirmBtn).toBeDisabled();
    expect(confirmBtn.querySelector("svg")).toBeInTheDocument();
  });

  it("renders cancel and confirm buttons", () => {
    render(<ConfirmDialog {...defaultProps} />);
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /delete/i })).toBeInTheDocument();
  });
});
