"use client";

import { useEffect } from "react";
import { installGlobalErrorHandlers } from "@/lib/error-reporter";

export default function GlobalErrorHandlers() {
  useEffect(() => {
    installGlobalErrorHandlers();
  }, []);

  return null;
}
