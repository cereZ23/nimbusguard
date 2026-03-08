"use client";

import { ChevronUp, ChevronDown } from "lucide-react";

interface SortIndicatorProps<T extends string> {
  column: T;
  active: T;
  order: "asc" | "desc";
}

export default function SortIndicator<T extends string>({
  column,
  active,
  order,
}: SortIndicatorProps<T>) {
  if (column !== active) {
    return (
      <span className="ml-1 inline-flex flex-col opacity-30" aria-hidden="true">
        <ChevronUp className="h-3 w-3 -mb-1" />
        <ChevronDown className="h-3 w-3" />
      </span>
    );
  }
  return order === "asc" ? (
    <ChevronUp
      className="ml-1 inline h-3.5 w-3.5 text-blue-500"
      aria-hidden="true"
    />
  ) : (
    <ChevronDown
      className="ml-1 inline h-3.5 w-3.5 text-blue-500"
      aria-hidden="true"
    />
  );
}
