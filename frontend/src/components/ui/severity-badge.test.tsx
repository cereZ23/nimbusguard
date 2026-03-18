import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import SeverityBadge from "./severity-badge";

describe("SeverityBadge", () => {
  it("renders the severity text for high", () => {
    render(<SeverityBadge severity="high" />);
    expect(screen.getByText("high")).toBeInTheDocument();
  });

  it("renders the severity text for medium", () => {
    render(<SeverityBadge severity="medium" />);
    expect(screen.getByText("medium")).toBeInTheDocument();
  });

  it("renders the severity text for low", () => {
    render(<SeverityBadge severity="low" />);
    expect(screen.getByText("low")).toBeInTheDocument();
  });

  it("has correct color classes for high severity", () => {
    render(<SeverityBadge severity="high" />);
    const badge = screen.getByText("high");
    expect(badge.className).toContain("bg-red-50");
    expect(badge.className).toContain("text-red-700");
  });

  it("has correct color classes for medium severity", () => {
    render(<SeverityBadge severity="medium" />);
    const badge = screen.getByText("medium");
    expect(badge.className).toContain("bg-amber-50");
    expect(badge.className).toContain("text-amber-700");
  });

  it("has correct color classes for low severity", () => {
    render(<SeverityBadge severity="low" />);
    const badge = screen.getByText("low");
    expect(badge.className).toContain("bg-blue-50");
    expect(badge.className).toContain("text-blue-700");
  });

  it("has correct dot color for high severity", () => {
    render(<SeverityBadge severity="high" />);
    const badge = screen.getByText("high");
    const dot = badge.querySelector("span");
    expect(dot?.className).toContain("bg-red-500");
  });

  it("has correct dot color for medium severity", () => {
    render(<SeverityBadge severity="medium" />);
    const badge = screen.getByText("medium");
    const dot = badge.querySelector("span");
    expect(dot?.className).toContain("bg-amber-500");
  });

  it("has correct dot color for low severity", () => {
    render(<SeverityBadge severity="low" />);
    const badge = screen.getByText("low");
    const dot = badge.querySelector("span");
    expect(dot?.className).toContain("bg-blue-500");
  });

  it("falls back to gray for unknown severity", () => {
    render(<SeverityBadge severity="critical" />);
    const badge = screen.getByText("critical");
    expect(badge.className).toContain("bg-gray-100");
    expect(badge.className).toContain("text-gray-600");
  });
});
