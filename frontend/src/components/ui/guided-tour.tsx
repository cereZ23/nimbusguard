"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export interface TourStep {
  target: string;
  title: string;
  content: string;
  placement?: "top" | "bottom" | "left" | "right";
}

interface GuidedTourProps {
  steps: TourStep[];
  tourId: string;
  active: boolean;
  onComplete: () => void;
}

export default function GuidedTour({
  steps,
  tourId,
  active,
  onComplete,
}: GuidedTourProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const step = steps[currentStep];

  const measure = useCallback(() => {
    if (!step) return;
    const el = document.querySelector(step.target);
    if (el) {
      setRect(el.getBoundingClientRect());
    } else {
      setRect(null);
    }
  }, [step]);

  useEffect(() => {
    if (!active) return;
    measure();
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [active, measure]);

  useEffect(() => {
    if (!active) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        finish();
      } else if (e.key === "ArrowRight" || e.key === "Enter") {
        next();
      } else if (e.key === "ArrowLeft") {
        prev();
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  });

  const finish = useCallback(() => {
    localStorage.setItem(`tour-completed-${tourId}`, "true");
    setCurrentStep(0);
    onComplete();
  }, [tourId, onComplete]);

  const next = useCallback(() => {
    if (currentStep < steps.length - 1) {
      setCurrentStep((s) => s + 1);
    } else {
      finish();
    }
  }, [currentStep, steps.length, finish]);

  const prev = useCallback(() => {
    if (currentStep > 0) {
      setCurrentStep((s) => s - 1);
    }
  }, [currentStep]);

  if (!active || !step) return null;

  const padding = 8;
  const spotlightX = rect ? rect.x - padding : 0;
  const spotlightY = rect ? rect.y - padding : 0;
  const spotlightW = rect ? rect.width + padding * 2 : 0;
  const spotlightH = rect ? rect.height + padding * 2 : 0;

  const placement = step.placement ?? "bottom";

  const getTooltipStyle = (): React.CSSProperties => {
    if (!rect)
      return { top: "50%", left: "50%", transform: "translate(-50%, -50%)" };
    switch (placement) {
      case "top":
        return {
          bottom: window.innerHeight - rect.top + 16,
          left: rect.left + rect.width / 2,
          transform: "translateX(-50%)",
        };
      case "bottom":
        return {
          top: rect.bottom + 16,
          left: rect.left + rect.width / 2,
          transform: "translateX(-50%)",
        };
      case "left":
        return {
          top: rect.top + rect.height / 2,
          right: window.innerWidth - rect.left + 16,
          transform: "translateY(-50%)",
        };
      case "right":
        return {
          top: rect.top + rect.height / 2,
          left: rect.right + 16,
          transform: "translateY(-50%)",
        };
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-[9999]" aria-modal="true" role="dialog">
      {/* SVG overlay with spotlight cutout */}
      <svg className="absolute inset-0 h-full w-full" aria-hidden="true">
        <defs>
          <mask id={`tour-mask-${tourId}`}>
            <rect x="0" y="0" width="100%" height="100%" fill="white" />
            {rect && (
              <rect
                x={spotlightX}
                y={spotlightY}
                width={spotlightW}
                height={spotlightH}
                rx="8"
                fill="black"
              />
            )}
          </mask>
        </defs>
        <rect
          x="0"
          y="0"
          width="100%"
          height="100%"
          fill="rgba(0,0,0,0.5)"
          mask={`url(#tour-mask-${tourId})`}
        />
      </svg>

      {/* Tooltip */}
      <div
        ref={tooltipRef}
        className="absolute z-[10000] w-80 rounded-xl bg-white p-4 shadow-2xl dark:bg-gray-800"
        style={getTooltipStyle()}
      >
        <div className="mb-1 text-xs font-medium text-indigo-600 dark:text-indigo-400">
          Step {currentStep + 1} of {steps.length}
        </div>
        <h3 className="mb-1 text-sm font-semibold text-gray-900 dark:text-gray-100">
          {step.title}
        </h3>
        <p className="mb-4 text-sm text-gray-600 dark:text-gray-300">
          {step.content}
        </p>
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={finish}
            className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
          >
            Skip tour
          </button>
          <div className="flex gap-2">
            {currentStep > 0 && (
              <button
                type="button"
                onClick={prev}
                className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
              >
                Back
              </button>
            )}
            <button
              type="button"
              onClick={next}
              className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700"
            >
              {currentStep < steps.length - 1 ? "Next" : "Finish"}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
