"use client";

import { useState, useSyncExternalStore } from "react";
import Link from "next/link";

import { CopyButton } from "./copy-button";
import { usePeople } from "./people-provider";
import { copy } from "@/lib/copy";

/**
 * The setup steps, held back until you are on the wall.
 *
 * Not a hard gate, since the repository is public and the commands are in the
 * README either way. It is a trade: the wall is worth more with people on it,
 * and one name is a fair price for the thing you came here to install. The
 * locked state says exactly what it wants rather than pretending the section
 * is not there.
 */
export function InstallSection() {
  const { joined } = usePeople();

  return (
    <section id="install" className="scroll-mt-24 border-t px-6 py-24 sm:py-32 md:px-12 lg:px-24">
      <div className="mx-auto w-full max-w-5xl">
        <div className="grid gap-10 md:grid-cols-12 md:gap-14">
          <div className="md:col-span-4">
            <p className="text-muted-foreground font-mono text-[11px] tracking-[0.2em] uppercase">
              {copy.install.label}
            </p>
            <h2 className="mt-5 font-serif text-3xl leading-tight sm:text-4xl">
              {copy.install.heading}
            </h2>
            <p className="text-muted-foreground mt-5 text-base leading-relaxed">
              {copy.install.intro}
            </p>
          </div>

          {/* min-w-0 because a grid item defaults to min-width:auto and so
              will not shrink below its own content. The commands inside are
              whitespace-pre, so without this the longest one sets the width of
              this column, and on a phone that drags the entire page sideways
              rather than scrolling inside its own box. */}
          <div className="min-w-0 md:col-span-7 md:col-start-6">
            {joined ? <Steps /> : <Locked />}
          </div>
        </div>
      </div>
    </section>
  );
}

type Os = "windows" | "macos" | "linux";

const PLATFORMS = ["windows", "macos", "linux"] as const;

/**
 * The visitor's platform, read the sanctioned way rather than assigned inside
 * an effect. `navigator` is state React does not own, and setting state from an
 * effect to mirror it causes a second render on every load for a value that
 * never changes.
 */
const NEVER_CHANGES = () => () => {};
const platformNow = (): Os => {
  const agent = navigator.userAgent;
  if (agent.includes("Win")) return "windows";
  if (agent.includes("Mac")) return "macos";
  return "linux";
};
const platformOnServer = (): Os => "windows";

/**
 * The setup, as four commands for one machine.
 *
 * The switch sits above the list rather than inside a step, because the Git
 * command and the run command both differ by platform. Choosing once and having
 * every command below follow is the difference between reading a page and
 * assembling one. Mac and Linux used to share a tab, which was fine when only
 * the last command differed and misleading the moment the first one did too.
 */
function Steps() {
  const detected = useSyncExternalStore(NEVER_CHANGES, platformNow, platformOnServer);
  // Guessing beats making someone choose, and guessing wrong costs one click.
  const [chosenOs, setChosenOs] = useState<Os | null>(null);
  const os = chosenOs ?? detected;

  const { list } = copy.install.steps[os];
  // Coming back another day is the tail of the setup, not a different script:
  // go into the folder, start it. Taken from the same list so the commands
  // cannot drift apart from the ones above.
  const again = list.slice(-2);

  return (
    <div>
      <p className="text-sm font-medium">{copy.install.osLabel}</p>
      <div className="mt-3 flex gap-1 rounded-lg border p-1">
        {PLATFORMS.map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => setChosenOs(key)}
            aria-pressed={os === key}
            className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              os === key
                ? "bg-foreground text-background"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {copy.install.steps[key].tab}
          </button>
        ))}
      </div>

      {/* Where the terminal is and what to do with it. Everything below assumes
          a window that a lot of people have never opened. */}
      <p className="text-muted-foreground mt-4 text-sm leading-relaxed">
        {copy.install.terminalHint[os]}
      </p>

      <ol className="mt-8 space-y-8">
        {list.map((step, i) => (
          <Step key={step.title} index={i} title={step.title}>
            <CopyButton command={step.command} />
            <p className="text-muted-foreground text-xs">{step.note}</p>
          </Step>
        ))}
      </ol>

      <p className="mt-9 text-sm">
        {copy.install.outroBefore}{" "}
        <a href={copy.install.port} className="font-mono underline underline-offset-4">
          {copy.install.portLabel}
        </a>{" "}
        {copy.install.outroAfter}
      </p>

      <div className="mt-10 border-t pt-8">
        <h4 className="text-sm font-medium">{copy.install.againHeading}</h4>
        <p className="text-muted-foreground mt-2 text-sm leading-relaxed">
          {copy.install.againBody}
        </p>
        <div className="mt-4 space-y-2">
          {again.map((step) => (
            <CopyButton key={step.command} command={step.command} />
          ))}
        </div>
        <p className="text-muted-foreground mt-3 text-xs">{copy.install.againNote}</p>
      </div>

      <p className="text-muted-foreground mt-8 text-sm">
        {copy.install.guideBefore}{" "}
        <Link href="/guide" className="hover:text-foreground underline underline-offset-4">
          {copy.install.guideLink}
        </Link>{" "}
        {copy.install.guideAfter}
      </p>
    </div>
  );
}

function Step({
  index,
  title,
  children,
}: {
  index: number;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <li className="space-y-3">
      <div className="flex items-baseline gap-3">
        <span className="text-muted-foreground/60 font-mono text-xs tabular-nums">
          {String(index + 1).padStart(2, "0")}
        </span>
        <h4 className="text-sm font-medium">{title}</h4>
      </div>
      {children}
    </li>
  );
}

function Locked() {
  return (
    <div className="card flex flex-col items-start gap-5">
      <div className="space-y-3">
        {/* Blurred bars standing in for the commands, one per real step, so it
            is obvious what is behind this rather than being a mystery. */}
        {[86, 72, 44, 60].map((width, i) => (
          <div key={i} className="flex items-center gap-3">
            <span className="text-muted-foreground/40 font-mono text-xs tabular-nums">
              {String(i + 1).padStart(2, "0")}
            </span>
            <div
              className="bg-muted h-8 rounded-md blur-[3px]"
              style={{ width: `${width}%`, minWidth: "12rem" }}
            />
          </div>
        ))}
      </div>
      <p className="text-base">{copy.install.locked}</p>
      <a href="/join" className="btn-solid">
        {copy.join.submit}
      </a>
    </div>
  );
}
