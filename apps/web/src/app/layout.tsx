import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AVENEL — Préparation comptable",
  description: "Service de préparation des dossiers comptables mensuels pour fiduciaires marocaines",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr-MA">
      <body className="bg-paper text-ink min-h-screen">
        {children}
      </body>
    </html>
  );
}
