"use client";

/**
 * SecureScoreGauge -- circular SVG gauge that displays the overall
 * secure-score percentage with a gradient arc, glow effect and label.
 */

interface SecureScoreGaugeProps {
  score: number | null;
}

export default function SecureScoreGauge({ score }: SecureScoreGaugeProps) {
  const value = score ?? 0;
  const clampedValue = Math.max(0, Math.min(100, value));

  // Arc geometry
  const cx = 140;
  const cy = 130;
  const radius = 100;
  const strokeWidth = 14;
  const startAngle = 150; // degrees, measured from positive X axis
  const endAngle = 390; // 150 + 240 = full sweep of 240 degrees
  const sweepAngle = 240;

  const polarToCartesian = (
    centerX: number,
    centerY: number,
    r: number,
    angleDeg: number,
  ) => {
    const angleRad = ((angleDeg - 90) * Math.PI) / 180;
    return {
      x: centerX + r * Math.cos(angleRad),
      y: centerY + r * Math.sin(angleRad),
    };
  };

  const describeArc = (
    x: number,
    y: number,
    r: number,
    startAng: number,
    endAng: number,
  ) => {
    const start = polarToCartesian(x, y, r, endAng);
    const end = polarToCartesian(x, y, r, startAng);
    const largeArcFlag = endAng - startAng <= 180 ? "0" : "1";
    return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArcFlag} 0 ${end.x} ${end.y}`;
  };

  const bgPath = describeArc(cx, cy, radius, startAngle, endAngle);
  const valueAngle = startAngle + (sweepAngle * clampedValue) / 100;
  const valuePath =
    clampedValue > 0 ? describeArc(cx, cy, radius, startAngle, valueAngle) : "";

  // Gradient ID and color based on score
  const getScoreColor = (v: number): string => {
    if (v >= 80) return "#22c55e";
    if (v >= 50) return "#f59e0b";
    return "#ef4444";
  };

  const getScoreGradient = (
    v: number,
  ): { start: string; end: string; id: string } => {
    if (v >= 80) return { start: "#4ade80", end: "#16a34a", id: "gaugeGreen" };
    if (v >= 50) return { start: "#fbbf24", end: "#d97706", id: "gaugeAmber" };
    return { start: "#f87171", end: "#dc2626", id: "gaugeRed" };
  };

  const gradient = getScoreGradient(clampedValue);
  const scoreColor = getScoreColor(clampedValue);

  const getScoreLabel = (v: number): string => {
    if (v >= 90) return "Excellent";
    if (v >= 80) return "Good";
    if (v >= 60) return "Fair";
    if (v >= 40) return "Needs Work";
    return "Critical";
  };

  // Circumference for dash animation
  const arcLength = (sweepAngle / 360) * 2 * Math.PI * radius;
  const filledLength = (clampedValue / 100) * arcLength;

  return (
    <div className="relative flex flex-col items-center select-none">
      <svg
        className="h-auto w-full max-w-[280px] drop-shadow-lg"
        viewBox="0 0 280 200"
        style={{ userSelect: "none" }}
      >
        <defs>
          <linearGradient id={gradient.id} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={gradient.start} />
            <stop offset="100%" stopColor={gradient.end} />
          </linearGradient>
          <filter id="gaugeShadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow
              dx="0"
              dy="0"
              stdDeviation="4"
              floodColor={scoreColor}
              floodOpacity="0.3"
            />
          </filter>
        </defs>

        {/* Background arc */}
        <path
          d={bgPath}
          fill="none"
          stroke="currentColor"
          className="text-gray-200 dark:text-gray-700"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />

        {/* Value arc with gradient */}
        {clampedValue > 0 && (
          <path
            d={valuePath}
            fill="none"
            stroke={`url(#${gradient.id})`}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            filter="url(#gaugeShadow)"
            strokeDasharray={`${filledLength} ${arcLength}`}
            className="transition-all duration-1000 ease-out"
          />
        )}

        {/* Score text in center */}
        <text
          x={cx}
          y={cy - 4}
          textAnchor="middle"
          className="fill-gray-900 dark:fill-white"
          style={{ fontSize: "38px", fontWeight: 800, pointerEvents: "none" }}
        >
          {score != null ? `${score}%` : "N/A"}
        </text>
        <text
          x={cx}
          y={cy + 18}
          textAnchor="middle"
          className="fill-gray-500 dark:fill-gray-400"
          style={{ fontSize: "13px", fontWeight: 500 }}
        >
          {score != null ? getScoreLabel(clampedValue) : "No data"}
        </text>

        {/* Tick marks at 0 and 100 positions */}
        <text
          x={polarToCartesian(cx, cy, radius + 22, startAngle).x}
          y={polarToCartesian(cx, cy, radius + 22, startAngle).y}
          textAnchor="middle"
          className="fill-gray-400 dark:fill-gray-500"
          style={{ fontSize: "11px" }}
        >
          0
        </text>
        <text
          x={polarToCartesian(cx, cy, radius + 22, endAngle).x}
          y={polarToCartesian(cx, cy, radius + 22, endAngle).y}
          textAnchor="middle"
          className="fill-gray-400 dark:fill-gray-500"
          style={{ fontSize: "11px" }}
        >
          100
        </text>
      </svg>
    </div>
  );
}
