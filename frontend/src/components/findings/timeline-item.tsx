"use client";

import {
  ArrowRightLeft,
  ShieldAlert,
  UserCheck,
  UserMinus,
  MessageCircle,
  ShieldCheck,
  Clock,
} from "lucide-react";
import { formatRelative } from "@/lib/dates";
import type { FindingEvent } from "@/types";

export function getEventIcon(eventType: string) {
  switch (eventType) {
    case "status_change":
      return <ArrowRightLeft className="h-3.5 w-3.5" />;
    case "severity_change":
      return <ShieldAlert className="h-3.5 w-3.5" />;
    case "assigned":
      return <UserCheck className="h-3.5 w-3.5" />;
    case "unassigned":
      return <UserMinus className="h-3.5 w-3.5" />;
    case "commented":
      return <MessageCircle className="h-3.5 w-3.5" />;
    case "waiver_requested":
      return <ShieldCheck className="h-3.5 w-3.5" />;
    case "waiver_approved":
      return <ShieldCheck className="h-3.5 w-3.5" />;
    default:
      return <Clock className="h-3.5 w-3.5" />;
  }
}

export function getEventColor(eventType: string): string {
  switch (eventType) {
    case "status_change":
      return "bg-blue-100 text-blue-600 dark:bg-blue-900/40 dark:text-blue-400";
    case "severity_change":
      return "bg-orange-100 text-orange-600 dark:bg-orange-900/40 dark:text-orange-400";
    case "assigned":
      return "bg-green-100 text-green-600 dark:bg-green-900/40 dark:text-green-400";
    case "unassigned":
      return "bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400";
    case "commented":
      return "bg-indigo-100 text-indigo-600 dark:bg-indigo-900/40 dark:text-indigo-400";
    case "waiver_requested":
      return "bg-purple-100 text-purple-600 dark:bg-purple-900/40 dark:text-purple-400";
    case "waiver_approved":
      return "bg-emerald-100 text-emerald-600 dark:bg-emerald-900/40 dark:text-emerald-400";
    default:
      return "bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400";
  }
}

export function formatEventDescription(event: FindingEvent): string {
  const actor = event.user_email ?? "System";

  switch (event.event_type) {
    case "status_change":
      return `Status changed from ${event.old_value ?? "unknown"} to ${event.new_value ?? "unknown"} by ${actor}`;
    case "severity_change":
      return `Severity changed from ${event.old_value ?? "unknown"} to ${event.new_value ?? "unknown"} by ${actor}`;
    case "assigned":
      return `Assigned by ${actor}`;
    case "unassigned":
      return `Unassigned by ${actor}`;
    case "commented":
      return `${actor} added a comment`;
    case "waiver_requested":
      return `Waiver requested by ${actor}`;
    case "waiver_approved":
      return `Waiver approved by ${actor}`;
    default:
      return `${event.event_type} by ${actor}`;
  }
}

interface TimelineItemProps {
  event: FindingEvent;
}

function TimelineItem({ event }: TimelineItemProps) {
  return (
    <div className="relative flex gap-3 pl-0">
      {/* Dot / icon */}
      <div
        className={`relative z-10 flex h-[30px] w-[30px] flex-shrink-0 items-center justify-center rounded-full ${getEventColor(event.event_type)}`}
      >
        {getEventIcon(event.event_type)}
      </div>

      {/* Content */}
      <div className="flex-1 pt-1">
        <p className="text-sm text-gray-800 dark:text-gray-200">
          {formatEventDescription(event)}
        </p>
        {event.details && event.event_type !== "commented" && (
          <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400 truncate max-w-md">
            {event.details}
          </p>
        )}
        <p className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">
          {formatRelative(event.created_at)}
        </p>
      </div>
    </div>
  );
}

export default TimelineItem;
