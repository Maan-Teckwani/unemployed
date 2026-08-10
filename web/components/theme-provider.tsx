"use client";

import { ThemeProvider as NextThemes } from "next-themes";

/**
 * The dark palette has been sitting in globals.css since the app was scaffolded
 * with nothing mounted to switch it on, so every `dark:` class in the codebase
 * has been dead CSS. This is the switch.
 *
 * `attribute="class"` because the dark variant is declared as
 * `@custom-variant dark (&:is(.dark *))` — it wants a class, not a data
 * attribute. `disableTransitionOnChange` stops every colour transition in the
 * app from firing at once when you flip the theme, which reads as a smear
 * rather than a switch.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemes
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      {children}
    </NextThemes>
  );
}
