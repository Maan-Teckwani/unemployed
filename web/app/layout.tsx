import type { Metadata, Viewport } from "next";
import { Instrument_Sans, Instrument_Serif, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { PipelineProvider } from "@/components/pipeline/pipeline-provider";
import { SiteNav } from "@/components/site-nav";
import { StackProvider } from "@/components/stack/stack-provider";
import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "@/components/ui/sonner";

// The same three faces as the landing page, so the tool and the page it is
// announced on look like one product.
const display = Instrument_Serif({
  variable: "--font-display",
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  display: "swap",
});
const body = Instrument_Sans({
  variable: "--font-body",
  subsets: ["latin"],
  display: "swap",
});
const code = JetBrains_Mono({
  variable: "--font-code",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "unemployed",
  description: "Discover jobs, tailor resumes, and prepare applications faster.",
};

export const viewport: Viewport = {
  // Both, and in this order, so the browser paints its own chrome to match
  // whichever theme the inline script settles on before first paint.
  colorScheme: "light dark",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0a0a" },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    // suppressHydrationWarning because next-themes writes the theme class onto
    // this element from an inline script before React runs. Without it, React
    // sees a mismatch and re-renders from the nearest boundary, throwing away
    // the very correction that stops the page flashing the wrong theme.
    <html
      lang="en"
      suppressHydrationWarning
      className={`${display.variable} ${body.variable} ${code.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <ThemeProvider>
          <StackProvider>
            <PipelineProvider>
              <SiteNav />
              <main className="flex-1 w-full max-w-5xl mx-auto px-6 py-10">
                {children}
              </main>
              <Toaster />
              {/* Where a thrown card flies. Outside every scroll container and
                  above everything, so the flight is never clipped by a card it
                  happens to start inside. */}
              <div
                id="flip-layer"
                aria-hidden
                className="pointer-events-none fixed inset-0 z-[60]"
              />
            </PipelineProvider>
          </StackProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
