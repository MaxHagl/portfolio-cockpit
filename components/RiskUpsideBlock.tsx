export default function RiskUpsideBlock({ risk, upside }: { risk: string[]; upside: string[] }) {
  return (
    <div className="grid md:grid-cols-2 gap-3">
      <div className="card-sub">
        <div className="h-section text-danger">Risk</div>
        <ul className="space-y-1.5 text-sm">
          {risk.map((r, i) => (
            <li key={i} className="flex gap-2"><span className="text-danger">▸</span><span>{r}</span></li>
          ))}
        </ul>
      </div>
      <div className="card-sub">
        <div className="h-section text-accent">Upside</div>
        <ul className="space-y-1.5 text-sm">
          {upside.map((u, i) => (
            <li key={i} className="flex gap-2"><span className="text-accent">▸</span><span>{u}</span></li>
          ))}
        </ul>
      </div>
    </div>
  );
}
