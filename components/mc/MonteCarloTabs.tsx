"use client";
import { useState, type ReactNode } from "react";

interface Props {
  today: ReactNode;
  accumulation: ReactNode;
  retirement: ReactNode;
}

export default function MonteCarloTabs({ today, accumulation, retirement }: Props) {
  const [tab, setTab] = useState<"today" | "accumulation" | "retirement">("today");
  return (
    <div>
      <div className="flex gap-1 border-b border-zinc-800 mb-5">
        {[
          { id: "today" as const, label: "Today (v1)" },
          { id: "accumulation" as const, label: "Accumulation (DCA + realism)" },
          { id: "retirement" as const, label: "Retirement (withdrawal phase)" },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-medium transition border-b-2 -mb-px ${
              tab === t.id
                ? "border-blue-400 text-zinc-100"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div>
        {tab === "today" && today}
        {tab === "accumulation" && accumulation}
        {tab === "retirement" && retirement}
      </div>
    </div>
  );
}
