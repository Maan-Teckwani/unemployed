"use client";

import { useEffect } from "react";
import Lenis from "lenis";

/**
 * Smooth scrolling, and the two things that have to happen with it.
 *
 * Lenis stops the page scrolling natively and animates the offset itself. Two
 * consequences, both handled here rather than left to be discovered:
 *
 * 1. `scroll-behavior: smooth` in the stylesheet now fights it, so the class on
 *    <html> below turns that rule off. It stays on for anyone Lenis skips.
 * 2. Anchors stop working. The browser jumps the real scroll position, which
 *    Lenis then overwrites on its next frame. So anchor clicks are intercepted
 *    and handed to Lenis, which is also the only way `scroll-mt` keeps working.
 *
 * Anyone who asked their system for less motion gets none of this. Smoothing is
 * decoration on top of an interaction the browser already does correctly, and
 * hijacking the scroll wheel is exactly what that setting is asking us not to
 * do. It is checked live rather than once, so changing the setting takes effect
 * without a reload.
 */
/**
 * The running instance, or null when smoothing is off.
 *
 * Module scope rather than context: the only other thing that needs it is the
 * nav's own scroll to top, and threading a provider through the tree for one
 * call would be more machinery than the call is worth.
 */
let instance: Lenis | null = null;

/** Scroll to the top, smoothly if Lenis is running and natively if it is not. */
export function scrollToTop() {
  if (instance) instance.scrollTo(0);
  else window.scrollTo({ top: 0, behavior: "smooth" });
}

export function SmoothScroll() {
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    let lenis: Lenis | null = null;
    let frame = 0;

    function start() {
      if (lenis) return;
      lenis = new Lenis({
        duration: 1.05,
        // Eases out hard, so it lands rather than drifts.
        easing: (t) => 1 - Math.pow(1 - t, 4),
        // Touch devices already scroll smoothly and have their own physics.
        // Overriding them makes a phone feel broken, not polished.
        smoothWheel: true,
        touchMultiplier: 1.6,
      });
      instance = lenis;
      document.documentElement.classList.add("lenis-on");

      const raf = (time: number) => {
        lenis?.raf(time);
        frame = requestAnimationFrame(raf);
      };
      frame = requestAnimationFrame(raf);
    }

    function stop() {
      cancelAnimationFrame(frame);
      lenis?.destroy();
      lenis = null;
      instance = null;
      document.documentElement.classList.remove("lenis-on");
    }

    // Same-page anchors, delegated so it covers the nav, the menu and anything
    // added later. The offset comes from the target's own scroll-mt, read back
    // off the element, so the fixed header keeps being accounted for in exactly
    // one place: the stylesheet.
    function onClick(event: MouseEvent) {
      if (!lenis || event.defaultPrevented) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;

      const anchor = (event.target as Element).closest?.("a");
      if (!(anchor instanceof HTMLAnchorElement) || anchor.target === "_blank") return;

      const url = new URL(anchor.href, window.location.href);
      if (url.origin !== window.location.origin) return;
      if (url.pathname !== window.location.pathname || !url.hash) return;

      const target = document.querySelector(url.hash);
      if (!(target instanceof HTMLElement)) return;

      event.preventDefault();
      const margin = parseFloat(getComputedStyle(target).scrollMarginTop) || 0;
      lenis.scrollTo(target, { offset: -margin });
      // The URL still has to change, or a section stops being linkable and the
      // back button stops undoing the jump.
      history.pushState(null, "", url.hash);
    }

    const onPreference = () => (query.matches ? stop() : start());
    onPreference();

    document.addEventListener("click", onClick);
    query.addEventListener("change", onPreference);
    return () => {
      document.removeEventListener("click", onClick);
      query.removeEventListener("change", onPreference);
      stop();
    };
  }, []);

  return null;
}
