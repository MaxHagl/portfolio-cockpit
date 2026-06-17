import { NextRequest, NextResponse } from "next/server";
import { getPriceSeries } from "@/lib/prices";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest, { params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  const sym = decodeURIComponent(symbol);
  const yahoo = req.nextUrl.searchParams.get("yahoo") ?? undefined;
  const series = await getPriceSeries(sym, yahoo);
  return NextResponse.json(series);
}
