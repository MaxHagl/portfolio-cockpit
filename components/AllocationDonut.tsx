"use client";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";

export interface Slice { id: string; label: string; value: number; color: string }

export default function AllocationDonut({ data, totalLabel }: { data: Slice[]; totalLabel?: string }) {
  return (
    <div className="relative h-72">
      <ResponsiveContainer>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="label" innerRadius="60%" outerRadius="90%" stroke="#0b0d10" strokeWidth={2} paddingAngle={1}>
            {data.map((s) => <Cell key={s.id} fill={s.color} />)}
          </Pie>
          <Tooltip
            contentStyle={{ background: "#13161b", border: "1px solid #262b34", borderRadius: 8, fontSize: 12 }}
            formatter={(v: any, n: any) => [`${(Number(v)*100).toFixed(1)}%`, n]}
          />
        </PieChart>
      </ResponsiveContainer>
      {totalLabel && (
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <div className="text-xs uppercase tracking-wider text-muted">Total</div>
          <div className="text-2xl font-semibold">{totalLabel}</div>
        </div>
      )}
    </div>
  );
}
