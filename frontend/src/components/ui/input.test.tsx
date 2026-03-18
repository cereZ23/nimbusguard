import { createRef } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import Input from "./input";

describe("Input", () => {
  it("renders with a label", () => {
    render(<Input label="Email" />);
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
  });

  it("renders without a label", () => {
    render(<Input placeholder="type here" />);
    expect(screen.getByPlaceholderText("type here")).toBeInTheDocument();
    expect(screen.queryByRole("label")).not.toBeInTheDocument();
  });

  it("shows error message when error prop is provided", () => {
    render(<Input error="This field is required" />);
    expect(screen.getByText("This field is required")).toBeInTheDocument();
  });

  it("has error styling when error prop is provided", () => {
    render(<Input error="Invalid" />);
    const input = screen.getByRole("textbox");
    expect(input.className).toContain("border-red-500");
  });

  it("has normal styling when no error", () => {
    render(<Input />);
    const input = screen.getByRole("textbox");
    expect(input.className).toContain("border-gray-300");
    expect(input.className).not.toContain("border-red-500");
  });

  it("sets aria-invalid to true when error is present", () => {
    render(<Input error="Bad input" />);
    expect(screen.getByRole("textbox")).toHaveAttribute("aria-invalid", "true");
  });

  it("does not set aria-invalid when no error", () => {
    render(<Input />);
    expect(screen.getByRole("textbox")).not.toHaveAttribute("aria-invalid");
  });

  it("links error message via aria-describedby", () => {
    render(<Input label="Name" error="Required" id="name-input" />);
    const input = screen.getByRole("textbox");
    const describedById = input.getAttribute("aria-describedby");
    expect(describedById).toBe("name-input-error");
    const errorEl = document.getElementById("name-input-error");
    expect(errorEl?.textContent).toBe("Required");
  });

  it("forwards ref to the input element", () => {
    const ref = createRef<HTMLInputElement>();
    render(<Input ref={ref} />);
    expect(ref.current).toBeInstanceOf(HTMLInputElement);
  });

  it("handles onChange events", async () => {
    const user = userEvent.setup();
    const handleChange = vi.fn();
    render(<Input onChange={handleChange} />);
    const input = screen.getByRole("textbox");
    await user.type(input, "hello");
    expect(handleChange).toHaveBeenCalledTimes(5);
  });

  it("applies custom className", () => {
    render(<Input className="extra-class" />);
    const input = screen.getByRole("textbox");
    expect(input.className).toContain("extra-class");
  });

  it("uses external id when provided", () => {
    render(<Input id="my-id" label="Field" />);
    const input = screen.getByRole("textbox");
    expect(input.id).toBe("my-id");
  });
});
