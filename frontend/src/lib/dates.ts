/**
 * Centralized date formatting utilities.
 */

const DEFAULT_LOCALE = "en-US";

/** Format as "Mar 18, 2026" */
export function formatDate(date: string | Date): string {
  return new Date(date).toLocaleDateString(DEFAULT_LOCALE, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/** Format as "Mar 18, 2026, 3:45 PM" */
export function formatDateTime(date: string | Date): string {
  return new Date(date).toLocaleString(DEFAULT_LOCALE, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** Format as relative time: "2 hours ago", "3 days ago", "just now" */
export function formatRelative(date: string | Date): string {
  const now = Date.now();
  const then = new Date(date).getTime();
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHour < 24) return `${diffHour}h ago`;
  if (diffDay < 30) return `${diffDay}d ago`;
  return formatDate(date);
}
