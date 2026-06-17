import { lookThroughCountries, countryWeightsCoverage } from "@/lib/lookthrough";

const FLAG: Record<string, string> = {
  US: "🇺🇸", JP: "🇯🇵", GB: "🇬🇧", CN: "🇨🇳", CA: "🇨🇦", FR: "🇫🇷", CH: "🇨🇭",
  DE: "🇩🇪", IN: "🇮🇳", TW: "🇹🇼", AU: "🇦🇺", KR: "🇰🇷", NL: "🇳🇱", IT: "🇮🇹",
  ES: "🇪🇸", BR: "🇧🇷", SE: "🇸🇪", IL: "🇮🇱", SA: "🇸🇦", ZA: "🇿🇦", MX: "🇲🇽",
  ID: "🇮🇩", AE: "🇦🇪", PL: "🇵🇱",
};

export default function LookThroughCountries({ minWeight = 0.01 }: { minWeight?: number }) {
  const countries = lookThroughCountries().filter((c) => c.weight >= minWeight);
  const coverage = countryWeightsCoverage();
  const eur = (n: number) => n.toLocaleString("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
  const pct = (n: number) => `${(n * 100).toFixed(2)}%`;

  return (
    <div>
      <p className="text-xs text-muted mb-3">
        Country exposure aggregated across all funds (look-through). Weights below {pct(minWeight)} hidden.
        Coverage: {coverage.fundsWithData}/{coverage.totalFunds} funds have country data.
      </p>
      {countries.length === 0 ? (
        <div className="text-sm text-muted">No country exceeds {pct(minWeight)} of portfolio.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted border-b border-zinc-800">
                <th className="py-2 pr-3">Country</th>
                <th className="py-2 pr-3 text-right tabular-nums">Look-through weight</th>
                <th className="py-2 pr-3 text-right tabular-nums">Amount (EUR)</th>
                <th className="py-2 text-left">Comes from</th>
              </tr>
            </thead>
            <tbody>
              {countries.map((c) => (
                <tr key={c.code} className="border-b border-zinc-900">
                  <td className="py-2 pr-3">
                    <span className="mr-2">{FLAG[c.code] ?? ""}</span>
                    <span className="font-medium">{c.name}</span>
                    <span className="text-xs text-muted ml-2">{c.code}</span>
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums font-medium">{pct(c.weight)}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{eur(c.eur)}</td>
                  <td className="py-2 text-xs text-muted">
                    {c.breakdown
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
          Fund country weights approximate. As of: {coverage.asOfDates.join("; ")}.
        </p>
      )}
    </div>
  );
}
