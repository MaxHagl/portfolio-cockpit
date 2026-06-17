import { lookThroughIndustries, industryWeightsCoverage } from "@/lib/lookthrough";

const SECTOR_COLOR: Record<string, string> = {
  "Information Technology":     "bg-purple-500/10 text-purple-300",
  "Communication Services":     "bg-fuchsia-500/10 text-fuchsia-300",
  "Consumer Discretionary":     "bg-pink-500/10 text-pink-300",
  "Consumer Staples":           "bg-amber-500/10 text-amber-300",
  "Financials":                 "bg-emerald-500/10 text-emerald-300",
  "Health Care":                "bg-teal-500/10 text-teal-300",
  "Industrials":                "bg-blue-500/10 text-blue-300",
  "Energy":                     "bg-orange-500/10 text-orange-300",
  "Materials":                  "bg-yellow-500/10 text-yellow-300",
  "Real Estate":                "bg-stone-500/10 text-stone-300",
  "Utilities":                  "bg-sky-500/10 text-sky-300",
};

export default function LookThroughIndustries({ minWeight = 0.01 }: { minWeight?: number }) {
  const industries = lookThroughIndustries().filter((i) => i.weight >= minWeight);
  const coverage = industryWeightsCoverage();
  const eur = (n: number) => n.toLocaleString("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
  const pct = (n: number) => `${(n * 100).toFixed(2)}%`;

  return (
    <div>
      <p className="text-xs text-muted mb-3">
        Industry exposure aggregated across all funds (look-through, GICS Industry level).
        Weights below {pct(minWeight)} hidden. Coverage: {coverage.fundsWithData}/{coverage.totalFunds} funds.
      </p>
      {industries.length === 0 ? (
        <div className="text-sm text-muted">No industry exceeds {pct(minWeight)} of portfolio.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted border-b border-zinc-800">
                <th className="py-2 pr-3">Industry</th>
                <th className="py-2 pr-3">Sector</th>
                <th className="py-2 pr-3 text-right tabular-nums">Look-through weight</th>
                <th className="py-2 pr-3 text-right tabular-nums">Amount (EUR)</th>
                <th className="py-2 text-left">Comes from</th>
              </tr>
            </thead>
            <tbody>
              {industries.map((i) => (
                <tr key={i.industry} className="border-b border-zinc-900">
                  <td className="py-2 pr-3 font-medium">{i.industry}</td>
                  <td className="py-2 pr-3">
                    <span className={`text-xs px-2 py-0.5 rounded ${SECTOR_COLOR[i.sector] ?? "bg-zinc-800 text-zinc-300"}`}>
                      {i.sector}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums font-medium">{pct(i.weight)}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{eur(i.eur)}</td>
                  <td className="py-2 text-xs text-muted">
                    {i.breakdown
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
          Fund industry weights approximate (factsheet-level). As of: {coverage.asOfDates.join("; ")}.
        </p>
      )}
    </div>
  );
}
