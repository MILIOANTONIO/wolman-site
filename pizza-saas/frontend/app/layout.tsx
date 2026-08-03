import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Pizza SaaS",
  description: "Ordini e prenotazioni con agente AI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="it">
      <body>{children}</body>
    </html>
  );
}
