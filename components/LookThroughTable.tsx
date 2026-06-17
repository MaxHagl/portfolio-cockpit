import { lookThroughPositions, topHoldingsCoverage } from "@/lib/lookthrough";

export default function LookThroughTable({ minWeight = 0.03 }: { minWeight?: number }) {
  const positions = lookThroughPositions().filter((p) => p.weight >= minWeight);
  const coverage = topHoldingsCoverage();
  const eur = (n: number) => n.toLocaleString("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
  const pct = (n: number) => `${(n * 100).toFixed(2)}%`;

  return (
    <div>
      <p className="text-xs text-muted mb-3">
        Single-stock exposure aggregated across all funds (look-through). Weights below {pct(minWeight)} hidden.
        Coverage: {coverage.fundsWithData}/{coverage.totalFunds} funds have top-holdings data.
      </p>
      {positions.length === 0 ? (
        <div className="text-sm text-muted">No single stock exceeds {pct(minWeight)} of portfolio.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted border-b border-zinc-800">
                <th className="py-2 pr-3">Stock</th>
                <th className="py-2 pr-3 text-right tabular-nums">Look-through weight</th>
                <th className="py-2 pr-3 text-right tabular-nums">Amount (EUR)</th>
                <th className="py-2 text-left">Comes from</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => (
                <tr key={p.ticker} className="border-b border-zinc-900">
                  <td className="py-2 pr-3">
                    <div className="font-medium">{p.name}</div>
                    <div className="text-xs text-muted">{p.ticker}</div>
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums font-medium">{pct(p.weight)}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{eur(p.eur)}</td>
                  <td className="py-2 text-xs text-muted">
                    {p.breakdown
                      .sort((a, b) => b.contribution - a.contribution)
                      .map((b) => `${b.holdingShortName} ${pct(b.contribution)}`)
                      .join(" + ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {coverage.asOfDates.length > 0 && (
        <p className="text-xs text-muted mt-3">
          Fund weights approximate. As of: {coverage.asOfDates.join("; ")}.
        </p>
      )}
    </div>
  );
}
