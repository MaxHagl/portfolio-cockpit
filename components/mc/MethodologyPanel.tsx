"use client";
import { useState } from "react";
import type { MonteCarloOutput } from "@/lib/monteCarlo";

export default function MethodologyPanel({ mc }: { mc: MonteCarloOutput }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button onClick={() => setOpen(!open)} className="text-sm text-blue-400 hover:underline">
        {open ? "▼ Hide methodology" : "▶ Show methodology + diagnostics"}
      </button>
      {open && (
        <div className="mt-3 space-y-4 text-sm">
          <div>
            <div className="font-medium mb-1">Engines</div>
            <ul className="list-disc pl-5 space-y-1 text-zinc-300">
              <li><span className="text-zinc-100 font-medium">Stationary block bootstrap</span> ({mc.inputs.pathsBootstrap.toLocaleString()} paths): {mc.engines.bootstrap.method}. Block length: {mc.inputs.blockLengthBootstrap} days (Politis-White).</li>
              <li><span className="text-zinc-100 font-medium">Parametric multivariate Student-t</span> ({mc.inputs.pathsParametricT.toLocaleString()} paths): {mc.engines.parametricT.method}. ν = {mc.engines.parametricT.nu?.toFixed(2)}.</li>
              <li><span className="text-zinc-100 font-medium">Filtered Historical Simulation</span> ({mc.inputs.pathsFhs.toLocaleString()} paths): {mc.engines.fhs.method}. Standardized residuals bootstrapped jointly across assets.</li>
              <li><span className="text-zinc-100 font-medium">Expanding-window cross-validation</span> ({mc.inputs.pathsCv.toLocaleString()} paths × N windows): sensitivity to history sample length.</li>
            </ul>
          </div>

          <div>
            <div className="font-medium mb-1">History augmentation</div>
            <p className="text-zinc-300 mb-2">
              Active funds with short history (BGF since 2022, A3DRHJ since 2022) are augmented pre-2022 via OLS proxy regression: <code>r_native = α + β·r_proxy + ε</code>, residuals bootstrapped from native window.
            </p>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-muted border-b border-zinc-800">
                  <th className="text-left py-1">Holding</th>
                  <th className="text-left">Proxy</th>
                  <th className="text-right">EUR conv.</th>
                  <th className="text-right">Lag</th>
                  <th className="text-right">α (ann)</th>
                  <th className="text-right">β</th>
                  <th className="text-right">R²</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(mc.history.augmentation).map(([hid, f]) => (
                  <tr key={hid} className="border-b border-zinc-900">
                    <td className="py-1 font-medium">{hid}</td>
                    <td>{f.proxyId}</td>
                    <td className="text-right">{f.eurConvert ? "✓" : "—"}</td>
                    <td className="text-right tabular-nums">{f.lag}</td>
                    <td className="text-right tabular-nums">{(f.alphaAnnualized * 100).toFixed(2)}%</td>
                    <td className="text-right tabular-nums">{f.beta.toFixed(3)}</td>
                    <td className={`text-right tabular-nums ${f.r2 < 0.3 ? "text-amber-400" : ""}`}>{f.r2.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-xs text-muted mt-2">
              Low R² (amber) means the proxy explains little of native variance — pre-2022 synthetic returns
              for these funds are dominated by bootstrapped residuals rather than systematic exposure.
            </p>
          </div>

          <div>
            <div className="font-medium mb-1">Window</div>
            <p className="text-zinc-300">
              Augmented matrix: {mc.history.augmentedWindow.start} → {mc.history.augmentedWindow.end}
              {" "}({mc.history.augmentedWindow.years.toFixed(1)}y, {mc.history.augmentedWindow.days} bdays).
              Native-only: {mc.history.nativeWindow.start} → {mc.history.nativeWindow.end}
              {" "}({mc.history.nativeWindow.years.toFixed(1)}y).
            </p>
          </div>

          <div>
            <div className="font-medium mb-1">GARCH(1,1) fits</div>
            <table className="w-full text-xs">
              <thead><tr className="text-muted border-b border-zinc-800">
                <th className="text-left py-1">Asset</th><th className="text-right">α</th><th className="text-right">β</th><th className="text-right">Persistence</th>
              </tr></thead>
              <tbody>
                {mc.engines.fhs.garch?.map((g, i) => (
                  <tr key={i} className="border-b border-zinc-900">
                    <td className="py-1">{g.asset}</td>
                    <td className="text-right tabular-nums">{Number(g.alpha).toFixed(3)}</td>
                    <td className="text-right tabular-nums">{Number(g.beta).toFixed(3)}</td>
                    <td className="text-right tabular-nums">{Number(g.persistence).toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div>
            <div className="font-medium mb-1">Correlation matrix (augmented)</div>
            <table className="w-full text-xs">
              <thead><tr className="text-muted border-b border-zinc-800">
                <th></th>
                {Object.keys(mc.diagnostics.correlationAugmented).map((k) => <th key={k} className="text-right py-1">{k}</th>)}
              </tr></thead>
              <tbody>
                {Object.entries(mc.diagnostics.correlationAugmented).map(([row, cols]) => (
                  <tr key={row} className="border-b border-zinc-900">
                    <td className="py-1 font-medium">{row}</td>
                    {Object.entries(cols).map(([c, v]) => (
                      <td key={c} className="text-right tabular-nums">{(v as number).toFixed(2)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="text-xs text-muted">
            Generated {new Date(mc.generatedAt).toLocaleString("de-DE")} ·
            seed {mc.seed} ·
            compute {(mc.computeSeconds / 60).toFixed(1)} min ·
            weights hash {mc.inputs.weightsHash}
          </div>
        </div>
      )}
    </div>
  );
}
