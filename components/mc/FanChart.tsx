"use client";
import { Area, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid, Legend } from "recharts";
import type { FanChart as FanChartData, SamplePath } from "@/lib/monteCarlo";

interface Props {
  fan: FanChartData;
  samples?: SamplePath[];
  startingEur: number;
  horizonYears: number;
}

export default function FanChart({ fan, samples, startingEur, horizonYears }: Props) {
  // Convert ts (trading day indices) to year fractions for x-axis
  const tradingDaysPerYear = 252;
  const data = fan.ts.map((t, i) => {
    const yr = t / tradingDaysPerYear;
    const row: Record<string, number> = {
      year: parseFloat(yr.toFixed(2)),
      p5: fan.p5[i],
      p10: fan.p10[i],
      p25: fan.p25[i],
      p50: fan.p50[i],
      p75: fan.p75[i],
      p90: fan.p90[i],
      p95: fan.p95[i],
      band_5_95: fan.p95[i] - fan.p5[i],
      band_10_90: fan.p90[i] - fan.p10[i],
      band_25_75: fan.p75[i] - fan.p25[i],
    };
    return row;
  });

  const fmt = (v: number) => v.toLocaleString("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

  return (
    <div style={{ width: "100%", height: 420 }}>
      <ResponsiveContainer>
        <ComposedChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis
            dataKey="year"
            type="number"
            domain={[0, horizonYears]}
            ticks={Array.from({ length: horizonYears + 1 }, (_, i) => i)}
            label={{ value: "Years from today", position: "insideBottom", offset: -5, fill: "#71717a", fontSize: 11 }}
            stroke="#52525b"
          />
          <YAxis
            scale="log"
            domain={[startingEur * 0.4, "auto"]}
            tickFormatter={fmt}
            stroke="#52525b"
            width={90}
          />
          <Tooltip
            contentStyle={{ backgroundColor: "#18181b", border: "1px solid #3f3f46", borderRadius: 6 }}
            labelStyle={{ color: "#e4e4e7" }}
            formatter={(v: number) => fmt(v)}
          />

          {/* 5-95 ribbon (lightest) */}
          <Area type="monotone" dataKey="p5" stackId="band95" stroke="none" fill="transparent" />
          <Area type="monotone" dataKey="band_5_95" stackId="band95" stroke="none" fill="#3b82f6" fillOpacity={0.08} />

          {/* 10-90 ribbon */}
          <Area type="monotone" dataKey="p10" stackId="band90" stroke="none" fill="transparent" />
          <Area type="monotone" dataKey="band_10_90" stackId="band90" stroke="none" fill="#3b82f6" fillOpacity={0.18} />

          {/* 25-75 ribbon (darkest) */}
          <Area type="monotone" dataKey="p25" stackId="band75" stroke="none" fill="transparent" />
          <Area type="monotone" dataKey="band_25_75" stackId="band75" stroke="none" fill="#3b82f6" fillOpacity={0.30} />

          {/* Median line */}
          <Line type="monotone" dataKey="p50" stroke="#60a5fa" strokeWidth={2.5} dot={false} name="Median" />
        </ComposedChart>
      </ResponsiveContainer>
      <p className="text-xs text-muted mt-2">
        Shaded bands: 25-75 percentile (darkest), 10-90, 5-95 (lightest). Log scale.
      </p>
    </div>
  );
}
