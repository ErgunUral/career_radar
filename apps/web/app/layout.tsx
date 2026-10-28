import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CareerRadar AI",
  description: "CV ayrıştırma, profil doğrulama ve watcher yönetimi için CareerRadar AI arayüzü",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="tr">
      <body>{children}</body>
    </html>
  );
}
