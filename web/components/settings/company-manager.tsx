"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type CompanyRow, type CompanySearchResult } from "@/lib/api";
import { usePipeline } from "@/components/pipeline/pipeline-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/**
 * Add any company with a public job board.
 *
 * Typing a name probes Greenhouse, Lever, Ashby, SmartRecruiters and Recruitee
 * live and reports which one hosts it — so coverage isn't limited to the
 * shipped seed list. A board only counts if it actually has jobs for your
 * region: slugs collide across vendors, and a same-named company elsewhere is
 * not a match.
 *
 * The same box takes a Workday careers link, because Workday cannot be probed
 * by name. Its API path ends in a site slug picked per company and derived
 * from nothing, so guessing it found six companies in fifty nine. That slug is
 * in the URL, which a person reads in one look.
 */
export function CompanyManager() {
  const [companies, setCompanies] = useState<CompanyRow[]>([]);
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<CompanySearchResult | null>(null);
  const [searching, setSearching] = useState(false);
  // A pasted link only tells us the subdomain, so Morgan Stanley resolves as
  // "Ms" and HPE as "Hpe". The careers pages declare no usable name either,
  // and this one is worth getting right: it is what the companies list shows
  // and what every job from this board is filed under.
  const [name, setName] = useState("");
  const { start, running } = usePipeline();

  const load = useCallback(async () => {
    try {
      setCompanies(await api.listCompanies());
    } catch {
      /* backend not reachable */
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const looksLikeLink = /^https?:\/\//i.test(query.trim());

  async function search() {
    if (query.trim().length < 2) return toast.error("Enter a company name or a link");
    setSearching(true);
    setResult(null);
    try {
      const found = await api.searchCompany(query.trim());
      setResult(found);
      setName(found.name);
    } catch (e) {
      toast.error(String(e));
    } finally {
      setSearching(false);
    }
  }

  async function add() {
    if (!result?.found) return;
    const label = name.trim() || result.name;
    try {
      await api.addCompany({
        source: result.source!,
        token: result.token!,
        name: label,
        matched_jobs: result.matched_jobs ?? 0,
      });
      toast.success(`Added ${label} — run a fetch to pull its jobs`);
      setResult(null);
      setQuery("");
      setName("");
      load();
    } catch (e) {
      toast.error(String(e));
    }
  }

  async function remove(company: CompanyRow) {
    if (!confirm(`Stop tracking ${company.name}? Its jobs stop being fetched.`)) return;
    try {
      await api.removeCompany(company.id);
      toast.success(`Removed ${company.name}`);
      load();
    } catch (e) {
      toast.error(String(e));
    }
  }

  return (
    <div className="rounded-lg border p-5 space-y-4">
      <div>
        <h2 className="font-medium">Companies</h2>
        <p className="text-xs text-muted-foreground mt-1">
          {companies.length} tracked. Search by name for Greenhouse, Lever, Ashby,
          SmartRecruiters and Recruitee. For a Workday company, paste its careers
          link instead.
        </p>
      </div>

      <div className="flex gap-2">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          placeholder="Razorpay, Stripe, or a workday careers link…"
        />
        <Button onClick={search} disabled={searching}>
          {searching ? (looksLikeLink ? "Reading…" : "Searching…") : "Search"}
        </Button>
      </div>

      {/* Shown while typing a link rather than after failing with one: most
          people paste the company's own careers domain, which is a redirect
          and carries none of the parts the API path needs. */}
      {looksLikeLink && !query.includes("myworkdayjobs.com") && (
        <p className="text-xs text-muted-foreground">
          Workday links look like{" "}
          <code className="bg-muted rounded px-1">
            company.wd5.myworkdayjobs.com/CareerSite
          </code>
          . If the company&rsquo;s careers page redirects somewhere else, open a job
          on it and copy the address from there.
        </p>
      )}

      {/* Moved here from the home page, where it sat beside Fetch at the same
          size. It is a once-in-a-while action that adds rows to the list right
          below it, so this is where you are when you want it. */}
      <button
        onClick={() => start("discover")}
        disabled={running}
        className="text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground disabled:no-underline disabled:opacity-60"
      >
        {running ? "Something is already running…" : "Or find companies automatically — about 5 minutes"}
      </button>

      {result && (
        <div className="rounded-md border p-3 text-sm">
          {result.found ? (
            <div className="flex items-center gap-3 flex-wrap">
              {result.already_tracked ? (
                <span className="font-medium">{result.name}</span>
              ) : (
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && add()}
                  aria-label="Company name"
                  className="h-8 w-48"
                />
              )}
              <Badge variant="secondary">{result.source}</Badge>
              <span className="text-muted-foreground text-xs">
                {result.matched_jobs} matching job
                {result.matched_jobs === 1 ? "" : "s"} of {result.total_jobs}
              </span>
              {result.already_tracked ? (
                <Badge variant="outline">already tracked</Badge>
              ) : (
                <Button size="sm" onClick={add}>
                  Add
                </Button>
              )}
            </div>
          ) : (
            <p className="text-muted-foreground">
              No public board found for &ldquo;{result.name}&rdquo; with jobs in your
              region. They may use a different ATS, or post nothing there right now.
            </p>
          )}
        </div>
      )}

      <div className="max-h-72 overflow-y-auto rounded-md border divide-y">
        {companies.map((c) => (
          <div key={c.id} className="flex items-center gap-3 px-3 py-2 text-sm">
            <span className="flex-1 truncate">{c.name}</span>
            <Badge variant="secondary">{c.source}</Badge>
            <span className="text-xs text-muted-foreground w-20 text-right">
              {c.active_jobs} job{c.active_jobs === 1 ? "" : "s"}
            </span>
            <button
              onClick={() => remove(c)}
              className="text-xs text-muted-foreground underline shrink-0"
            >
              remove
            </button>
          </div>
        ))}
        {companies.length === 0 && (
          <p className="px-3 py-4 text-sm text-muted-foreground">
            No companies yet. Search above, or run{" "}
            <code className="bg-muted px-1 rounded">
              python -m app.ingestion.discover
            </code>
            .
          </p>
        )}
      </div>
    </div>
  );
}
