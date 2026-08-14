import type { Metadata } from "next";
import { Instrument_Serif, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/Providers";
import { Sidebar } from "@/components/Sidebar";
import { MobileNav } from "@/components/MobileNav";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const serif = Instrument_Serif({
  variable: "--font-serif",
  weight: "400",
  subsets: ["latin"],
});
const mono = JetBrains_Mono({ variable: "--font-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "GroundedDocs",
  description:
    "Hybrid retrieval-augmented generation for enterprise documentation, with verified citations and full observability.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${inter.variable} ${serif.variable} ${mono.variable} min-h-screen font-sans antialiased`}
      >
        <Providers>
          <MobileNav />
          <div className="flex min-h-screen">
            <Sidebar />
            <main className="min-w-0 flex-1 lg:pl-60">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
