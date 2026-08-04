import { auth } from "@/auth";
import { deleteExperience, signupForGoogleSub, updateExperience } from "@/lib/db";
import {
  checkCompany,
  checkRole,
  checkText,
  isValidResult,
  isValidRoundOutcome,
  isValidRoundType,
} from "@/lib/validate";
import { CORS, corsOptions } from "@/lib/cors";

export const dynamic = "force-dynamic";
const MAX_ROUNDS = 20;

export async function OPTIONS() {
  return corsOptions();
}

type RoundInput = {
  round_number: number;
  round_type: string;
  description: string;
  outcome: string;
};

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await auth();
  const googleSub = session?.user?.id;
  if (!googleSub) return fail("mustSignIn", 401);

  const { id } = await params;
  if (!id || !/^\d+$/.test(id)) return fail("generic", 400);

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return fail("generic", 400);
  }
  if (typeof body !== "object" || body === null) return fail("generic", 400);

  const { company: rawCompany, role: rawRole, result, summary: rawSummary, rounds } =
    body as Record<string, unknown>;

  const { company, problem: companyProblem } = checkCompany(rawCompany);
  if (companyProblem) return fail(companyProblem, 400, "company");

  const { role, problem: roleProblem } = checkRole(rawRole);
  if (roleProblem) return fail(roleProblem, 400, "role");

  if (!isValidResult(result)) return fail("generic", 400, "result");

  const { text: summary, problem: summaryProblem } = checkText(rawSummary, 2000);
  if (summaryProblem) return fail(summaryProblem, 400, "summary");

  const roundsCheck = checkRounds(rounds);
  if (roundsCheck.problem) return fail(roundsCheck.problem, 400, "rounds");

  try {
    const signup = await signupForGoogleSub(googleSub);
    if (!signup) return fail("mustJoinWall", 403);
    const signupId = signup.id;

    const success = await updateExperience(id, signupId, company, role, result as string, summary, roundsCheck.rounds);
    if (!success) return fail("notFound", 404);
    
    return Response.json({ success: true }, { status: 200, headers: CORS });
  } catch (error) {
    console.error("experience update failed", error);
    return fail("generic", 503);
  }
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await auth();
  const googleSub = session?.user?.id;
  if (!googleSub) return fail("mustSignIn", 401);

  const { id } = await params;
  if (!id || !/^\d+$/.test(id)) return fail("generic", 400);

  try {
    const signup = await signupForGoogleSub(googleSub);
    if (!signup) return fail("mustJoinWall", 403);
    const signupId = signup.id;

    const success = await deleteExperience(id, signupId);
    if (!success) return fail("notFound", 404);

    return Response.json({ success: true }, { status: 200, headers: CORS });
  } catch (error) {
    console.error("experience delete failed", error);
    return fail("generic", 503);
  }
}

function checkRounds(raw: unknown): { rounds: RoundInput[]; problem: string | null } {
  if (!Array.isArray(raw) || raw.length === 0 || raw.length > MAX_ROUNDS) {
    return { rounds: [], problem: "rounds" };
  }

  const rounds: RoundInput[] = [];
  for (let i = 0; i < raw.length; i++) {
    const entry = raw[i];
    if (typeof entry !== "object" || entry === null) return { rounds: [], problem: "rounds" };
    const { round_type, description, outcome } = entry as Record<string, unknown>;

    if (!isValidRoundType(round_type)) return { rounds: [], problem: "rounds" };
    if (!isValidRoundOutcome(outcome)) return { rounds: [], problem: "rounds" };

    const { text, problem } = checkText(description, 1000);
    if (problem) return { rounds: [], problem: "rounds" };

    rounds.push({ round_number: i + 1, round_type, description: text, outcome: outcome as string });
  }

  return { rounds, problem: null };
}

function fail(error: string, status: number, field?: string) {
  return Response.json({ error, field }, { status, headers: CORS });
}
