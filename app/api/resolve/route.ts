import { NextRequest, NextResponse } from "next/server";
import { resolveSymbol } from "@/lib/resolve";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get("q") ?? "";
  if (!q.trim()) return NextResponse.json({ error: "missing q" }, { status: 400 });
  const value = await resolveSymbol(q);
  if (!value) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json(value);
}
