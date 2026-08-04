import type { Metadata } from "next";

import { PageNav } from "@/components/page-nav";
import { PeopleProvider } from "@/components/people-provider";
import { Wall } from "@/components/wall";
import { copy } from "@/lib/copy";
import { crowdPage } from "@/lib/db";
import { viewer } from "@/lib/viewer";

export const metadata: Metadata = {
  title: copy.meta.pages.wall,
  description: copy.meta.pages.wallDescription,
  alternates: { canonical: "/wall" },
};

// Read per request, same reasoning as the other pages: nothing here is worth
// freezing at build time, and the build must not need a database.
export const dynamic = "force-dynamic";

/**
 * The wall, on its own page.
 *
 * It used to be a section near the bottom of the home page, which made it both
 * hard to link to and something you had to scroll past the whole pitch to
 * reach. Interview experiences already had their own page; this matches it.
 */
export default async function WallPage() {
  const [page, me] = await Promise.all([crowdPage(), viewer()]);

  return (
    <PeopleProvider joined={me.signup !== null}>
      <PageNav signedIn={me.signedIn} />
      <main id="top">
        <Wall page={page} me={me.signup} />
      </main>
    </PeopleProvider>
  );
}
