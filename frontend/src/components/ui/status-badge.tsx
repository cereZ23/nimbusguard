const config: Record<
  string,
  {
    dot: string;
    bg: string;
    text: string;
    darkBg: string;
    darkText: string;
    label: string;
  }
> = {
  fail: {
    dot: "bg-red-500",
    bg: "bg-red-50",
    text: "text-red-700",
    darkBg: "dark:bg-red-900/30",
    darkText: "dark:text-red-400",
    label: "Fail",
  },
  error: {
    dot: "bg-orange-500",
    bg: "bg-orange-50",
    text: "text-orange-700",
    darkBg: "dark:bg-orange-900/30",
    darkText: "dark:text-orange-400",
    label: "Error",
  },
  pass: {
    dot: "bg-green-500",
    bg: "bg-green-50",
    text: "text-green-700",
    darkBg: "dark:bg-green-900/30",
    darkText: "dark:text-green-400",
    label: "Pass",
  },
  not_applicable: {
    dot: "bg-gray-400",
    bg: "bg-gray-100",
    text: "text-gray-600",
    darkBg: "dark:bg-gray-700",
    darkText: "dark:text-gray-300",
    label: "N/A",
  },
};

export default function StatusBadge({ status }: { status: string }) {
  const c = config[status] ?? {
    dot: "bg-gray-400",
    bg: "bg-gray-100",
    text: "text-gray-600",
    darkBg: "dark:bg-gray-700",
    darkText: "dark:text-gray-300",
    label: status,
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${c.bg} ${c.text} ${c.darkBg} ${c.darkText}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${c.dot}`} />
      {c.label}
    </span>
  );
}
