"use client";

import { useEffect, useState } from "react";
import api from "@/lib/api";

interface PasswordStrengthProps {
  password: string;
  userInputs?: string[];
}

const LABELS = ["Very weak", "Weak", "Fair", "Strong", "Very strong"];
const COLORS = [
  "bg-red-500",
  "bg-orange-500",
  "bg-yellow-500",
  "bg-blue-500",
  "bg-green-500",
];
const TEXT_COLORS = [
  "text-red-500",
  "text-orange-500",
  "text-yellow-500",
  "text-blue-500",
  "text-green-500",
];

export default function PasswordStrength({
  password,
  userInputs = [],
}: PasswordStrengthProps) {
  const [score, setScore] = useState(0);
  const [crackTime, setCrackTime] = useState("");
  const [feedback, setFeedback] = useState<string>("");

  useEffect(() => {
    if (!password || password.length < 4) {
      setScore(0);
      setCrackTime("");
      setFeedback("");
      return;
    }

    const timer = setTimeout(async () => {
      try {
        const res = await api.post("/auth/password-strength", {
          password,
          user_inputs: userInputs,
        });
        const data = res.data?.data;
        if (data) {
          setScore(data.score);
          setCrackTime(data.crack_time || "");
          const fb = data.feedback || {};
          setFeedback(fb.warning || (fb.suggestions?.[0] ?? ""));
        }
      } catch {
        // Ignore — strength check is best-effort
      }
    }, 300); // Debounce 300ms

    return () => clearTimeout(timer);
  }, [password, userInputs]);

  if (!password || password.length < 4) return null;

  return (
    <div className="mt-2 space-y-1.5">
      {/* Strength bar */}
      <div className="flex gap-1">
        {[0, 1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className={`h-1.5 flex-1 rounded-full transition-colors ${
              i <= score ? COLORS[score] : "bg-gray-200 dark:bg-gray-700"
            }`}
          />
        ))}
      </div>

      {/* Label + crack time */}
      <div className="flex items-center justify-between">
        <span className={`text-xs font-medium ${TEXT_COLORS[score]}`}>
          {LABELS[score]}
        </span>
        {crackTime && (
          <span className="text-xs text-gray-400 dark:text-gray-500">
            Crack time: {crackTime}
          </span>
        )}
      </div>

      {/* Feedback */}
      {feedback && (
        <p className="text-xs text-gray-500 dark:text-gray-400">{feedback}</p>
      )}
    </div>
  );
}
