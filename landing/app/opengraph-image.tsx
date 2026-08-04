import { ImageResponse } from "next/og";

import { copy } from "@/lib/copy";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = copy.meta.tagline;

/**
 * The card a link to this page unfurls into.
 *
 * Drawn with ImageResponse rather than exported from a design tool, the same way
 * app/icon.tsx is, so the mark cannot drift out of step with the site and there
 * is no binary in the repo to keep in sync.
 *
 * Black and white, because the page is. System fonts only: loading Outfit here
 * would mean fetching and embedding it on every card render, and at this size
 * the difference is not worth the cold start.
 */
export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          background: "#000",
          color: "#fff",
          padding: "0 90px",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", position: "relative" }}>
          <span
            style={{
              fontSize: 92,
              fontWeight: 700,
              fontFamily: "monospace",
              letterSpacing: "-0.02em",
            }}
          >
            unemployed
          </span>
          {/* The strike over "un", sized off the same 92px mark. */}
          <div
            style={{
              position: "absolute",
              left: 2,
              width: 108,
              top: 62,
              height: 7,
              background: "#fff",
            }}
          />
        </div>

        <div style={{ display: "flex", fontSize: 44, lineHeight: 1.25, marginTop: 34 }}>
          {copy.hero.tagline}
        </div>
        <div style={{ display: "flex", fontSize: 44, lineHeight: 1.25, opacity: 0.5 }}>
          {copy.hero.taglineEmphasis}
        </div>

        <div style={{ display: "flex", fontSize: 26, opacity: 0.6, marginTop: 46 }}>
          {copy.hero.badge}
        </div>
      </div>
    ),
    size,
  );
}
