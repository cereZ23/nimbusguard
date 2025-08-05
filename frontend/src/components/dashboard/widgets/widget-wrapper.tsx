"use client";

import { X, GripVertical, Maximize2, Minimize2 } from "lucide-react";

interface WidgetWrapperProps {
  title: string;
  children: React.ReactNode;
  colSpan?: number;
  rowSpan?: number;
  editing?: boolean;
  onRemove?: () => void;
  onResize?: (larger: boolean) => void;
}

export default function WidgetWrapper({
  title,
  children,
  colSpan = 4,
  rowSpan = 3,
  editing = false,
  onRemove,
  onResize,
}: WidgetWrapperProps) {
  return (
    <div
      className="relative overflow-hidden rounded-2xl border border-gray-200/80 bg-white/70 shadow-lg backdrop-blur-sm transition-all duration-200 dark:border-gray-700/60 dark:bg-gray-800/70"
      style={{
        gridColumn: `span ${colSpan}`,
        gridRow: `span ${rowSpan}`,
      }}
    >
      {editing && (
        <div className="absolute inset-x-0 top-0 z-10 flex items-center justify-between border-b border-dashed border-indigo-300 bg-indigo-50/80 px-3 py-1.5 dark:border-indigo-700 dark:bg-indigo-900/40">
          <div className="flex items-center gap-2">
            <GripVertical className="h-4 w-4 text-indigo-400" />
            <span className="text-xs font-medium text-indigo-600 dark:text-indigo-300">
              {title}
            </span>
          </div>
          <div className="flex items-center gap-1">
            {onResize && (
              <>
                <button
                  type="button"
                  onClick={() => onResize(false)}
                  className="rounded p-1 text-indigo-400 transition-colors hover:bg-indigo-100 hover:text-indigo-600 dark:hover:bg-indigo-800 dark:hover:text-indigo-300"
                  title="Make smaller"
                >
                  <Minimize2 className="h-3.5 w-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => onResize(true)}
                  className="rounded p-1 text-indigo-400 transition-colors hover:bg-indigo-100 hover:text-indigo-600 dark:hover:bg-indigo-800 dark:hover:text-indigo-300"
                  title="Make larger"
                >
                  <Maximize2 className="h-3.5 w-3.5" />
                </button>
              </>
            )}
            {onRemove && (
              <button
                type="button"
                onClick={onRemove}
                className="rounded p-1 text-red-400 transition-colors hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-900/40 dark:hover:text-red-300"
                title="Remove widget"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>
      )}
      <div className={`p-5 ${editing ? "pt-12" : ""}`}>{children}</div>
    </div>
  );
}
