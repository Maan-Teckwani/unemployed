"use client";

import { useRef } from "react";
import { gsap, OK, useGSAP } from "@/lib/motion";

/**
 * A number that rolls when it changes.
 *
 * Only the digits that actually changed move — rolling all of "99 → 100" at
 * once looks like the number was replaced, while rolling just the digit that
 * ticked looks like it counted.
 *
 * The animated digits are hidden from assistive tech and the real value is
 * carried by an `sr-only` span, so nothing about this number depends on the
 * animation running, or on GSAP loading at all.
 */
export function Odometer({
  value,
  className = "",
}: {
  value: number;
  className?: string;
}) {
  const scope = useRef<HTMLSpanElement>(null);
  const previous = useRef(value);

  useGSAP(
    () => {
      const from = String(previous.current);
      const to = String(value);
      previous.current = value;
      if (from === to) return;

      const mm = gsap.matchMedia();
      mm.add(OK, () => {
        const digits = gsap.utils.toArray<HTMLElement>("[data-digit]");
        // Right-aligned comparison: "9"→"10" changes every column, but
        // "23"→"24" should only move the last one.
        const padded = from.padStart(to.length, " ");
        const changed = digits.filter((_, i) => padded[i] !== to[i]);
        gsap.from(changed, {
          yPercent: 55,
          opacity: 0,
          duration: 0.24,
          stagger: 0.03,
          ease: "power3.out",
        });
      });
      return () => mm.revert();
    },
    { scope, dependencies: [value] },
  );

  return (
    <span ref={scope} className={className}>
      <span className="sr-only">{value}</span>
      <span aria-hidden className="inline-flex overflow-hidden">
        {String(value).split("").map((d, i) => (
          <span key={`${i}-${d}`} data-digit className="inline-block">
            {d}
          </span>
        ))}
      </span>
    </span>
  );
}
