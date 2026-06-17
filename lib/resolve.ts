export type ResolvedSymbol = {
  yahoo: string;
  name: string;
  isin?: string;
  wkn?: string;
  currency?: string;
  exchange?: string;
  type?: string;
  source: "figi" | "yahoo-search" | "direct";
};

const memo = new Map<string, { at: number; value: ResolvedSymbol | null }>();
const TTL_MS = 24 * 60 * 60 * 1000;

const HEADERS = {
  "User-Agent": "Mozilla/5.0",
  "Accept": "application/json",
};

const ISIN_RE = /^[A-Z]{2}[A-Z0-9]{9}\d$/i;
const WKN_RE = /^[A-Z0-9]{6}$/i;
const YAHOO_SYM_RE = /^[A-Z0-9][A-Z0-9.\-_]{0,14}$/i;

// FIGI exchCode → Yahoo symbol suffix (preference order)
const FIGI_TO_YAHOO_SUFFIX: Record<string, string> = {
  GR: ".DE",   // Xetra
  GY: ".DE",   // Frankfurt
  GF: ".F",    // Frankfurt floor
  GH: ".HM",   // Hamburg
  GM: ".MU",   // Munich
  GD: ".DU",   // Düsseldorf
  GB: ".BE",   // Berlin
  GS: ".SG",   // Stuttgart
  LN: ".L",    // London
  US: "",      // US composite
  UN: "",      // NYSE
  UQ: "",      // Nasdaq
  UR: "",      // ARCA
  FP: ".PA",   // Paris
  IM: ".MI",   // Milan
  NA: ".AS",   // Amsterdam
  SS: ".ST",   // Stockholm
  SW: ".SW",   // Swiss
  SE: ".VX",   // Swiss virtx
  SM: ".MC",   // Madrid
  IR: ".IR",   // Ireland
};
const EXCH_PREF = ["GR", "GY", "LN", "NA", "SW", "FP", "IM", "GS", "GF", "GH", "GM", "GD", "GB", "US", "UN", "UQ"];

async function figiMapping(idType: "ID_WERTPAPIER" | "ID_ISIN", idValue: string): Promise<any[]> {
  try {
    const r = await fetch("https://api.openfigi.com/v3/mapping", {
      method: "POST",
      headers: { ...HEADERS, "Content-Type": "application/json" },
      body: JSON.stringify([{ idType, idValue }]),
    });
    if (!r.ok) return [];
    const j = await r.json() as any;
    return j?.[0]?.data ?? [];
  } catch { return []; }
}

async function yahooSearch(q: string): Promise<any[]> {
  try {
    const r = await fetch(
      `https://query2.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(q)}&newsCount=0&listsCount=0`,
      { headers: HEADERS, cache: "no-store" }
    );
    if (!r.ok) return [];
    const j = await r.json() as any;
    return Array.isArray(j?.quotes) ? j.quotes : [];
  } catch { return []; }
}

async function verifyChart(symbol: string): Promise<{ ok: boolean; currency?: string; name?: string }> {
  try {
    const r = await fetch(
      `https://query2.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=1mo&interval=1d`,
      { headers: HEADERS, cache: "no-store" }
    );
    if (!r.ok) return { ok: false };
    const j = await r.json() as any;
    const res = j?.chart?.result?.[0];
    const ts: number[] | undefined = res?.timestamp;
    const closes: (number | null)[] | undefined =
      res?.indicators?.adjclose?.[0]?.adjclose ?? res?.indicators?.quote?.[0]?.close;
    const points = (ts && closes) ? closes.filter((c) => c != null && !Number.isNaN(c as number)).length : 0;
    return { ok: points >= 5, currency: res?.meta?.currency, name: res?.meta?.longName ?? res?.meta?.shortName };
  } catch { return { ok: false }; }
}

function figiCandidatesToYahooSymbols(figiRows: any[]): { sym: string; ticker: string; exch: string; name: string }[] {
  const out: { sym: string; ticker: string; exch: string; name: string }[] = [];
  const sorted = [...figiRows].sort((a, b) => {
    const ai = EXCH_PREF.indexOf(a.exchCode);
    const bi = EXCH_PREF.indexOf(b.exchCode);
    return (ai < 0 ? 99 : ai) - (bi < 0 ? 99 : bi);
  });
  for (const row of sorted) {
    const t = String(row?.ticker ?? "").trim();
    const exch = String(row?.exchCode ?? "");
    const name = String(row?.name ?? "");
    if (!t) continue;
    const suffix = FIGI_TO_YAHOO_SUFFIX[exch];
    if (suffix === undefined) continue;
    out.push({ sym: t + suffix, ticker: t, exch, name });
  }
  return out;
}

export async function resolveSymbol(rawQuery: string): Promise<ResolvedSymbol | null> {
  const q = rawQuery.trim();
  if (!q) return null;
  const key = q.toUpperCase();
  const cached = memo.get(key);
  if (cached && Date.now() - cached.at < TTL_MS) return cached.value;

  const isIsin = ISIN_RE.test(q);
  const isWkn = !isIsin && WKN_RE.test(q);

  // 1) If query already looks like a Yahoo symbol with suffix or is a known ticker — try direct
  if (!isIsin && !isWkn && YAHOO_SYM_RE.test(q)) {
    const v = await verifyChart(q.toUpperCase());
    if (v.ok) {
      const value: ResolvedSymbol = { yahoo: q.toUpperCase(), name: v.name ?? q.toUpperCase(), currency: v.currency, source: "direct" };
      memo.set(key, { at: Date.now(), value });
      return value;
    }
  }

  // 2) FIGI lookup for ISIN or WKN
  let figiRows: any[] = [];
  if (isIsin) figiRows = await figiMapping("ID_ISIN", q.toUpperCase());
  else if (isWkn) figiRows = await figiMapping("ID_WERTPAPIER", q.toUpperCase());

  for (const cand of figiCandidatesToYahooSymbols(figiRows).slice(0, 12)) {
    const v = await verifyChart(cand.sym);
    if (v.ok) {
      const value: ResolvedSymbol = {
        yahoo: cand.sym,
        name: v.name ?? cand.name ?? cand.sym,
        isin: isIsin ? q.toUpperCase() : undefined,
        wkn: isWkn ? q.toUpperCase() : undefined,
        currency: v.currency,
        exchange: cand.exch,
        source: "figi",
      };
      memo.set(key, { at: Date.now(), value });
      return value;
    }
  }

  // 3) Yahoo search fallback (handles names like "Apple", "Vanguard FTSE", or weird tickers)
  const quotes = await yahooSearch(q);
  const ranked = [...quotes].sort((a, b) => {
    const ax = ["GER", "STU", "FRA", "EBS", "AMS", "LSE", "NMS", "NYQ", "NGM"].indexOf(String(a?.exchange ?? ""));
    const bx = ["GER", "STU", "FRA", "EBS", "AMS", "LSE", "NMS", "NYQ", "NGM"].indexOf(String(b?.exchange ?? ""));
    return (ax < 0 ? 99 : ax) - (bx < 0 ? 99 : bx);
  });

  for (const cand of ranked.slice(0, 8)) {
    const sym = String(cand?.symbol ?? "");
    if (!sym) continue;
    const v = await verifyChart(sym);
    if (v.ok) {
      const value: ResolvedSymbol = {
        yahoo: sym,
        name: v.name ?? String(cand?.longname ?? cand?.shortname ?? sym),
        isin: isIsin ? q.toUpperCase() : undefined,
        wkn: isWkn ? q.toUpperCase() : undefined,
        currency: v.currency,
        exchange: cand?.exchange,
        type: cand?.quoteType,
        source: "yahoo-search",
      };
      memo.set(key, { at: Date.now(), value });
      return value;
    }
  }

  memo.set(key, { at: Date.now(), value: null });
  return null;
}
