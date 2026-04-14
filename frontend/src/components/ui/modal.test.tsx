import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import Modal from "./modal";

describe("Modal", () => {
  it("renders children when isOpen is true", () => {
    render(
      <Modal isOpen onClose={vi.fn()} title="Test Modal">
        <p>Modal content</p>
      </Modal>,
    );
    expect(screen.getByText("Modal content")).toBeInTheDocument();
  });

  it("does not render when isOpen is false", () => {
    render(
      <Modal isOpen={false} onClose={vi.fn()} title="Hidden Modal">
        <p>Hidden content</p>
      </Modal>,
    );
    expect(screen.queryByText("Hidden content")).not.toBeInTheDocument();
  });

  it("shows the title", () => {
    render(
      <Modal isOpen onClose={vi.fn()} title="My Title">
        <p>Content</p>
      </Modal>,
    );
    expect(screen.getByText("My Title")).toBeInTheDocument();
  });

  it("calls onClose when Escape key is pressed", () => {
    const onClose = vi.fn();
    render(
      <Modal isOpen onClose={onClose} title="Escape Test">
        <p>Content</p>
      </Modal>,
    );
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when backdrop is clicked", () => {
    const onClose = vi.fn();
    render(
      <Modal isOpen onClose={onClose} title="Backdrop Test">
        <p>Content</p>
      </Modal>,
    );
    const backdrop = screen.getByRole("dialog");
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("does not call onClose when panel content is clicked", () => {
    const onClose = vi.fn();
    render(
      <Modal isOpen onClose={onClose} title="Panel Click Test">
        <p>Inner content</p>
      </Modal>,
    );
    fireEvent.click(screen.getByText("Inner content"));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("renders close button with accessible label", () => {
    render(
      <Modal isOpen onClose={vi.fn()} title="Close Button Test">
        <p>Content</p>
      </Modal>,
    );
    expect(screen.getByRole("button", { name: /close/i })).toBeInTheDocument();
  });

  it("calls onClose when close button is clicked", () => {
    const onClose = vi.fn();
    render(
      <Modal isOpen onClose={onClose} title="Close Click Test">
        <p>Content</p>
      </Modal>,
    );
    fireEvent.click(screen.getByRole("button", { name: /close/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("renders with default lg size class", () => {
    render(
      <Modal isOpen onClose={vi.fn()} title="Default Size">
        <p>Content</p>
      </Modal>,
    );
    const dialog = screen.getByRole("dialog");
    const panel = dialog.querySelector("[tabindex]");
    expect(panel?.className).toContain("max-w-lg");
  });

  it("renders sm size class when specified", () => {
    render(
      <Modal isOpen onClose={vi.fn()} title="Small Modal" size="sm">
        <p>Content</p>
      </Modal>,
    );
    const dialog = screen.getByRole("dialog");
    const panel = dialog.querySelector("[tabindex]");
    expect(panel?.className).toContain("max-w-sm");
  });

  it("renders xl size class when specified", () => {
    render(
      <Modal isOpen onClose={vi.fn()} title="XL Modal" size="xl">
        <p>Content</p>
      </Modal>,
    );
    const dialog = screen.getByRole("dialog");
    const panel = dialog.querySelector("[tabindex]");
    expect(panel?.className).toContain("max-w-xl");
  });

  it("has aria-modal attribute", () => {
    render(
      <Modal isOpen onClose={vi.fn()} title="Accessible Modal">
        <p>Content</p>
      </Modal>,
    );
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
  });
});
