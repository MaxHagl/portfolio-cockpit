"use client";
import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Histogram } from "@/lib/monteCarlo";

interface Props {
  hist: Histogram;
  startingEur: number;
  multipliers?: number[];
  logX?: boolean;
}

export default function TerminalWealthHistogram({ hist, startingEur, multipliers = [1, 2, 3, 5, 10], logX = true }: Props) {
  const data = hist.binEdges.slice(0, -1).map((edge, i) => ({
    bin: edge,
    binCenter: (edge + hist.binEdges[i + 1]) / 2,
    count: hist.counts[i],
  }));
  const fmt = (v: number) => v.toLocaleString("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

  return (
    <div style={{ width: "100%", height: 320 }}>
      <ResponsiveContainer>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis
            dataKey="binCenter"
            scale={logX ? "log" : "linear"}
            domain={["dataMin", "dataMax"]}
            tickFormatter={fmt}
            stroke="#52525b"
            ticks={multipliers.map((m) => startingEur * m).filter((v) => v <= data[data.length - 1].binCenter * 2)}
          />
          <YAxis stroke="#52525b" />
          <Tooltip
            contentStyle={{ backgroundColor: "#18181b", border: "1px solid #3f3f46", borderRadius: 6 }}
            labelFormatter={(v: number) => `~ ${fmt(v)}`}
            formatter={(v: number) => [`${v} paths`, "count"]}
          />
          {multipliers.map((m) => (
            <ReferenceLine
              key={m}
              x={startingEur * m}
              stroke={m === 1 ? "#f87171" : "#71717a"}
              strokeDasharray={m === 1 ? "" : "4 4"}
              label={{ value: `${m}x`, position: "top", fill: "#a1a1aa", fontSize: 10 }}
            />
          ))}
          <Bar dataKey="count" fill="#60a5fa" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
