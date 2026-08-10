"use client";

import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";

/**
 * One place that knows about GSAP.
 *
 * Registration happens at module scope, which is safe because `registerPlugin`
 * and `defaults` touch no DOM — important, since a "use client" module is still
 * executed during the server render. Nothing else in this file may reference
 * `window` for the same reason.
 *
 * Two rules hold everywhere motion is used in this app:
 *
 * 1. Always animate *from* the finished state, never *to* it. No element starts
 *    life at `opacity-0` waiting for a tween to rescue it. If GSAP fails to
 *    load, a tween is interrupted, or someone has asked for reduced motion, the
 *    content is simply there. This is a tool people run from a script on their
 *    own laptop; a blank page because an animation did not fire is not a
 *    trade-off worth making for a fade.
 *
 * 2. Every number that is animated also exists as plain text. The motion is the
 *    reward, never the information.
 */
gsap.registerPlugin(useGSAP, ScrollTrigger);

gsap.defaults({ ease: "power3.out", duration: 0.26 });

export const DUR = {
  fast: 0.15,
  base: 0.26,
  /** The card's arc from a row into the counter. Long enough to follow. */
  flight: 0.52,
} as const;

/** 40ms between rows. Below ~30 it reads as one blur, above ~50 as a queue. */
export const STAGGER = 0.04;

export const EASE = {
  paper: "power3.out",
  flight: "power3.inOut",
} as const;

/** Fires only when the user has not asked for less motion. */
export const OK = "(prefers-reduced-motion: no-preference)";

export { gsap, useGSAP, ScrollTrigger };
