import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import SmoothScroller from "@/components/SmoothScroller";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "DataSentinel — AI-Powered Dataset Observability",
  description:
    "Secure, local-first anomaly detection and data cleaning platform for enterprise data teams.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // REMOVED 'h-full'
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} antialiased dark`}
    >
      {/* REMOVED 'min-h-full' */}
      <body className="flex flex-col bg-black text-white selection:bg-purple-500/30">
        <SmoothScroller>{children}</SmoothScroller>
      </body>
    </html>
  );
}