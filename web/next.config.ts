import type { NextConfig } from "next";
import { fileURLToPath } from "node:url";

const nextConfig: NextConfig = {
  // Pin the workspace root to this app so a stray lockfile elsewhere on the
  // machine doesn't get inferred as the root.
  turbopack: { root: fileURLToPath(new URL(".", import.meta.url)) },
  experimental: {
    // Lets a job keep its identity when you open it from the ranked list: the
    // title morphs into the detail page's heading instead of the whole screen
    // being replaced. Turning this off makes every <ViewTransition> an inert
    // wrapper — nothing breaks, the navigation just cuts.
    viewTransition: true,
  },
};

export default nextConfig;
