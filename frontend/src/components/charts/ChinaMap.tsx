import { useEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";

import { CountUp } from "../bits/CountUp";

export interface RegionDatum {
  name: string;
  value: number;
}

export interface RegionsOther {
  overseas: number;
  internal: number;
  unknown: number;
}

interface GeoFeature {
  type: string;
  properties: { name?: string; adcode?: number; center?: number[] };
  geometry: { type: string; coordinates: unknown };
}

const WIDTH = 1000;
const HEIGHT = 780;
const PADDING = 18;
const OPACITY_STEPS = [0.25, 0.43, 0.61, 0.79, 1];

function flattenPoints(geometry: { type: string; coordinates: unknown }): number[][] {
  const points: number[][] = [];
  const walk = (item: unknown): void => {
    if (!Array.isArray(item)) return;
    if (
      item.length === 2 &&
      typeof item[0] === "number" &&
      typeof item[1] === "number"
    ) {
      points.push(item as number[]);
      return;
    }
    for (const child of item) walk(child);
  };
  walk(geometry.coordinates);
  return points;
}

function computeProjection(features: GeoFeature[]) {
  const points = features.flatMap((feature) => flattenPoints(feature.geometry));
  const minLon = Math.min(...points.map((p) => p[0]));
  const maxLon = Math.max(...points.map((p) => p[0]));
  const minLat = Math.min(...points.map((p) => p[1]));
  const maxLat = Math.max(...points.map((p) => p[1]));
  const scale = Math.min(
    (WIDTH - PADDING * 2) / (maxLon - minLon),
    (HEIGHT - PADDING * 2) / (maxLat - minLat),
  );
  const offsetX =
    PADDING + (WIDTH - PADDING * 2 - (maxLon - minLon) * scale) / 2;
  const offsetY =
    PADDING + (HEIGHT - PADDING * 2 - (maxLat - minLat) * scale) / 2;
  return {
    project: (lon: number, lat: number): [number, number] => [
      offsetX + (lon - minLon) * scale,
      offsetY + (maxLat - lat) * scale,
    ],
  };
}

function pathD(
  geometry: { type: string; coordinates: unknown },
  project: (lon: number, lat: number) => [number, number],
): string {
  const ringD = (ring: number[][]): string => {
    if (!Array.isArray(ring) || ring.length === 0) return "";
    return (
      "M" +
      ring
        .map((point, index) => {
          const [x, y] = project(point[0], point[1]);
          return `${index === 0 ? "" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
        })
        .join("") +
      "Z"
    );
  };
  const polygonD = (polygon: number[][][]): string =>
    polygon.map(ringD).join("");
  if (geometry.type === "Polygon") {
    return polygonD(geometry.coordinates as number[][][]);
  }
  if (geometry.type === "MultiPolygon") {
    return (geometry.coordinates as number[][][][])
      .map(polygonD)
      .join("");
  }
  return "";
}

const numberFormat = new Intl.NumberFormat("zh-CN");

export function ChinaMap({
  data,
  others = { overseas: 0, internal: 0, unknown: 0 },
}: {
  data: RegionDatum[];
  others?: RegionsOther;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  // 地图 GeoJSON 体积较大（省级边界数据），组件挂载时按需异步加载，
  // 避免把它打进数据统计面板所在的分包，拖慢管理后台首次加载。
  const [regions, setRegions] = useState<{ name: string; d: string }[]>([]);
  const [hover, setHover] = useState<{
    name: string;
    value: number;
    x: number;
    y: number;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    void import("../../assets/maps/china.json")
      .then((mod) => {
        if (cancelled) return;
        const geoData = mod.default as unknown as { features: GeoFeature[] };
        const features = geoData.features.filter((feature) =>
          Boolean(feature.properties?.name),
        );
        const { project } = computeProjection(features);
        setRegions(
          features.map((feature) => ({
            name: feature.properties.name ?? "",
            d: pathD(feature.geometry, project),
          })),
        );
      })
      .catch(() => {
        // 地图数据加载失败时保留空地图与下方明细表，不阻断统计页其余内容
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const valueByName = useMemo(
    () => new Map(data.map((item) => [item.name, item.value])),
    [data],
  );
  const max = useMemo(
    () => Math.max(1, ...data.map((item) => item.value)),
    [data],
  );
  const total = useMemo(
    () =>
      data.reduce((sum, item) => sum + item.value, 0) +
      others.overseas +
      others.internal +
      others.unknown,
    [data, others],
  );

  const step = Math.max(1, Math.ceil(max / 5));
  const opacityFor = (value: number): number => {
    if (value <= 0) return 0;
    return OPACITY_STEPS[Math.min(4, Math.floor((value - 1) / step))];
  };
  const percentOf = (value: number): string =>
    total > 0 ? `${((value / total) * 100).toFixed(1)}%` : "0.0%";

  function handleMove(
    event: ReactMouseEvent<SVGPathElement>,
    name: string,
    value: number,
  ) {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    setHover({
      name,
      value,
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    });
  }

  const sorted = useMemo(
    () => [...data].sort((a, b) => b.value - a.value),
    [data],
  );

  return (
    <div ref={containerRef} className="relative">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label="中国登录来源地域分布图"
        className="block w-full"
      >
        {regions.map((region) => {
          const name = region.name;
          const value = valueByName.get(name) ?? 0;
          const opacity = opacityFor(value);
          return (
            <path
              key={name}
              d={region.d}
              data-name={name}
              data-value={String(value)}
              fill="var(--portal-primary)"
              fillOpacity={opacity}
              stroke="var(--portal-border)"
              strokeWidth={0.7}
              strokeLinejoin="round"
              onMouseEnter={(event) => handleMove(event, name, value)}
              onMouseMove={(event) => handleMove(event, name, value)}
              onMouseLeave={() => setHover(null)}
            >
              <title>
                {name}：{value} 次
              </title>
            </path>
          );
        })}
      </svg>

      {hover && (
        <div
          className="pointer-events-none absolute z-10 rounded-lg border border-border bg-surface px-2.5 py-2 text-xs shadow-sm"
          style={{
            left: Math.max(
              8,
              Math.min(
                hover.x + 12,
                (containerRef.current?.clientWidth ?? WIDTH) - 170,
              ),
            ),
            top: hover.y + 12,
          }}
        >
          <p className="whitespace-nowrap font-medium text-foreground">
            {hover.name} · {numberFormat.format(hover.value)} 次 ·{" "}
            {percentOf(hover.value)}
          </p>
        </div>
      )}

      {data.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 overflow-x-auto">
          <span
            className="flex items-center gap-1.5 text-xs text-muted"
          >
            <span
              className="inline-block h-3 w-4 rounded-sm"
              style={{ backgroundColor: "var(--portal-primary)", opacity: 0 }}
              aria-hidden="true"
            />
            0
          </span>
          {OPACITY_STEPS.map((opacity, index) => (
            <span
              key={opacity}
              className="flex items-center gap-1.5 text-xs text-muted"
            >
              <span
                className="inline-block h-3 w-4 rounded-sm"
                style={{ backgroundColor: "var(--portal-primary)", opacity }}
                aria-hidden="true"
              />
              {index === OPACITY_STEPS.length - 1
                ? `≥${index * step + 1}`
                : `${index * step + 1}–${(index + 1) * step}`}
            </span>
          ))}
        </div>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span className="badge badge-muted">
          海外 <CountUp from={0} to={others.overseas} separator="," className="tabular-nums" />
        </span>
        <span className="badge badge-muted">
          内网 <CountUp from={0} to={others.internal} separator="," className="tabular-nums" />
        </span>
        <span className="badge badge-muted">
          其它 <CountUp from={0} to={others.unknown} separator="," className="tabular-nums" />
        </span>
      </div>

      <table className="mt-3 w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted">
            <th className="pb-1.5 font-medium">地区</th>
            <th className="pb-1.5 text-right font-medium">登录次数</th>
            <th className="pb-1.5 text-right font-medium">占比</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((item) => (
            <tr key={item.name} className="border-b border-border/50">
              <td className="py-1.5 text-foreground">{item.name}</td>
              <td className="py-1.5 text-right text-foreground">
                {numberFormat.format(item.value)}
              </td>
              <td className="py-1.5 text-right text-muted">
                {percentOf(item.value)}
              </td>
            </tr>
          ))}
          {others.overseas > 0 && (
            <tr className="border-b border-border/50 text-muted">
              <td className="py-1.5">海外</td>
              <td className="py-1.5 text-right">{numberFormat.format(others.overseas)}</td>
              <td className="py-1.5 text-right">{percentOf(others.overseas)}</td>
            </tr>
          )}
          {others.internal > 0 && (
            <tr className="border-b border-border/50 text-muted">
              <td className="py-1.5">内网</td>
              <td className="py-1.5 text-right">{numberFormat.format(others.internal)}</td>
              <td className="py-1.5 text-right">{percentOf(others.internal)}</td>
            </tr>
          )}
          {others.unknown > 0 && (
            <tr className="border-b border-border/50 text-muted">
              <td className="py-1.5">其它</td>
              <td className="py-1.5 text-right">{numberFormat.format(others.unknown)}</td>
              <td className="py-1.5 text-right">{percentOf(others.unknown)}</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
