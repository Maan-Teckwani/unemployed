"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { api, type City } from "@/lib/api";
import { Input } from "@/components/ui/input";

/**
 * Preferred locations, chosen from the list the matcher actually knows.
 *
 * This used to be a text field split on commas. Two things went wrong with that
 * and neither was visible to the person typing. A typo silently stopped ranking
 * anything, and so did any spelling the boards do not use: "Bangalore" never
 * matched a posting that said "Bengaluru", which is most of them.
 *
 * So the options come from the backend, searching matches aliases as well as
 * labels, and picking one stores the spelling the matcher resolves. Free text is
 * still allowed, because a list of a hundred and fifty cities is not everywhere
 * and refusing someone their own city is worse than a preference we cannot
 * improve.
 */
export function LocationPicker({
  region,
  value,
  onChange,
}: {
  region: string;
  value: string[];
  onChange: (next: string[]) => void;
}) {
  const [cities, setCities] = useState<City[]>([]);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  // Scoped to the region, since that is the hard filter: offering Toronto to
  // someone who only ingests Indian postings would be a preference that can
  // never apply to anything.
  useEffect(() => {
    let live = true;
    api
      .getCities(region)
      .then((rows) => {
        if (live) setCities(rows);
      })
      .catch(() => {
        // The field still works as free text without the list.
        if (live) setCities([]);
      });
    return () => {
      live = false;
    };
  }, [region]);

  useEffect(() => {
    function onPointerDown(event: PointerEvent) {
      if (!boxRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, []);

  const chosen = useMemo(() => new Set(value.map((v) => v.toLowerCase())), [value]);

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return cities.filter((c) => !chosen.has(c.label.toLowerCase())).slice(0, 8);
    return cities
      .filter((c) => !chosen.has(c.label.toLowerCase()))
      .filter(
        (c) =>
          c.label.toLowerCase().includes(q) ||
          c.aliases.some((a) => a.toLowerCase().includes(q)),
      )
      .slice(0, 8);
  }, [cities, query, chosen]);

  function add(label: string) {
    const text = label.trim();
    if (!text || chosen.has(text.toLowerCase())) return;
    onChange([...value, text]);
    setQuery("");
    setOpen(false);
  }

  function remove(label: string) {
    onChange(value.filter((v) => v !== label));
  }

  return (
    <div ref={boxRef} className="relative space-y-2">
      {value.length > 0 && (
        <ul className="flex flex-wrap gap-1.5">
          {value.map((label) => (
            <li key={label}>
              <button
                type="button"
                onClick={() => remove(label)}
                aria-label={`Remove ${label}`}
                className="flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs hover:bg-muted"
              >
                {label}
                <span aria-hidden className="text-muted-foreground">
                  x
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <Input
        id="locations"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            // The first match if there is one, otherwise whatever was typed.
            add(matches[0]?.label ?? query);
          }
          if (e.key === "Escape") setOpen(false);
        }}
        placeholder="Search a city, or type your own and press Enter"
        autoComplete="off"
        role="combobox"
        aria-expanded={open}
        aria-controls="location-options"
      />

      {open && (matches.length > 0 || query.trim()) && (
        <ul
          id="location-options"
          className="absolute z-20 mt-1 w-full overflow-hidden rounded-lg border bg-background shadow-md"
        >
          {matches.map((city) => (
            <li key={city.id}>
              <button
                type="button"
                onClick={() => add(city.label)}
                className="flex w-full items-baseline justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-muted"
              >
                {city.label}
                {city.aliases.length > 0 && (
                  <span className="text-muted-foreground text-xs">
                    also {city.aliases.join(", ")}
                  </span>
                )}
              </button>
            </li>
          ))}
          {query.trim() && !matches.some((c) => c.label.toLowerCase() === query.trim().toLowerCase()) && (
            <li className="border-t">
              <button
                type="button"
                onClick={() => add(query)}
                className="w-full px-3 py-2 text-left text-sm hover:bg-muted"
              >
                Use &ldquo;{query.trim()}&rdquo;
                <span className="text-muted-foreground text-xs"> (not in the list)</span>
              </button>
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
