// Typed client for the FastAPI backend. One place that knows the API shape.
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type KBChunk = {
  id: number;
  type: string;
  title: string;
  context: string | null;
  company: string | null;
  date_range: string | null;
  accomplishment: string;
  technologies: string[];
  skills: string[];
  impact: string | null;
  created_at: string;
};

export type SearchResult = KBChunk & { similarity: number };

export type AccomplishmentIn = {
  text: string;
  technologies: string[];
  skills: string[];
  impact: string | null;
};

export type KBItemIn = {
  type: string;
  title: string;
  context: string | null;
  company: string | null;
  date_range: string | null;
  accomplishments: AccomplishmentIn[];
};

// A single chunk — used for both parsed proposals and reviewed saves.
export type ChunkIn = {
  type: string;
  title: string;
  context: string | null;
  company: string | null;
  date_range: string | null;
  accomplishment: string;
  technologies: string[];
  skills: string[];
  impact: string | null;
};

/** A running document parse. `chunks` is empty until `status` is "done". */
export type ParseJob = {
  id: string;
  status: "running" | "done" | "failed";
  done: number;
  total: number;
  message: string;
  errors: string[];
  chunks: ChunkIn[];
};

export type Job = {
  id: number;
  source: string;
  company: string;
  title: string;
  location: string;
  remote: boolean;
  apply_url: string;
  posted_at: string | null;
  status: string;
};

export type JobStats = { active: number; expired: number; companies: number };

export type IngestionRun = {
  id: number;
  source: string;
  company: string;
  started_at: string;
  finished_at: string | null;
  jobs_seen: number;
  jobs_new: number;
  jobs_updated: number;
  jobs_expired: number;
  ok: boolean;
  error: string | null;
};

export type MatchWhy = {
  weights?: Record<string, number>;
  contributions?: Record<string, number>;
  required_matched?: string[];
  required_missing?: string[];
  preferred_matched?: string[];
  seniority?: string;
  min_years?: number;
  skipped?: string;
};

/**
 * The funnel, in order. Everything from "applied" onward has left your hands,
 * which is what the pile on the home page is made of.
 */
export const STATUSES = [
  "todo",
  "resume_ready",
  "applied",
  "outreach_sent",
  "test",
  "interview",
  "offer",
  "rejected",
  "closed",
] as const;
export type Status = (typeof STATUSES)[number];

/** One row of your own progress, joined to the job it belongs to. */
export type ApplicationRow = {
  job_id: number;
  status: Status;
  notes: string;
  updated_at: string;
  /**
   * The first time this became an application that was sent. Stamped once by
   * the backend and never moved, which is what lets a closed job keep its place
   * in the pile — a rejection changes the status, not the fact that you applied.
   * Null until it goes out.
   */
  applied_at: string | null;
  title: string;
  company: string;
};

export type Match = {
  job: Job;
  status: Status;
  /** "estimated" = ranked without the LLM; "full" = requirements extracted. */
  tier: "estimated" | "full";
  score: number;
  f_semantic: number;
  f_keyword: number;
  f_required_cov: number;
  f_preferred_cov: number;
  f_preference_fit: number;
  confidence: number;
  hard_filtered: boolean;
  filter_reason: string;
  why: MatchWhy;
};

/** Score breakdown for a single job, as shown on its detail page. */
export type MatchDetail = {
  job: Job;
  score: number;
  tier: "estimated" | "full";
  f_semantic: number;
  f_keyword: number;
  f_required_cov: number;
  f_preferred_cov: number;
  f_preference_fit: number;
  confidence: number;
  hard_filtered: boolean;
  filter_reason: string;
  why: MatchWhy;
  requirements: {
    required_skills: string[];
    preferred_skills: string[];
    responsibilities: string[];
    seniority: string;
    min_years: number;
  };
};

export type MatchStats = {
  active: number;
  scored: number;
  filtered: number;
  rankable: number;
};

export type Profile = {
  id?: number;
  name: string;
  email: string;
  phone: string;
  location: string;
  links: Record<string, string>;
  summary: string;
  education: string;
  college: string;
};

export type ResumeBullet = {
  text: string;
  source_chunk_ids: number[];
  section: string;
  title: string;
  context: string | null;
  company: string | null;
  date_range: string | null;
};

export type AtsReport = {
  coverage: number | null;
  required_matched: string[];
  required_missing: string[];
  preferred_matched: string[];
  parse_ok: boolean;
  page_count: number;
  warnings: string[];
  rejected_bullets: { text: string; reason: string }[];
};

/** Per-section outcome of tailoring a LaTeX template, in document order. */
/** One entry the backend chose from the knowledge base to fill a slot. */
export type LatexEntry = {
  title: string;
  chunk_ids: number[];
  bullets: string[];
};

export type LatexSection = {
  name: string;
  heading: string;
  rewritten: boolean;
  reason?: string;
  /**
   * How this section was produced. "entries" means the projects in it were
   * chosen from the knowledge base and may not be the ones in the template;
   * "rewrite" means only the wording changed; "kept" means nothing did.
   */
  mode?: "entries" | "rewrite" | "kept";
  /** Whether the model picked the projects, or the relevance ranking did. */
  chosen_by?: "model" | "ranking";
  entries?: LatexEntry[];
  /**
   * Why this section's entries could not be chosen from the knowledge base,
   * when they could not. Set independently of `reason`, which is about the
   * rewrite that ran instead.
   */
  entries_declined?: string;
};

export type Resume = {
  id: number;
  job_id: number;
  headline: string;
  summary: string;
  skills: string[];
  bullets: ResumeBullet[];
  /** The whole tailored document; empty unless generated from a template. */
  latex: string;
  ats_report: AtsReport & { latex_sections?: LatexSection[] };
  sources: Record<string, { title: string; accomplishment: string }>;
  created_at: string;
};

export type MarketSkillItem = {
  skill: string;
  frequency: number;
  percentage: number;
  is_mastered: boolean;
  category: string;
  importance: number;
  potential_score_lift: number;
  sample_companies: string[];
};

export type DomainCluster = {
  category: string;
  mastered_count: number;
  missing_count: number;
  skills: MarketSkillItem[];
};

export type SkillAnalytics = {
  total_jobs_analyzed: number;
  candidate_skills_count: number;
  market_readiness_pct: number;
  top_missing_skills: MarketSkillItem[];
  top_mastered_skills: MarketSkillItem[];
  domain_clusters: DomainCluster[];
};

export type ImpactedJob = {
  job_id: number;
  company: string;
  title: string;
  old_score: number;
  new_score: number;
  score_lift: number;
};

export type SkillSimulationResult = {
  target_skills: string[];
  previous_avg_score: number;
  new_avg_score: number;
  avg_lift: number;
  unlocked_jobs_count: number;
  impacted_jobs: ImpactedJob[];
};

export type RoadmapMilestone = {
  week: number;
  title: string;
  objective: string;
  tasks: string[];
  deliverable: string;
  completed: boolean;
};

export type EngineeringChallenge = {
  challenge: string;
  solution: string;
  impact: string;
};

export type SkillRoadmap = {
  id: number;
  title: string;
  summary: string;
  role_family: string;
  target_skills: string[];
  status: "in_progress" | "completed" | "archived";
  estimated_weeks: number;
  architecture: string;
  milestones: RoadmapMilestone[];
  engineering_challenges: EngineeringChallenge[];
  resume_bullet_preview: string;
  interview_talking_points: string[];
  created_at: string;
  updated_at: string;
};


export type ResumeTemplate = {
  id: number;
  name: string;
  is_default: boolean;
  created_at: string;
  sections: { heading: string; rewritable: boolean }[];
};

export type JobDetail = Job & {
  description: string;
  first_seen: string;
  last_seen: string;
};

/**
 * Every family the classifier can produce (app/ingestion/role_family.py).
 * Nothing is discarded silently — a job you don't want is a family you didn't
 * tick, and it stays visible behind "Show filtered".
 */
export const ROLE_FAMILIES = [
  { id: "software", label: "Software Engineering", group: "Technical" },
  { id: "ai_ml", label: "AI / ML / Data Science", group: "Technical" },
  { id: "data", label: "Data / Analytics Engineering", group: "Technical" },
  { id: "devops", label: "DevOps / SRE / Cloud", group: "Technical" },
  { id: "security", label: "Security", group: "Technical" },
  { id: "qa", label: "QA / Testing", group: "Technical" },
  { id: "hardware", label: "Hardware / Embedded", group: "Technical" },
  { id: "research", label: "Research / Science", group: "Technical" },
  { id: "product", label: "Product Management", group: "Non-technical" },
  { id: "design", label: "Design / UX", group: "Non-technical" },
  { id: "sales", label: "Sales / Customer Success", group: "Non-technical" },
  { id: "marketing", label: "Marketing / Growth", group: "Non-technical" },
  { id: "content", label: "Content / Writing / Video", group: "Non-technical" },
  { id: "hr", label: "HR / Recruiting", group: "Non-technical" },
  { id: "finance", label: "Finance / Risk", group: "Non-technical" },
  { id: "operations", label: "Operations / Strategy", group: "Non-technical" },
  { id: "other", label: "Everything else", group: "Non-technical" },
] as const;

export const ROLE_FAMILY_GROUPS = ["Technical", "Non-technical"] as const;

export const SENIORITY_LEVELS = ["intern", "entry", "mid"] as const;

/** Hard location filter. "global" turns geographic filtering off. */
export const REGIONS = [
  { id: "india", label: "India" },
  { id: "us", label: "United States" },
  { id: "uk", label: "United Kingdom" },
  { id: "eu", label: "Europe" },
  { id: "canada", label: "Canada" },
  { id: "australia", label: "Australia / NZ" },
  { id: "singapore", label: "Singapore" },
  { id: "global", label: "Anywhere (no location filter)" },
] as const;

/** One place the preferred-locations field can offer. Served by the backend. */
export type City = {
  id: string;
  label: string;
  region: string;
  /** Other spellings of the same place, so searching "bangalore" finds it. */
  aliases: string[];
};

export type CompanyRow = {
  id: number;
  source: string;
  token: string;
  name: string;
  enabled: boolean;
  matched_jobs: number;
  active_jobs: number;
};

export type CompanySearchResult = {
  found: boolean;
  name: string;
  source?: string;
  token?: string;
  total_jobs?: number;
  matched_jobs?: number;
  already_tracked?: boolean;
};

export type Preferences = {
  id?: number;
  region: string;
  max_years: number;
  allowed_seniority: string[];
  role_families: string[];
  preferred_locations: string[];
  remote_ok: boolean;
};

export const CONTACT_STATUSES = ["todo", "found", "contacted", "replied"] as const;
export type ContactStatus = (typeof CONTACT_STATUSES)[number];

export type Contact = {
  id: number;
  job_id: number;
  category: string;
  label: string;
  search_url: string;
  draft: string;
  name: string;
  profile_url: string;
  status: ContactStatus;
  notes: string;
};

export type ProjectIdea = {
  id: number;
  job_id: number;
  title: string;
  problem: string;
  what_to_build: string;
  why_it_impresses: string;
  tech_stack: string[];
  covers_gaps: string[];
  scope: string;
};

/** "ingest" fetches and scores in one run; there is no scoring on its own. */
export type PipelineKind = "discover" | "ingest" | "rescore";

export type PipelineRun = {
  id: number;
  kind: PipelineKind;
  status: "running" | "done" | "failed";
  done: number;
  total: number;
  message: string;
  error: string | null;
  started_at: string;
  finished_at: string | null;
};

export type SetupStep = {
  id: string;
  label: string;
  done: boolean;
  href?: string;
  action?: PipelineKind;
  detail?: string;
};

export type SetupStatus = {
  steps: SetupStep[];
  ready: boolean;
  counts: {
    kb_chunks: number;
    companies: number;
    active_jobs: number;
    scored: number;
    rankable: number;
    applied: number;
    /** Everything ever sent, including jobs since rejected. Never falls. */
    pile: number;
  };
};

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export const api = {
  listChunks: () => req<KBChunk[]>("/kb/chunks"),
  addItem: (item: KBItemIn) =>
    req<KBChunk[]>("/kb/items", { method: "POST", body: JSON.stringify(item) }),
  deleteChunk: (id: number) =>
    req<void>(`/kb/chunks/${id}`, { method: "DELETE" }),
  search: (q: string, k = 5) =>
    req<SearchResult[]>(`/kb/search?q=${encodeURIComponent(q)}&k=${k}`),

  /**
   * Start parsing uploaded documents. Returns a job to poll with `parseStatus`
   * — a long CV is several minutes of local model time, far too long to hold a
   * request open for. Multipart, so no JSON header.
   */
  startParse: async (items: { file: File; kind: string }[]) => {
    const fd = new FormData();
    for (const { file, kind } of items) {
      fd.append("files", file);
      fd.append("kinds", kind);
    }
    const res = await fetch(`${BASE}/kb/parse`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
    return (await res.json()) as ParseJob;
  },
  parseStatus: (jobId: string) => req<ParseJob>(`/kb/parse/${jobId}`),

  saveChunks: (chunks: ChunkIn[]) =>
    req<KBChunk[]>("/kb/chunks/bulk", {
      method: "POST",
      body: JSON.stringify(chunks),
    }),

  listJobs: (q = "", limit = 100) =>
    req<Job[]>(`/jobs?limit=${limit}${q ? `&q=${encodeURIComponent(q)}` : ""}`),
  jobStats: () => req<JobStats>("/jobs/stats"),
  listRuns: (limit = 20) => req<IngestionRun[]>(`/jobs/runs?limit=${limit}`),

  listMatches: (limit = 25, includeFiltered = false) =>
    req<Match[]>(`/matches?limit=${limit}&include_filtered=${includeFiltered}`),
  matchStats: () => req<MatchStats>("/matches/stats"),

  getJob: (id: number) => req<JobDetail>(`/jobs/${id}`),
  matchDetail: (jobId: number) => req<MatchDetail>(`/matches/${jobId}`),

  getProfile: () => req<Profile>("/profile"),
  updateProfile: (p: Profile) =>
    req<Profile>("/profile", { method: "PUT", body: JSON.stringify(p) }),

  // Runs retrieval + local LLM generation — slow by nature.
  generateResume: (jobId: number, format: "pdf" | "latex" = "pdf") =>
    req<Resume>(`/resumes/generate/${jobId}?format=${format}`, { method: "POST" }),
  resumeForJob: (jobId: number) => req<Resume | null>(`/resumes/for-job/${jobId}`),
  resumePdfUrl: (resumeId: number) => `${BASE}/resumes/${resumeId}/pdf`,
  resumeLatexUrl: (resumeId: number) => `${BASE}/resumes/${resumeId}/latex`,

  listTemplates: () => req<ResumeTemplate[]>("/templates"),
  createTemplate: (name: string, source: string) =>
    req<ResumeTemplate>("/templates", {
      method: "POST",
      body: JSON.stringify({ name, source }),
    }),
  setDefaultTemplate: (id: number) =>
    req<ResumeTemplate>(`/templates/${id}/default`, { method: "POST" }),
  deleteTemplate: (id: number) => req<void>(`/templates/${id}`, { method: "DELETE" }),

  editResume: (
    resumeId: number,
    body: { summary: string; skills: string[]; bullets: ResumeBullet[] },
  ) => req<Resume>(`/resumes/${resumeId}`, { method: "PUT", body: JSON.stringify(body) }),

  setStatus: (jobId: number, status: Status, notes = "") =>
    req<{ job_id: number; status: Status; applied_at: string | null }>(
      `/applications/${jobId}`,
      { method: "PUT", body: JSON.stringify({ status, notes }) },
    ),
  applicationStats: () =>
    req<Record<Status, number> & { pile: number }>("/applications/stats"),
  listApplications: () => req<ApplicationRow[]>("/applications"),

  // Creates the job, then runs extraction + scoring inline (~30s).
  projectIdea: (jobId: number) => req<ProjectIdea | null>(`/projects/${jobId}`),
  // One LLM call (~40s) to design a project tailored to this company.
  generateProjectIdea: (jobId: number) =>
    req<ProjectIdea>(`/projects/${jobId}/generate`, { method: "POST" }),

  listContacts: (jobId: number) => req<Contact[]>(`/outreach/${jobId}`),
  // Builds the search links, then drafts a grounded message each (~30s).
  generateOutreach: (jobId: number) =>
    req<Contact[]>(`/outreach/${jobId}/generate`, { method: "POST" }),
  updateContact: (
    id: number,
    body: {
      name: string;
      profile_url: string;
      status: ContactStatus;
      notes: string;
      draft: string;
    },
  ) => req<Contact>(`/outreach/contact/${id}`, { method: "PUT", body: JSON.stringify(body) }),

  setupStatus: () => req<SetupStatus>("/setup/status"),
  // 409 when a run is already in flight — the server refuses, we surface it.
  startPipeline: (kind: PipelineKind) =>
    req<PipelineRun>("/pipeline/run", {
      method: "POST",
      body: JSON.stringify({ kind }),
    }),
  pipelineStatus: () => req<PipelineRun | null>("/pipeline/status"),

  listCompanies: () => req<CompanyRow[]>("/companies"),
  // Probes all four ATS platforms live (~5s), so any company can be added.
  searchCompany: (name: string) =>
    req<CompanySearchResult>(`/companies/search?name=${encodeURIComponent(name)}`),
  addCompany: (body: {
    source: string;
    token: string;
    name: string;
    matched_jobs: number;
  }) => req<{ id: number; name: string }>("/companies", {
    method: "POST",
    body: JSON.stringify(body),
  }),
  removeCompany: (id: number) =>
    req<void>(`/companies/${id}`, { method: "DELETE" }),

  getPreferences: () => req<Preferences>("/preferences"),
  // Fetched, not bundled. The same list decides which jobs are ingested at all,
  // so a copy kept here would eventually offer a city the backend has never
  // heard of, which looks like it works and ranks nothing.
  getCities: (region?: string) =>
    req<City[]>(`/preferences/cities${region ? `?region=${encodeURIComponent(region)}` : ""}`),
  updatePreferences: (p: Preferences) =>
    req<Preferences>("/preferences", { method: "PUT", body: JSON.stringify(p) }),
  // Pure arithmetic over cached extractions — no LLM, so this is seconds.
  rescore: () =>
    req<{ scored: number; filtered: number }>("/preferences/rescore", {
      method: "POST",
    }),

  createManualJob: (body: {
    title: string;
    company: string;
    description: string;
    location: string;
    apply_url: string;
  }) =>
    req<{ job_id: number; score: number; filtered: boolean }>("/jobs/manual", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getSkillAnalytics: (roleFamily?: string) =>
    req<SkillAnalytics>(
      `/skills/analytics${roleFamily ? `?role_family=${encodeURIComponent(roleFamily)}` : ""}`
    ),
  simulateSkills: (targetSkills: string[]) =>
    req<SkillSimulationResult>("/skills/simulate", {
      method: "POST",
      body: JSON.stringify({ target_skills: targetSkills }),
    }),
  listRoadmaps: () => req<SkillRoadmap[]>("/roadmaps"),
  generateRoadmap: (body: {
    target_skills: string[];
    role_family?: string;
    estimated_weeks?: number;
  }) =>
    req<SkillRoadmap>("/roadmaps/generate", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getRoadmap: (id: number) => req<SkillRoadmap>(`/roadmaps/${id}`),
  updateRoadmap: (
    id: number,
    body: { status?: string; milestones?: RoadmapMilestone[] }
  ) =>
    req<SkillRoadmap>(`/roadmaps/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  completeRoadmapToKb: (id: number) =>
    req<{ status: string; message: string; chunk_id: number }>(
      `/roadmaps/${id}/complete-to-kb`,
      { method: "POST" }
    ),
  deleteRoadmap: (id: number) =>
    req<void>(`/roadmaps/${id}`, { method: "DELETE" }),
};


// ---------------------------------------------------------------------------
// The community wall.
//
// It lives on the hosted landing page rather than the local backend, and it is
// the only thing in this app that talks to the internet. Everything below is
// optional by design: it must never take a page down, and being offline has to
// look the same as a wall that happens to be empty.
//
// Deliberately not routed through `req()`, which prefixes the local API and
// throws on any non-2xx.
// ---------------------------------------------------------------------------
// The deployed landing site both in dev and in production. `.env*` is
// gitignored, so a fresh clone has no NEXT_PUBLIC_LANDING_URL — and in dev
// localhost:3000 is *this* app, which serves no /api/avatar, so defaulting
// there just breaks every avatar. Point at the real site and let anyone
// running landing/ locally set NEXT_PUBLIC_LANDING_URL themselves.
const LANDING =
  process.env.NEXT_PUBLIC_LANDING_URL ?? "https://unemployed-eight.vercel.app";

export type Signup = {
  id: string;
  name: string;
  country: string;
  gender: "female" | "male" | "neutral";
  seed: string;
  created_at: string;
};

/** Avatars are drawn by the landing site, so this app needs no avatar code. */
export function avatarUrl(seed: string, gender: string): string {
  return `${LANDING}/api/avatar?seed=${encodeURIComponent(seed)}&gender=${encodeURIComponent(gender)}`;
}

export function wallUrl(): string {
  return LANDING;
}

/**
 * Returns null rather than throwing, and gives up after four seconds. Offline
 * is a normal state for a local-first tool, not an error worth a spinner on a
 * train.
 */
export async function fetchSignups(
  limit = 200,
): Promise<{ count: number; signups: Signup[] } | null> {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 4000);
    const res = await fetch(`${LANDING}/api/signups?limit=${limit}`, {
      signal: controller.signal,
      cache: "no-store",
    });
    clearTimeout(timer);
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}
