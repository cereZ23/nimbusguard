"use client";

import { forwardRef, useId } from "react";
import type { InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className = "", id: externalId, ...rest }, ref) => {
    const generatedId = useId();
    const inputId = externalId ?? generatedId;
    const errorId = error ? `${inputId}-error` : undefined;

    return (
      <div>
        {label && (
          <label
            htmlFor={inputId}
            className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300"
          >
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          aria-invalid={error ? "true" : undefined}
          aria-describedby={errorId}
          className={[
            "w-full rounded-lg border px-3 py-2 text-sm shadow-sm transition-colors",
            "placeholder:text-gray-400 dark:placeholder:text-gray-500",
            "focus:outline-none focus:ring-1",
            "dark:bg-gray-900 dark:text-white",
            error
              ? "border-red-500 focus:border-red-500 focus:ring-red-500 dark:border-red-500"
              : "border-gray-300 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600",
            rest.disabled
              ? "cursor-not-allowed bg-gray-50 opacity-60 dark:bg-gray-800"
              : "bg-white",
            className,
          ]
            .filter(Boolean)
            .join(" ")}
          {...rest}
        />
        {error && (
          <p
            id={errorId}
            className="mt-1 text-xs text-red-600 dark:text-red-400"
          >
            {error}
          </p>
        )}
      </div>
    );
  },
);

Input.displayName = "Input";

export default Input;
