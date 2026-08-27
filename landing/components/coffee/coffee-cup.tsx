/**
 * A mug, with coffee in it, filled to whatever the reader picked.
 *
 * Drawn rather than fetched. It is one shape, it has to inherit the page's ink
 * colour so it works on both themes, and the liquid inside it has to be
 * animated by a number that changes as a slider moves, which rules out an image
 * and rules out an icon package.
 *
 * How the fill works: the coffee is a full height shape with a wave along its
 * top edge, clipped to the inside of the mug and slid up and down. Nothing is
 * resized, so the wave keeps its proportions at every level, and a CSS
 * transition on the slide is what makes the level move rather than jump. The
 * clip is the whole trick: outside it the coffee is simply not painted, so the
 * ceramic never has to be drawn over the top of it.
 *
 * The brown is the one place on this site where a second colour was allowed in.
 * Coffee that is not brown is not coffee, and a grey mug of grey liquid reads
 * as a diagram of a mug. The rings on the wall stay amber, so the accent that
 * means "this person did something" is still the only one of its kind.
 *
 * Everything that moves here is decoration on a number that is also written out
 * in text beside it, so under prefers-reduced-motion it all stops and the cup
 * simply sits at the right level.
 */

/** Where the surface sits at nothing, and at a full cup, in user units. */
const EMPTY = 150;
const FULL = 54;

export function CoffeeCup({
  fill,
  emptied = false,
  className = "",
}: {
  /** 0 to 1. */
  fill: number;
  /** The thank you state: they drank it. */
  emptied?: boolean;
  className?: string;
}) {
  const level = emptied ? 0 : Math.min(Math.max(fill, 0), 1);
  const surface = EMPTY - level * (EMPTY - FULL);

  return (
    <svg
      viewBox="0 0 220 210"
      // The level is written out in words next to this, so a screen reader
      // reading the picture as well would only say it twice.
      aria-hidden
      className={`coffee-cup ${className}`}
      // Steam thins out as the cup empties, and stops entirely once it is.
      data-steaming={level > 0.15 || undefined}
    >
      <defs>
        {/* The inside of the mug. Its top is the full rim ellipse, so a full cup
            reads as a disc of coffee seen at an angle rather than as a straight
            line cutting across the opening. */}
        <clipPath id="coffee-cavity">
          <path d="M53 52 A43 10.5 0 0 1 139 52 L128 152 Q96 167 64 152 Z" />
        </clipPath>
      </defs>

      {/* Saucer, behind everything, so the mug sits on something instead of
          floating. Drawn as two arcs rather than a full ellipse: the part of it
          hidden behind the mug should not show through the ceramic. */}
      <ellipse
        cx="104"
        cy="180"
        rx="88"
        ry="14"
        className="coffee-cup__saucer"
      />

      {/* Steam. Three strands, above the rim, each on its own clock so they do
          not rise in formation. */}
      <g className="coffee-cup__steam" fill="none" strokeLinecap="round" strokeWidth="3">
        <path d="M74 32c-7-9 7-13 0-23" style={{ animationDelay: "0ms" }} />
        <path d="M96 26c-8-10 8-15 0-27" style={{ animationDelay: "700ms" }} />
        <path d="M118 32c-7-9 7-13 0-23" style={{ animationDelay: "1400ms" }} />
      </g>

      {/* The ceramic, drawn before the coffee so the coffee sits inside it. */}
      <path
        d="M53 52 A43 10.5 0 0 1 139 52 L128 152 Q96 167 64 152 Z"
        className="coffee-cup__ceramic"
      />

      {/* The coffee. One group, slid up and down; see the note at the top. */}
      <g clipPath="url(#coffee-cavity)">
        <g
          className="coffee-cup__liquid"
          style={{ transform: `translateY(${surface}px)` }}
        >
          {/* Crema first, then the body of the coffee seven units lower, which
              leaves a lighter band along the surface. Two waves rather than one
              shape with a highlight: they run at different speeds, so the band
              breathes instead of sliding along as a rigid stripe. */}
          <path className="coffee-cup__crema" d={WAVE} />
          <path
            className="coffee-cup__body"
            d={WAVE}
            style={{ transform: "translateY(7px)" }}
          />
        </g>
      </g>

      {/* The rim, over the coffee, so a full cup has a lip rather than a flat
          edge of brown running off the sides. */}
      <ellipse cx="96" cy="52" rx="43" ry="10.5" className="coffee-cup__rim" />

      {/* The handle. Outside the clip and outside the body path, because a
          handle drawn as part of the body would take the coffee with it. */}
      <path
        d="M139 70c26-6 42 6 41 26 -1 20-19 30-45 30"
        className="coffee-cup__handle"
      />

      {/* The outer wall, last, so the ink reads on top of everything. */}
      <path
        d="M53 52 A43 10.5 0 0 0 139 52 M53 52 L64 152 Q96 167 128 152 L139 52"
        className="coffee-cup__wall"
      />
    </svg>
  );
}

/**
 * The surface, as a wave with a period of 120 user units.
 *
 * Wide enough to cover the mug three times over, because it is animated by
 * sliding it exactly one period sideways and starting again, and the part that
 * scrolls into view has to already exist. Anything shorter shows the end of the
 * path crossing the cup once a second.
 */
const WAVE = "M-120 0q30-7 60 0t60 0t60 0t60 0t60 0t60 0V240H-120Z";
