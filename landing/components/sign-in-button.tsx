"use client";

import { signIn, signOut } from "next-auth/react";

import { copy } from "@/lib/copy";

/**
 * Sign-in and sign-out, as buttons rather than links.
 *
 * `signIn` posts to the provider's endpoint with a CSRF token, which a plain
 * anchor cannot do, so these have to be client components even though they
 * render one element each.
 */
export function SignInButton({ className = "btn-solid" }: { className?: string }) {
  return (
    <button type="button" onClick={() => signIn("google", { redirectTo: "/join" })} className={className}>
      {copy.auth.signIn}
    </button>
  );
}

export function SignOutButton() {
  return (
    <button
      type="button"
      onClick={() => signOut({ redirectTo: "/" })}
      className="text-red-600 hover:text-red-700 rounded-sm text-xs underline underline-offset-4 focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      {copy.auth.signOut}
    </button>
  );
}
