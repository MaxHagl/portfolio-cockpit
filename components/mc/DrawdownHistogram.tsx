"use client";
import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Histogram } from "@/lib/monteCarlo";

interface Props { hist: Histogram }

export default function DrawdownHistogram({ hist }: Props) {
  const data = hist.binEdges.slice(0, -1).map((edge, i) => ({
    bin: edge,
    binCenter: (edge + hist.binEdges[i + 1]) / 2,
    count: hist.counts[i],
  }));
  const fmt = (v: number) => `${(v * 100).toFixed(0)}%`;
  return (
    <div style={{ width: "100%", height: 300 }}>
      <ResponsiveContainer>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis
            dataKey="binCenter"
            tickFormatter={fmt}
            stroke="#52525b"
          />
          <YAxis stroke="#52525b" />
          <Tooltip
            contentStyle={{ backgroundColor: "#18181b", border: "1px solid #3f3f46", borderRadius: 6 }}
            labelFormatter={(v: number) => `Max DD: ${fmt(v)}`}
            formatter={(v: number) => [`${v} paths`, "count"]}
          />
          {[-0.20, -0.30, -0.40, -0.50].map((thr) => (
            <ReferenceLine key={thr} x={thr} stroke="#a1a1aa" strokeDasharray="4 4"
                           label={{ value: `${(thr*100).toFixed(0)}%`, position: "top", fill: "#a1a1aa", fontSize: 10 }} />
          ))}
          <Bar dataKey="count" fill="#fb7185" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
