import type { Metadata } from "next";
import "./globals.css";
import { ClientProviders } from "./providers";

export const metadata: Metadata = {
  title: "Trader — TFSA Portfolio Dashboard",
  description: "Trading signals, portfolio tracking, and P&L analysis for Canadian TFSA",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">
        <ClientProviders>{children}</ClientProviders>
      </body>
    </html>
  );
}
