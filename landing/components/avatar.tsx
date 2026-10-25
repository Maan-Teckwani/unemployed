/**
 * Every avatar on the site, and in the local app, is this: an image pointing at
 * /api/avatar. Nothing draws an avatar in the browser, so the style definition
 * never reaches a visitor and a wall of two hundred faces costs no JavaScript.
 */
export function avatarSrc(seed: string, gender: string): string {
  return `/api/avatar?seed=${encodeURIComponent(seed)}&gender=${encodeURIComponent(gender)}`;
}

export function AvatarImage({
  seed,
  gender,
  size = 56,
  priority = false,
}: {
  seed: string;
  gender: string;
  size?: number;
  priority?: boolean;
}) {
  return (
    // Plain img, not next/image: the source is already an SVG of a few KB, and
    // an optimiser would only add a round trip.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={avatarSrc(seed, gender)}
      alt=""
      width={size}
      height={size}
      loading={priority ? "eager" : "lazy"}
      className="rounded-full border border-blue-500 bg-background"
    />
  );
}
