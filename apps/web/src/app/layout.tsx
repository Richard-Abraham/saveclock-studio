import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Instrument_Sans } from "next/font/google";
import type { ReactNode } from "react";

import { AppHeader } from "@/components/features/app-frame/app-header";
import { Providers } from "@/components/features/app-frame/providers";
import { RouteFocus } from "@/components/features/app-frame/route-focus";
import { SkipLink } from "@/components/features/app-frame/skip-link";
import { UnreachableBanner } from "@/components/features/health-indicator/unreachable-banner";
import { appOrigin } from "@/lib/config";
import { THEME_COLOR } from "@/styles/theme-color";

import "./globals.css";

const display = Bricolage_Grotesque({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-bricolage",
  // shortcut: one static weight (600) instead of the variable file: 22 KB vs 41 KB, so fonts fit the 70 KB budget
  // (DESIGN §3.2 budgets "Bricolage 600"). h1 is 600 not 650; upgrade if the budget allows the variable file.
  weight: "600",
});
const sans = Instrument_Sans({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-instrument",
});

export const metadata: Metadata = {
  metadataBase: new URL(appOrigin),
  title: { default: "SaveClock Studio", template: "%s · SaveClock Studio" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  colorScheme: "light dark",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: THEME_COLOR.light },
    { media: "(prefers-color-scheme: dark)", color: THEME_COLOR.dark },
  ],
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable}`}>
      <body>
        <Providers>
          <SkipLink />
          <AppHeader />
          <main
            id="main"
            tabIndex={-1}
            className="mx-auto w-full max-w-[1200px] px-4 pt-8 pb-[calc(3.25rem+env(safe-area-inset-bottom)+2rem)] md:px-6 lg:px-8 lg:pb-12"
          >
            <UnreachableBanner />
            {children}
          </main>
          <RouteFocus />
        </Providers>
      </body>
    </html>
  );
}
