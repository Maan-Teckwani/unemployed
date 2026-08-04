"use client";

import { MotionConfig } from "framer-motion";

import { SmoothScroll } from "./smooth-scroll";

/**
 * Everything that moves, and the one setting that turns it all off.
 *
 * `reducedMotion="user"` is the piece that was missing. The reveals used to be
 * CSS with a prefers-reduced-motion block; moving them to framer-motion moved
 * them out from under that block, and nothing replaced it, so the page animated
 * at people who had asked it not to. Framer only honours the setting when it is
 * told to, which is what this does for every motion component at once.
 */
export function MotionProvider({ children }: { children: React.ReactNode }) {
  return (
    <MotionConfig reducedMotion="user">
      <SmoothScroll />
      {children}
    </MotionConfig>
  );
}
