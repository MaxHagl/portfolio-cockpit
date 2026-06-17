export default function MetricDelta({
  label, value, baseline, fmt, betterWhen = "higher"
}: {
  label: string; value: number; baseline: number;
  fmt: (n:number)=>string; betterWhen?: "higher"|"lower"
}) {
  const delta = value - baseline;
  const isBetter = betterWhen === "higher" ? delta > 0 : delta < 0;
  const color = Math.abs(delta) < 1e-9 ? "text-muted" : isBetter ? "text-accent" : "text-danger";
  return (
    <div className="card-sub">
      <div className="text-xs text-muted">{label}</div>
      <div className="flex items-baseline justify-between gap-2">
        <div className="text-xl font-semibold tabular-nums">{fmt(value)}</div>
        <div className={`text-xs tabular-nums ${color}`}>Δ {fmt(delta)}</div>
      </div>
      <div className="text-[11px] text-muted mt-0.5">vs baseline {fmt(baseline)}</div>
    </div>
  );
}
