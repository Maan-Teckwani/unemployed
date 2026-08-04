/**
 * Everything a stranger can type, checked before it reaches the database.
 *
 * Pure functions on purpose: this is the file worth testing, and none of it
 * needs a request, a database or a network.
 */
// Explicit .ts extensions: `node --test` strips types but does not resolve
// extensionless paths the way a bundler does, so without these the test suite
// cannot import this module at all. tsconfig already sets
// allowImportingTsExtensions, and the bundler is happy either way.
import { canonicalCountry, COUNTRY_CODES } from "./countries.ts";
import { GENDERS, type Gender } from "./gender-options.ts";

export const MAX_NAME_LENGTH = 24;

/**
 * Two tiers, because one list cannot do both jobs.
 *
 * Slurs are matched anywhere in the name: there is no real name that contains
 * one by accident, so the false positive risk is worth taking.
 *
 * Ordinary swearing is matched only as a whole word. Dickson, Cockburn and
 * Sexton are real surnames, and a wall that tells someone their own name is
 * unacceptable is worse than a wall with a rude word on it.
 */
const SLURS = ["nigger", "nigga", "faggot", "retard", "nazi", "hitler"];

const SWEARS = [
  "fuck", "shit", "cunt", "bitch", "bastard", "wanker", "slut", "whore",
  "rape", "penis", "vagina", "dick", "cock", "boobs", "porn", "sex", "anal",
];

const LEET: Record<string, string> = {
  "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t",
  "@": "a", $: "s", "!": "i", "|": "i",
};

/** Undo the substitutions people reach for first, and drop everything else. */
function flatten(text: string): string {
  return text
    .toLowerCase()
    .replace(/[013457@$!|]/g, (c) => LEET[c] ?? c)
    .replace(/[^a-z]/g, "");
}

function isProfane(name: string): boolean {
  const flat = flatten(name);
  if (SLURS.some((word) => flat.includes(word))) return true;

  // Whole words only. "Dickson" is one token and is not "dick", but "F U C K"
  // collapses to a single token once the spacing is removed, so check both.
  const tokens = name.toLowerCase().split(/\s+/).map(flatten).filter(Boolean);
  return SWEARS.some((word) => flat === word || tokens.includes(word));
}

export function cleanName(raw: unknown): string {
  return String(raw ?? "")
    .normalize("NFC")
    // Control and format characters. This is what removes zero-width joiners and
    // the right-to-left override that makes a name rearrange the page around it.
    .replace(/[\p{Cc}\p{Cf}]/gu, "")
    .replace(/\s+/g, " ")
    .trim();
}

export type NameProblem = "empty" | "tooLong" | "profane" | null;

export function checkName(raw: unknown): { name: string; problem: NameProblem } {
  const name = cleanName(raw);
  if (name.length === 0) return { name, problem: "empty" };
  // Count code points, not UTF-16 units, or one emoji spends four characters.
  if ([...name].length > MAX_NAME_LENGTH) return { name, problem: "tooLong" };

  if (isProfane(name)) return { name, problem: "profane" };
  return { name, problem: null };
}

export function isValidCountry(code: unknown): code is string {
  return typeof code === "string" && COUNTRY_CODES.has(canonicalCountry(code));
}

/**
 * The code to store, given whatever arrived.
 *
 * Folds the retired duplicates onto the code that replaced them, so the wall
 * never ends up with two groups of Germans. Returns null rather than a fallback
 * country, because guessing where someone is from is worse than asking again.
 */
export function normalizeCountry(code: unknown): string | null {
  return isValidCountry(code) ? canonicalCountry(code) : null;
}

export function asGenderStrict(value: unknown): Gender | null {
  return GENDERS.includes(value as Gender) ? (value as Gender) : null;
}

export function isValidSeedInput(seed: unknown): seed is string {
  return typeof seed === "string" && /^[a-z0-9-]{1,64}$/i.test(seed);
}

export const RESULTS = ["offer", "rejected", "withdrawn", "pending"] as const;
export type Result = (typeof RESULTS)[number];

export const ROUND_TYPES = [
  "oa", "technical", "system_design", "hr", "managerial", "group_discussion", "other",
] as const;
export type RoundType = (typeof ROUND_TYPES)[number];

export const ROUND_OUTCOMES = ["cleared", "rejected", "pending"] as const;
export type RoundOutcome = (typeof ROUND_OUTCOMES)[number];

export type TextProblem = "empty" | "tooLong" | "profane" | null;

/** Same cleaning + profanity checks as a name, for any other free-text field. */
export function checkText(raw: unknown, maxLen: number): { text: string; problem: TextProblem } {
  const text = cleanName(raw);
  if (text.length === 0) return { text, problem: "empty" };
  if ([...text].length > maxLen) return { text, problem: "tooLong" };
  if (isProfane(text)) return { text, problem: "profane" };
  return { text, problem: null };
}

export function checkCompany(raw: unknown) {
  const { text, problem } = checkText(raw, 80);
  return { company: text, problem };
}

export function checkRole(raw: unknown) {
  const { text, problem } = checkText(raw, 80);
  return { role: text, problem };
}

export function isValidResult(value: unknown): value is Result {
  return RESULTS.includes(value as Result);
}

export function isValidRoundType(value: unknown): value is RoundType {
  return ROUND_TYPES.includes(value as RoundType);
}

export function isValidRoundOutcome(value: unknown): value is RoundOutcome {
  return ROUND_OUTCOMES.includes(value as RoundOutcome);
}
