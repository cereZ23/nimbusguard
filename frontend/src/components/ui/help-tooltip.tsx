"use client";

import { useEffect, useRef, useState } from "react";

export interface HelpTooltipProps {
  content: string;
  title?: string;
  placement?: "top" | "bottom" | "left" | "right";
  className?: string;
}

export default function HelpTooltip({
  content,
  title,
  placement = "top",
  className = "",
}: HelpTooltipProps) {
  const [visible, setVisible] = useState(false);
  const containerRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!visible) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setVisible(false);
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [visible]);

  useEffect(() => {
    if (!visible) return;
    const handleClick = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setVisible(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [visible]);

  const placementClasses: Record<string, string> = {
    top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
    bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
    left: "right-full top-1/2 -translate-y-1/2 mr-2",
    right: "left-full top-1/2 -translate-y-1/2 ml-2",
  };

  const arrowClasses: Record<string, string> = {
    top: "top-full left-1/2 -translate-x-1/2 border-l-transparent border-r-transparent border-b-transparent border-t-gray-800 dark:border-t-gray-100",
    bottom:
      "bottom-full left-1/2 -translate-x-1/2 border-l-transparent border-r-transparent border-t-transparent border-b-gray-800 dark:border-b-gray-100",
    left: "left-full top-1/2 -translate-y-1/2 border-t-transparent border-b-transparent border-r-transparent border-l-gray-800 dark:border-l-gray-100",
    right:
      "right-full top-1/2 -translate-y-1/2 border-t-transparent border-b-transparent border-l-transparent border-r-gray-800 dark:border-r-gray-100",
  };

  return (
    <span
      ref={containerRef}
      className={`relative inline-flex items-center ${className}`}
    >
      <button
        type="button"
        aria-label={title ? `Help: ${title}` : "Help"}
        aria-expanded={visible}
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
        onFocus={() => setVisible(true)}
        onBlur={() => setVisible(false)}
        onClick={() => setVisible((v) => !v)}
        className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-gray-300 bg-gray-100 text-[10px] font-bold text-gray-500 transition-colors hover:border-indigo-400 hover:bg-indigo-50 hover:text-indigo-600 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-1 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-400 dark:hover:border-indigo-500 dark:hover:bg-indigo-900/30 dark:hover:text-indigo-400"
      >
        ?
      </button>
      {visible && (
        <span
          role="tooltip"
          className={`pointer-events-none absolute z-50 w-64 ${placementClasses[placement]}`}
        >
          <span
            className={`absolute h-0 w-0 border-4 ${arrowClasses[placement]}`}
            aria-hidden="true"
          />
          <span className="block rounded-lg bg-gray-800 px-3 py-2 text-xs text-gray-100 shadow-lg dark:bg-gray-100 dark:text-gray-800">
            {title && <span className="mb-1 block font-semibold">{title}</span>}
            {content}
          </span>
        </span>
      )}
    </span>
  );
}
