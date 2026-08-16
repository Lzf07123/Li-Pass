import {
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";

export interface LineSeries {
  name: string;
  values: number[];
  dashed?: boolean;
  color?: string;
}

interface LineChartProps {
  labels: string[];
  series: LineSeries[];
  formatValue?: (value: number) => string;
  height?: number;
}

const DEFAULT_COLORS = [
  "var(--portal-primary)",
  "var(--portal-accent-aqua)",
  "var(--portal-accent-lilac)",
  "var(--portal-accent-sage)",
  "var(--portal-accent-mint)",
  "var(--portal-accent-ice)",
];

const PADDING = { top: 16, right: 12, bottom: 28, left: 42 };

export function LineChart({
  labels,
  series,
  formatValue = (value) => String(value),
  height = 240,
}: LineChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [width, setWidth] = useState(0);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  useLayoutEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const measure = () => setWidth(element.clientWidth);
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const model = useMemo(() => {
    const pointCount = labels.length;
    const rawMax = Math.max(1, ...series.flatMap((item) => item.values));
    const step = Math.max(1, Math.ceil(rawMax / 4));
    const max = step * 4;
    const plotWidth = Math.max(0, width - PADDING.left - PADDING.right);
    const plotHeight = Math.max(0, height - PADDING.top - PADDING.bottom);

    const xAt = (index: number) =>
      PADDING.left +
      (pointCount <= 1 ? 0.5 : index / (pointCount - 1)) * plotWidth;
    const yAt = (value: number) =>
      PADDING.top + plotHeight * (1 - value / max);

    return { pointCount, max, step, plotWidth, plotHeight, xAt, yAt };
  }, [height, labels.length, series, width]);

  const ariaLabel = useMemo(() => {
    const names = series.map((item) => item.name).join("、");
    return `${names} 最近 ${labels.length} 天趋势图`;
  }, [labels.length, series]);

  function handlePointerMove(event: ReactPointerEvent<SVGSVGElement>) {
    const svg = svgRef.current;
    if (!svg || model.pointCount === 0) return;
    const rect = svg.getBoundingClientRect();
    const relativeX = event.clientX - rect.left - PADDING.left;
    const fraction =
      model.pointCount <= 1 ? 0 : relativeX / model.plotWidth;
    const index = Math.round(fraction * (model.pointCount - 1));
    setHoverIndex(Math.max(0, Math.min(model.pointCount - 1, index)));
  }

  const tooltipLeft =
    hoverIndex === null ? 0 : model.xAt(hoverIndex);
  const ticks = [0, model.step, model.step * 2, model.step * 3, model.max];
  const xLabelEvery = Math.max(1, Math.ceil(labels.length / 8));

  return (
    <div ref={containerRef} className="relative w-full">
      <div style={{ height }}>
        <svg
          ref={svgRef}
          role="img"
          aria-label={ariaLabel}
          width={width}
          height={height}
          className="block overflow-visible"
          onPointerMove={handlePointerMove}
          onPointerLeave={() => setHoverIndex(null)}
        >
          {ticks.map((tick, index) => (
            <g key={tick}>
              <line
                x1={PADDING.left}
                x2={Math.max(PADDING.left, width - PADDING.right)}
                y1={model.yAt(tick)}
                y2={model.yAt(tick)}
                className="stroke-border"
                strokeWidth={1}
                strokeDasharray={index === 0 ? undefined : "3 4"}
              />
              <text
                x={PADDING.left - 8}
                y={model.yAt(tick) + 4}
                textAnchor="end"
                className="fill-muted text-[11px]"
              >
                {formatValue(tick)}
              </text>
            </g>
          ))}

          {labels.map((label, index) =>
            index % xLabelEvery === 0 ? (
              <text
                key={label}
                x={model.xAt(index)}
                y={height - 8}
                textAnchor="middle"
                className="fill-muted text-[11px]"
              >
                {label}
              </text>
            ) : null
          )}

          {hoverIndex !== null && (
            <line
              x1={tooltipLeft}
              x2={tooltipLeft}
              y1={PADDING.top}
              y2={height - PADDING.bottom}
              className="stroke-border"
              strokeWidth={1}
            />
          )}

          {series.map((item, seriesIndex) => {
            const color =
              item.color ??
              DEFAULT_COLORS[seriesIndex % DEFAULT_COLORS.length];
            const points = item.values
              .map((value, index) => `${model.xAt(index)},${model.yAt(value)}`)
              .join(" ");
            return (
              <polyline
                key={item.name}
                points={points}
                fill="none"
                stroke={color}
                strokeWidth={2}
                strokeLinejoin="round"
                strokeLinecap="round"
                strokeDasharray={item.dashed ? "5 4" : undefined}
              />
            );
          })}

          {hoverIndex !== null &&
            series.map((item, seriesIndex) => (
              <circle
                key={item.name}
                cx={model.xAt(hoverIndex)}
                cy={model.yAt(item.values[hoverIndex] ?? 0)}
                r={3.5}
                fill={
                  item.color ??
                  DEFAULT_COLORS[seriesIndex % DEFAULT_COLORS.length]
                }
                stroke="var(--portal-surface)"
                strokeWidth={1.5}
              />
            ))}
        </svg>
      </div>

      {width > 0 && hoverIndex !== null && labels[hoverIndex] && (
        <div
          className="pointer-events-none absolute z-10 rounded-lg border border-border bg-surface px-2.5 py-2 text-xs shadow-sm"
          style={{
            left: Math.max(70, Math.min(width - 70, tooltipLeft)),
            top: 4,
            transform: "translateX(-50%)",
          }}
        >
          <p className="mb-1 whitespace-nowrap font-medium text-foreground">
            {labels[hoverIndex]}
          </p>
          {series.map((item, seriesIndex) => (
            <p
              key={item.name}
              className="flex items-center gap-1.5 whitespace-nowrap text-muted"
            >
              <span
                className="inline-block size-2 rounded-full"
                style={{
                  backgroundColor:
                    item.color ??
                    DEFAULT_COLORS[seriesIndex % DEFAULT_COLORS.length],
                }}
                aria-hidden="true"
              />
              {item.name}：{formatValue(item.values[hoverIndex] ?? 0)}
            </p>
          ))}
        </div>
      )}

      <div className="mt-2 flex items-center gap-x-4 gap-y-1 overflow-x-auto">
        {series.map((item, seriesIndex) => (
          <span
            key={item.name}
            className="flex items-center gap-1.5 whitespace-nowrap text-xs text-muted"
          >
            <span
              className="inline-block h-0.5 w-4 rounded-full"
              style={{
                backgroundColor:
                  item.color ??
                  DEFAULT_COLORS[seriesIndex % DEFAULT_COLORS.length],
              }}
              aria-hidden="true"
            />
            {item.name}
          </span>
        ))}
      </div>

      {/* 屏幕阅读器可见的数据表：图表本体的可访问性兜底。 */}
      <table className="sr-only">
        <caption>{ariaLabel}</caption>
        <thead>
          <tr>
            <th>日期</th>
            {series.map((item) => (
              <th key={item.name}>{item.name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {labels.map((label, index) => (
            <tr key={label}>
              <th scope="row">{label}</th>
              {series.map((item) => (
                <td key={item.name}>
                  {formatValue(item.values[index] ?? 0)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
