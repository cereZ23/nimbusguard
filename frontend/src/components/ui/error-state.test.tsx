import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ErrorState from "./error-state";

describe("ErrorState", () => {
  it("renders default error message", () => {
    render(<ErrorState />);
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("renders custom error message", () => {
    render(<ErrorState message="Failed to load data" />);
    expect(screen.getByText("Failed to load data")).toBeInTheDocument();
  });

  it("shows retry button when onRetry is provided", () => {
    render(<ErrorState onRetry={vi.fn()} />);
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("does not show retry button when onRetry is not provided", () => {
    render(<ErrorState />);
    expect(
      screen.queryByRole("button", { name: /retry/i }),
    ).not.toBeInTheDocument();
  });

  it("calls onRetry when retry button is clicked", () => {
    const onRetry = vi.fn();
    render(<ErrorState onRetry={onRetry} />);
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("applies custom className", () => {
    const { container } = render(<ErrorState className="my-error-class" />);
    const wrapper = container.firstElementChild;
    expect(wrapper?.className).toContain("my-error-class");
  });
});
