import type { Metadata } from "next";
import { Inter, Outfit, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { MotionProvider } from "@/components/motion-provider";
import { copy } from "@/lib/copy";
import { SITE_URL } from "@/lib/site";
import { Analytics } from "@vercel/analytics/next"

/**
 * Modern clean fonts. Outfit for headings, Inter for body text.
 */
const display = Outfit({
  variable: "--font-display",
  subsets: ["latin"],
});

const body = Inter({
  variable: "--font-body",
  subsets: ["latin"],
});

const code = JetBrains_Mono({
  variable: "--font-code",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  // Without a base, every relative image and canonical in the tree resolves
  // against nothing and Next warns on each one.
  metadataBase: new URL(SITE_URL),
  title: {
    default: copy.meta.title,
    // Pages set a plain title and get the wordmark appended, so a tab and a
    // search result both say which site they belong to.
    template: `%s | ${copy.meta.title}`,
  },
  description: copy.meta.description,
  applicationName: copy.meta.title,
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: copy.meta.title,
    title: copy.meta.tagline,
    description: copy.meta.description,
    url: "/",
  },
  twitter: {
    card: "summary_large_image",
    title: copy.meta.tagline,
    description: copy.meta.description,
  },
};

/**
 * Sets the theme class before the first paint.
 *
 * This has to be a blocking inline script rather than an effect. React runs
 * effects after the browser has already painted, so doing it there means every
 * dark mode reader gets one white flash on every navigation.
 *
 * A stored choice wins over the operating system, because someone who picked
 * light on a dark machine meant it.
 */
const THEME_SCRIPT = `try{var s=localStorage.getItem("theme");if(s==="dark"||(!s&&matchMedia("(prefers-color-scheme: dark)").matches))document.documentElement.classList.add("dark")}catch(e){}`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    // The script mutates <html> before React hydrates, so React would otherwise
    // report the class it did not render as a mismatch.
    <html
      lang="en"
      suppressHydrationWarning
      className={`${display.variable} ${body.variable} ${code.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="min-h-full bg-background text-foreground">
        <MotionProvider>{children}</MotionProvider>
        <Analytics />
      </body>
    </html>
  );
}
