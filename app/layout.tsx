import "./globals.css";
import Link from "next/link";

export const metadata = {
  title: "Portfolio Decision Cockpit",
  description: "Local research site for portfolio decisions.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="border-b border-line bg-panel/80 backdrop-blur sticky top-0 z-10">
          <div className="max-w-6xl mx-auto px-5 py-3 flex items-center justify-between">
            <Link href="/" className="text-ink font-semibold tracking-tight">
              Portfolio <span className="text-accent">Cockpit</span>
            </Link>
            <nav className="flex gap-1 text-sm">
              <Link href="/" className="btn">Dashboard</Link>
              <Link href="/sandbox" className="btn">Sandbox</Link>
            </nav>
          </div>
        </header>
        <main className="max-w-6xl mx-auto px-5 py-6">{children}</main>
        <footer className="max-w-6xl mx-auto px-5 py-8 text-xs text-muted">
          Educational research tool — not financial advice. Past performance ≠ future returns.
        </footer>
      </body>
    </html>
  );
}
