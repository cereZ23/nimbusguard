import type { TourStep } from "@/components/ui/guided-tour";

export const DASHBOARD_TOUR: TourStep[] = [
  {
    target: "[data-tour='secure-score']",
    title: "Secure Score",
    content:
      "This gauge shows your overall cloud security posture (0-100%). Aim for 80%+ to maintain a healthy baseline. It updates after every scan.",
    placement: "right",
  },
  {
    target: "[data-tour='kpi-cards']",
    title: "KPI Summary",
    content:
      "These cards give you a quick overview of your total assets, total findings, and high-severity issues across all connected cloud accounts.",
    placement: "bottom",
  },
  {
    target: "[data-tour='severity-donut']",
    title: "Findings by Severity",
    content:
      "Click any segment of this chart to filter the Findings page by that severity level. Red is critical, orange is high.",
    placement: "top",
  },
  {
    target: "[data-tour='trend-chart']",
    title: "Trend Over Time",
    content:
      "Track how your security findings have changed over the selected time range. A downward trend means your posture is improving.",
    placement: "top",
  },
  {
    target: "[data-tour='top-controls']",
    title: "Top Failing Controls",
    content:
      "These controls have the most failing resources. Focus your remediation efforts here for the highest impact on your score.",
    placement: "top",
  },
];

export const FINDINGS_TOUR: TourStep[] = [
  {
    target: "[data-tour='findings-search']",
    title: "Search Findings",
    content:
      "Search findings by title using keywords. The search is debounced — results update automatically as you type.",
    placement: "bottom",
  },
  {
    target: "[data-tour='findings-filters']",
    title: "Filter by Severity and Status",
    content:
      "Narrow down findings by severity (High, Medium, Low) or status (Open, Waived, etc.) to focus on what matters most.",
    placement: "bottom",
  },
  {
    target: "[data-tour='findings-table']",
    title: "Findings Table",
    content:
      "Click any row to view full details, evidence, and remediation steps. Use the checkboxes to select multiple findings for bulk actions.",
    placement: "top",
  },
];

export const ASSETS_TOUR: TourStep[] = [
  {
    target: "[data-tour='assets-search']",
    title: "Search Assets",
    content:
      "Search cloud resources by name. Supports partial matches. Press Enter or wait 300ms to trigger the search.",
    placement: "bottom",
  },
  {
    target: "[data-tour='assets-filters']",
    title: "Filter Assets",
    content:
      "Filter by resource type (e.g., Storage Account, VM) or Azure region to quickly find specific resources.",
    placement: "bottom",
  },
  {
    target: "[data-tour='assets-table']",
    title: "Asset Inventory",
    content:
      "All cloud resources discovered during your last scan. Click any row to view the asset details and associated findings.",
    placement: "top",
  },
];
