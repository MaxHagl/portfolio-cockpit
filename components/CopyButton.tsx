"use client";
import { useState } from "react";

export default function CopyButton({ value, label }: { value: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      className="chip hover:bg-line hover:text-ink transition cursor-pointer"
      onClick={async () => {
        try { await navigator.clipboard.writeText(value); setDone(true); setTimeout(()=>setDone(false), 1200); } catch {}
      }}
      title={`Copy ${value}`}
    >
      <span className="font-mono">{label ?? value}</span>
      <span className="text-[10px] text-muted">{done ? "✓" : "⧉"}</span>
    </button>
  );
}
