import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "ZeroGPU Studio | Cinematic AI Video Generator",
  description: "A professional, multi-agent AI video production studio. Generate cinematic AI video using fal.ai, NVIDIA NIM, and Kling with a seamless, zero-GPU workflow.",
  openGraph: {
    title: "ZeroGPU Studio | Cinematic AI Video",
    description: "Generate cinematic AI video using a multi-agent workflow.",
    type: "website",
    locale: "en_US",
    siteName: "ZeroGPU Studio",
  },
  twitter: {
    card: "summary_large_image",
    title: "ZeroGPU Studio",
    description: "Professional AI video production at your fingertips.",
  },
};

import { Providers } from "@/components/Providers";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}
