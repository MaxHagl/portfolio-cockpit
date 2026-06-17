import { lookThroughThemes, themeWeightsCoverage } from "@/lib/lookthrough";

const THEME_ICON: Record<string, string> = {
  "AI Infrastructure":                            "🧠",
  "AI Supporting (semi eq, networking, memory)":  "⚙️",
  "Cloud Hyperscalers":                           "☁️",
  "SaaS / Application Software":                  "💾",
  "Cybersecurity":                                "🔒",
  "E-commerce / Internet Retail":                 "🛒",
  "Social Media & Digital Ads":                   "📱",
  "Consumer Tech Hardware":                       "📦",
  "Electric Vehicles & Mobility":                 "🚗",
  "Robotics & Automation":                        "🤖",
  "Quantum / Next-gen Compute":                   "🧮",
  "Biotech & Drug Discovery":                     "🧬",
  "GLP-1 / Obesity Drugs":                        "💊",
  "Defense & Aerospace":                          "🛡️",
  "Renewable / Clean Energy":                     "🌱",
  "Luxury Consumer":                              "💎",
  "Banks (legacy)":                               "🏦",
  "Big Oil & Fossil Fuels":                       "🛢️",
  "REITs / Real Estate":                          "🏢",
};

export default function LookThroughThemes({ minWeight = 0.01 }: { minWeight?: number }) {
  const themes = lookThroughThemes().filter((t) => t.weight >= minWeight);
  const coverage = themeWeightsCoverage();
  const eur = (n: number) => n.toLocaleString("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
  const pct = (n: number) => `${(n * 100).toFixed(2)}%`;

  return (
    <div>
      <p className="text-xs text-muted mb-3">
        Thematic exposure aggregated across all funds (look-through). Themes intentionally overlap — same stock can sit in multiple themes (e.g., NVDA = AI Infrastructure + AI Supporting), so sum across themes exceeds 100%.
        Coverage: {coverage.fundsWithData}/{coverage.totalFunds} funds tagged. Weights below {pct(minWeight)} hidden.
      </p>
      {themes.length === 0 ? (
        <div className="text-sm text-muted">No theme exceeds {pct(minWeight)} of portfolio.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted border-b border-zinc-800">
                <th className="py-2 pr-3">Theme</th>
                <th className="py-2 pr-3 text-right tabular-nums">Look-through weight</th>
                <th className="py-2 pr-3 text-right tabular-nums">Amount (EUR)</th>
                <th className="py-2 text-left">Comes from</th>
              </tr>
            </thead>
            <tbody>
              {themes.map((t) => (
                <tr key={t.theme} className="border-b border-zinc-900">
                  <td className="py-2 pr-3">
                    <span className="mr-2">{THEME_ICON[t.theme] ?? "•"}</span>
                    <span className="font-medium">{t.theme}</span>
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums font-medium">{pct(t.weight)}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{eur(t.eur)}</td>
                  <td className="py-2 text-xs text-muted">
                    {t.breakdown
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
          Theme tags are editorial (assigned per-fund based on top-holding composition). As of: {coverage.asOfDates.join("; ")}.
        </p>
      )}
    </div>
  );
}
