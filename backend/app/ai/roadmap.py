"""AI Learning Roadmap Engine: Generates multi-skill engineering project blueprints.

Combines top missing high-leverage skills into a unified, high-signal project
with step-by-step weekly milestones, deliverables, architecture specs, and STAR resume bullets.
"""
from app.ai.llm import generate_json
from app.ai.project_idea import _GENERIC

_SYSTEM_PROMPT = """You are a Principal Software Engineer designing an impressive, high-signal portfolio project for a software engineering candidate.

The candidate needs a multi-week project that proves mastery of specific target skills they currently lack, while building on their existing strengths.

Rules:
1. NEVER suggest generic beginner tutorials (todo app, weather app, crud demo, simple clone).
2. The project must solve a realistic, production-grade problem (e.g., distributed caching, event streaming, rate limiting, async job queues, real-time analytics).
3. The project MUST deeply integrate ALL target skills requested.
4. Each milestone must have concrete, verifiable engineering deliverables and tasks.
5. Provide realistic technical challenges, interview talking points, and a STAR resume bullet point.
6. NEVER invent performance numbers. The project has not been built yet, so the resume
   bullet describes what was built and why, and leaves measured figures to the candidate.

Return JSON adhering to this exact schema:
{
  "title": "Concrete Project Name",
  "summary": "2-3 sentences on what this system does and why it proves senior-level engineering competence.",
  "architecture": "Clear description of the system architecture, component interactions, and data flow.",
  "milestones": [
    {
      "week": 1,
      "title": "Milestone Title",
      "objective": "Core objective of this phase",
      "tasks": ["Specific task 1", "Specific task 2", "Specific task 3"],
      "deliverable": "Verifiable end result of this week",
      "completed": false
    }
  ],
  "engineering_challenges": [
    {
      "challenge": "Specific technical hurdle (e.g., race conditions, backpressure, idempotency)",
      "solution": "How this project architecturally solves it",
      "impact": "Measurable benefit"
    }
  ],
  "resume_bullet_preview": "STAR-format bullet point: action verb, what was built, technologies used. No invented metrics.",
  "interview_talking_points": [
    "Tradeoff or design decision 1 to discuss with interviewers",
    "Tradeoff or design decision 2 to discuss with interviewers"
  ]
}"""


def generate_roadmap(
    target_skills: list[str],
    role_family: str = "backend",
    estimated_weeks: int = 3,
    candidate_strengths: list[str] | None = None,
) -> dict:
    """Generate an actionable multi-skill project learning roadmap."""
    strengths_str = (
        ", ".join(candidate_strengths[:10])
        if candidate_strengths
        else "general software development"
    )
    targets_str = ", ".join(target_skills)

    prompt = (
        f"ROLE FAMILY: {role_family}\n"
        f"TARGET SKILLS TO MASTER: {targets_str}\n"
        f"CANDIDATE EXISTING STRENGTHS: {strengths_str}\n"
        f"TIMELINE: {estimated_weeks} weeks\n\n"
        f"Design a comprehensive {estimated_weeks}-week engineering blueprint uniting these target skills."
    )

    try:
        raw = generate_json(_SYSTEM_PROMPT, prompt, timeout=300, max_tokens=2000)
        if isinstance(raw, dict) and _is_valid_roadmap(raw):
            return _format_roadmap(raw, target_skills, role_family, estimated_weeks)
    except Exception:  # noqa: BLE001
        pass

    # High-quality deterministic fallback if LLM times out or gives invalid schema
    return _fallback_roadmap(target_skills, role_family, estimated_weeks, candidate_strengths)


def _is_valid_roadmap(data: dict) -> bool:
    """Validate structure and ensure output is not generic."""
    if not isinstance(data, dict):
        return False
    title = str(data.get("title", "")).lower()
    summary = str(data.get("summary", "")).lower()
    if any(g in title or g in summary for g in _GENERIC):
        return False
    return bool(data.get("title") and data.get("milestones"))


def _format_roadmap(
    data: dict, target_skills: list[str], role_family: str, estimated_weeks: int
) -> dict:
    milestones = []
    raw_milestones = data.get("milestones", [])
    for idx, m in enumerate(raw_milestones):
        if not isinstance(m, dict):
            continue
        milestones.append(
            {
                "week": m.get("week", idx + 1),
                "title": m.get("title", f"Phase {idx + 1}"),
                "objective": m.get("objective", ""),
                "tasks": [str(t) for t in m.get("tasks", []) if t],
                "deliverable": m.get("deliverable", ""),
                "completed": bool(m.get("completed", False)),
            }
        )

    challenges = []
    for c in data.get("engineering_challenges", []):
        if isinstance(c, dict) and c.get("challenge"):
            challenges.append(
                {
                    "challenge": str(c.get("challenge", "")),
                    "solution": str(c.get("solution", "")),
                    "impact": str(c.get("impact", "")),
                }
            )

    return {
        "title": str(data.get("title", "Multi-Skill Systems Project")).strip(),
        "summary": str(data.get("summary", "")).strip(),
        "role_family": role_family,
        "target_skills": target_skills,
        "estimated_weeks": estimated_weeks,
        "architecture": str(data.get("architecture", "")).strip(),
        "milestones": milestones,
        "engineering_challenges": challenges,
        "resume_bullet_preview": str(
            data.get(
                "resume_bullet_preview",
                f"Built and deployed a high-throughput service with {', '.join(target_skills[:3])}.",
            )
        ).strip(),
        "interview_talking_points": [
            str(p) for p in data.get("interview_talking_points", []) if p
        ],
    }


def _fallback_roadmap(
    target_skills: list[str],
    role_family: str,
    estimated_weeks: int,
    candidate_strengths: list[str] | None = None,
) -> dict:
    """Deterministic, production-ready blueprint when LLM is unavailable."""
    primary_skills = target_skills[:4]
    skills_joined = ", ".join(primary_skills)

    title = f"High-Throughput Event Processing & Caching Service ({skills_joined})"
    summary = (
        f"A production-grade distributed backend service engineered to demonstrate mastery "
        f"of {skills_joined}. Handles high-volume asynchronous message ingestion, distributed state "
        f"caching, and containerized deployment with automated telemetry."
    )
    architecture = (
        "Client HTTP Requests -> API Gateway with Rate Limiting -> "
        f"Message Stream / Queue ({primary_skills[0] if primary_skills else 'Event Bus'}) -> "
        f"Worker Pool -> Storage & Caching Layer ({primary_skills[1] if len(primary_skills) > 1 else 'Cache'}) -> "
        "Prometheus & Grafana Observability Dashboard."
    )

    milestones = [
        {
            "week": 1,
            "title": f"Foundation, API Contracts & Core Ingestion with {primary_skills[0] if primary_skills else 'API'}",
            "objective": "Establish clean modular architecture, data schemas, and baseline request pipelines.",
            "tasks": [
                f"Design REST/gRPC interfaces and Pydantic/TypeScript validation models for data ingress.",
                f"Set up containerized local development environment with Docker and docker-compose.",
                "Implement structured logging and comprehensive unit test harness with 80%+ code coverage.",
            ],
            "deliverable": "Working Dockerized ingestion API with automated test suite and OpenAPI docs.",
            "completed": False,
        },
        {
            "week": 2,
            "title": f"Deep Integration & Optimization of {skills_joined}",
            "objective": "Implement core asynchronous workflows, caching tiers, and resilient failure handling.",
            "tasks": [
                f"Integrate {skills_joined} into the message pipeline with connection pooling and retry policies.",
                "Implement distributed locking and cache invalidation strategies to avoid stale state.",
                "Simulate high-throughput traffic load and benchmark performance bottlenecks.",
            ],
            "deliverable": "End-to-end event pipeline processing benchmarked under simulated peak load.",
            "completed": False,
        },
    ]

    if estimated_weeks >= 3:
        milestones.append(
            {
                "week": 3,
                "title": "Packaging, Observability, CI/CD & Portfolio Showcase",
                "objective": "Harden for production deployment, configure telemetry, and package for public review.",
                "tasks": [
                    "Configure GitHub Actions CI/CD pipeline for automated linting, testing, and Docker image builds.",
                    "Set up metrics collection (request duration, error rates, queue lag) with Prometheus.",
                    "Write detailed technical README with architectural diagrams, benchmark graphs, and reproduction steps.",
                ],
                "deliverable": "Public GitHub repository with clean documentation, CI badge, and live benchmark reports.",
                "completed": False,
            }
        )

    return {
        "title": title,
        "summary": summary,
        "role_family": role_family,
        "target_skills": target_skills,
        "estimated_weeks": estimated_weeks,
        "architecture": architecture,
        "milestones": milestones,
        "engineering_challenges": [
            {
                "challenge": "Handling traffic spikes and message backpressure without dropping events.",
                "solution": "Implemented decoupled asynchronous buffering with configurable consumer worker pools.",
                "impact": "Aims for no message loss under traffic bursts, with bounded memory.",
            },
            {
                "challenge": "Cache stampede and thundering herd problem during concurrent invalidations.",
                "solution": "Applied mutex-based distributed locking with probabilistic early cache recomputation.",
                "impact": "Aims to keep database read load flat across cache refresh cycles.",
            },
        ],
        # No numbers here on purpose: this project has not been built yet, and a
        # bullet that arrives pre-loaded with invented throughput figures is one
        # the candidate cannot defend in the interview it earns them.
        "resume_bullet_preview": (
            f"Built a distributed event-processing service with {skills_joined}, "
            f"handling asynchronous ingestion, cached reads and containerised deployment "
            f"(add your own measured throughput and latency once it runs)."
        ),
        "interview_talking_points": [
            f"Tradeoffs considered between push vs pull message delivery models when using {primary_skills[0] if primary_skills else 'queues'}.",
            "How distributed caching consistency was maintained across concurrent worker nodes.",
            "Strategies for graceful shutdown and in-flight transaction cleanup during service redeployments.",
        ],
    }
