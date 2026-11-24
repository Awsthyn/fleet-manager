import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { WakeGate } from "@/components/wake-gate";

import "./globals.css";

const geistSans = Geist({ variable: "--font-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "Fleet Manager", template: "%s · Fleet Manager" },
  description: "Fleet management dashboard: vehicles, drivers, maintenance and costs.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <WakeGate />
        {children}
      </body>
    </html>
  );
}
