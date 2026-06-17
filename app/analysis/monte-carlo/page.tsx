import Link from "next/link";
import { mc } from "@/lib/monteCarlo";
import MonteCarloTabs from "@/components/mc/MonteCarloTabs";
import TodayTab from "@/components/mc/TodayTab";
import AccumulationTab from "@/components/mc/AccumulationTab";
import RetirementTab from "@/components/mc/RetirementTab";

export default function MonteCarloPage() {
  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-baseline gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">Monte Carlo analysis</h1>
          <Link href="/" className="text-sm text-blue-400 hover:underline">← back to dashboard</Link>
        </div>
        <p className="text-muted text-sm mt-1">
          {mc.inputs.horizonYears}y baseline simulation + accumulation (DCA + realism layer) + retirement (withdrawal phase).
          Click tabs to explore each.
        </p>
      </div>

      <MonteCarloTabs
        today={<TodayTab />}
        accumulation={<AccumulationTab />}
        retirement={<RetirementTab />}
      />
    </div>
  );
}
