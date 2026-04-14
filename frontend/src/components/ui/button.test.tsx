import { createRef } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import Button from "./button";

describe("Button", () => {
  it("renders with default props", () => {
    render(<Button>Click me</Button>);
    const btn = screen.getByRole("button", { name: /click me/i });
    expect(btn).toBeInTheDocument();
    expect(btn).not.toBeDisabled();
  });

  it("renders primary variant classes", () => {
    render(<Button variant="primary">Primary</Button>);
    const btn = screen.getByRole("button", { name: /primary/i });
    expect(btn.className).toContain("bg-blue-600");
  });

  it("renders secondary variant classes", () => {
    render(<Button variant="secondary">Secondary</Button>);
    const btn = screen.getByRole("button", { name: /secondary/i });
    expect(btn.className).toContain("bg-white");
    expect(btn.className).toContain("border-gray-300");
  });

  it("renders danger variant classes", () => {
    render(<Button variant="danger">Danger</Button>);
    const btn = screen.getByRole("button", { name: /danger/i });
    expect(btn.className).toContain("bg-red-600");
  });

  it("renders ghost variant classes", () => {
    render(<Button variant="ghost">Ghost</Button>);
    const btn = screen.getByRole("button", { name: /ghost/i });
    expect(btn.className).toContain("hover:bg-gray-100");
  });

  it("renders sm size classes", () => {
    render(<Button size="sm">Small</Button>);
    const btn = screen.getByRole("button", { name: /small/i });
    expect(btn.className).toContain("px-3");
    expect(btn.className).toContain("text-xs");
  });

  it("renders md size classes (default)", () => {
    render(<Button>Medium</Button>);
    const btn = screen.getByRole("button", { name: /medium/i });
    expect(btn.className).toContain("px-4");
    expect(btn.className).toContain("text-sm");
  });

  it("renders lg size classes", () => {
    render(<Button size="lg">Large</Button>);
    const btn = screen.getByRole("button", { name: /large/i });
    expect(btn.className).toContain("px-5");
    expect(btn.className).toContain("text-base");
  });

  it("shows loading spinner when loading is true", () => {
    render(<Button loading>Loading</Button>);
    const svg = screen.getByRole("button").querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg?.classList.contains("animate-spin")).toBe(true);
  });

  it("is disabled when disabled prop is true", () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByRole("button", { name: /disabled/i })).toBeDisabled();
  });

  it("is disabled when loading is true", () => {
    render(<Button loading>Submit</Button>);
    expect(screen.getByRole("button", { name: /submit/i })).toBeDisabled();
  });

  it("applies opacity-50 and cursor-not-allowed when disabled", () => {
    render(<Button disabled>Disabled</Button>);
    const btn = screen.getByRole("button", { name: /disabled/i });
    expect(btn.className).toContain("opacity-50");
    expect(btn.className).toContain("cursor-not-allowed");
  });

  it("passes custom className", () => {
    render(<Button className="my-custom-class">Custom</Button>);
    const btn = screen.getByRole("button", { name: /custom/i });
    expect(btn.className).toContain("my-custom-class");
  });

  it("forwards ref to the button element", () => {
    const ref = createRef<HTMLButtonElement>();
    render(<Button ref={ref}>Ref</Button>);
    expect(ref.current).toBeInstanceOf(HTMLButtonElement);
    expect(ref.current?.textContent).toContain("Ref");
  });

  it("calls onClick handler when clicked", async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Clickable</Button>);
    await user.click(screen.getByRole("button", { name: /clickable/i }));
    expect(handleClick).toHaveBeenCalledOnce();
  });

  it("does not call onClick when disabled", async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();
    render(
      <Button disabled onClick={handleClick}>
        No click
      </Button>,
    );
    await user.click(screen.getByRole("button", { name: /no click/i }));
    expect(handleClick).not.toHaveBeenCalled();
  });
});
