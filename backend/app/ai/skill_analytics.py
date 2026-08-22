"""Macro skill gap intelligence and real-time market deficit analytics.

Scans all active jobs across company boards, categorizes demanded technologies,
cross-references the candidate's verified Knowledge Base, and quantifies the
exact score lift of acquiring specific skills.
"""
from collections import defaultdict
from copy import copy

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.match import (
    _ALIASES,
    _in_candidate,
    _norm,
    CandidateIndex,
    score as compute_full_score,
)
from app.db.models import Job, JobEmbedding, JobRequirements, KBChunk, Preferences
from app.ingestion.role_family import classify

# Skill domain categorization rules
_CATEGORIES = {
    "Languages": {
        "python", "javascript", "typescript", "java", "c++", "cpp", "c#", "go",
        "golang", "rust", "ruby", "php", "kotlin", "swift", "scala", "sql",
        "html", "css", "r", "dart", "bash", "shell", "c",
    },
    "Backend & APIs": {
        "fastapi", "flask", "django", "node", "nodejs", "express", "spring",
        "spring boot", "microservices", "rest", "restful", "rest api", "graphql",
        "grpc", "celery", "asp.net", "nest.js", "nestjs", "gin", "fiber",
        "api design", "backend",
    },
    "Databases & Storage": {
        "postgresql", "postgres", "psql", "mysql", "mongodb", "mongo", "redis",
        "elasticsearch", "sqlite", "cassandra", "dynamodb", "oracle", "firebase",
        "supabase", "memcached", "neo4j", "mariadb", "database design", "nosql",
    },
    "Cloud & DevOps": {
        "docker", "kubernetes", "k8s", "aws", "amazon web services", "gcp",
        "google cloud", "azure", "ci/cd", "cicd", "terraform", "linux", "git",
        "github actions", "gitlab", "jenkins", "prometheus", "grafana", "nginx",
        "ansible", "cloud computing", "devops",
    },
    "Frontend & Mobile": {
        "react", "reactjs", "react.js", "next.js", "nextjs", "vue", "vue.js",
        "angular", "svelte", "tailwind", "tailwindcss", "redux", "react native",
        "flutter", "android", "ios", "webpack", "vite", "frontend", "ui/ux",
    },
    "Data, AI & Messaging": {
        "kafka", "rabbitmq", "pytorch", "tensorflow", "machine learning", "ml",
        "deep learning", "dl", "nlp", "natural language processing", "llm",
        "large language models", "pandas", "numpy", "spark", "hadoop",
        "data engineering", "data pipelines", "airflow", "event-driven",
    },
    "Testing & Core CS": {
        "pytest", "unittest", "jest", "cypress", "selenium", "unit testing",
        "system design", "data structures", "algorithms", "oop",
        "object oriented programming", "agile", "scrum", "tdd", "design patterns",
        "operating systems", "computer networks",
    },
}


def categorize_skill(skill_name: str) -> str:
    """Classify a skill into a structured domain category."""
    norm = _norm(skill_name)
    resolved = _ALIASES.get(norm, norm)

    for category, terms in _CATEGORIES.items():
        if resolved in terms or any(t in resolved for t in terms if len(t) > 3):
            return category
    return "Core & Tools"


def analyze_market_skills(
    db: Session, role_family: str | None = None
) -> dict:
    """Analyze all active jobs in the DB to extract macro market skill demand and candidate deficits."""
    chunks = list(db.scalars(select(KBChunk)))
    candidate = CandidateIndex(chunks)

    # Fetch active jobs and requirements
    stmt = (
        select(Job, JobRequirements)
        .outerjoin(JobRequirements, Job.id == JobRequirements.job_id)
        .where(Job.status == "active")
    )
    results = db.execute(stmt).all()

    total_active_jobs = 0
    skill_demand = defaultdict(
        lambda: {
            "name": "",
            "frequency": 0,
            "required_count": 0,
            "preferred_count": 0,
            "companies": set(),
            "role_families": set(),
            "potential_score_lift_sum": 0.0,
        }
    )

    for job, reqs in results:
        job_family = classify(job.title)
        if role_family and role_family != "all" and job_family != role_family:
            continue

        req_skills = list(reqs.required_skills or []) if reqs else []
        pref_skills = list(reqs.preferred_skills or []) if reqs else []
        # A job whose requirements have not been extracted yet says nothing about
        # skills. Counting it in the denominator would report "wanted in 3 jobs
        # (2%)" for a skill named by 3 of the 5 postings we can actually read.
        if not req_skills and not pref_skills:
            continue

        total_active_jobs += 1

        # Track required skills (weighted higher for coverage lift)
        num_req = max(1, len(req_skills))
        for skill in req_skills:
            norm = _norm(str(skill))
            if not norm or len(norm) < 2:
                continue
            canonical = _ALIASES.get(norm, norm)
            entry = skill_demand[canonical]
            entry["name"] = str(skill).strip()
            entry["frequency"] += 1
            entry["required_count"] += 1
            if job.company:
                entry["companies"].add(job.company)
            entry["role_families"].add(job_family)
            # Required coverage weight is 0.30 in matching formula
            entry["potential_score_lift_sum"] += 0.30 / num_req

        # Track preferred skills
        num_pref = max(1, len(pref_skills))
        for skill in pref_skills:
            norm = _norm(str(skill))
            if not norm or len(norm) < 2:
                continue
            canonical = _ALIASES.get(norm, norm)
            entry = skill_demand[canonical]
            if not entry["name"]:
                entry["name"] = str(skill).strip()
            entry["frequency"] += 1
            entry["preferred_count"] += 1
            if job.company:
                entry["companies"].add(job.company)
            entry["role_families"].add(job_family)
            # Preferred coverage weight is 0.15 in matching formula
            entry["potential_score_lift_sum"] += 0.15 / num_pref

    if total_active_jobs == 0:
        return {
            "total_jobs_analyzed": 0,
            "candidate_skills_count": len(candidate.terms),
            "market_readiness_pct": 0.0,
            "missing_skills_count": 0,
            "mastered_skills_count": 0,
            "top_missing_skills": [],
            "top_mastered_skills": [],
            "domain_clusters": [],
        }

    missing_items = []
    mastered_items = []
    cluster_map = defaultdict(lambda: {"mastered": [], "missing": []})

    total_requirements_count = 0
    mastered_requirements_count = 0

    for canonical, data in skill_demand.items():
        name = data["name"]
        freq = data["frequency"]
        pct = round((freq / total_active_jobs) * 100, 1)
        is_mastered = _in_candidate(canonical, candidate)
        category = categorize_skill(name)

        importance = round(
            (data["required_count"] * 1.0 + data["preferred_count"] * 0.5)
            / total_active_jobs,
            3,
        )
        # Average match score lift on the specific jobs that demand this skill
        avg_lift = (
            round((data["potential_score_lift_sum"] / max(1, freq)) * 100, 1)
            if not is_mastered
            else 0.0
        )

        item = {
            "skill": name.title() if len(name) > 3 else name.upper(),
            "frequency": freq,
            "percentage": pct,
            "is_mastered": is_mastered,
            "category": category,
            "importance": importance,
            "potential_score_lift": avg_lift,
            "sample_companies": sorted(data["companies"])[:4],
        }

        total_requirements_count += freq
        if is_mastered:
            mastered_requirements_count += freq
            mastered_items.append(item)
            cluster_map[category]["mastered"].append(item)
        else:
            missing_items.append(item)
            cluster_map[category]["missing"].append(item)

    # Sort missing by combined impact (frequency and potential score lift)
    missing_items.sort(
        key=lambda x: (x["frequency"] * (x["potential_score_lift"] + 0.1)),
        reverse=True,
    )
    mastered_items.sort(key=lambda x: x["frequency"], reverse=True)

    readiness = (
        round((mastered_requirements_count / total_requirements_count) * 100, 1)
        if total_requirements_count > 0
        else 0.0
    )

    domain_clusters = []
    for cat_name, groups in cluster_map.items():
        all_cat_skills = sorted(
            groups["mastered"] + groups["missing"],
            key=lambda x: x["frequency"],
            reverse=True,
        )
        domain_clusters.append(
            {
                "category": cat_name,
                "mastered_count": len(groups["mastered"]),
                "missing_count": len(groups["missing"]),
                "skills": all_cat_skills[:12],
            }
        )

    # Sort clusters with largest missing gaps first
    domain_clusters.sort(key=lambda c: c["missing_count"], reverse=True)

    return {
        "total_jobs_analyzed": total_active_jobs,
        "candidate_skills_count": len(candidate.terms),
        "market_readiness_pct": readiness,
        # The lists are the top slice; the counts are the whole truth, so the
        # summary cards say "31 gaps" rather than the 16 that fit on screen.
        "missing_skills_count": len(missing_items),
        "mastered_skills_count": len(mastered_items),
        "top_missing_skills": missing_items[:16],
        "top_mastered_skills": mastered_items[:16],
        "domain_clusters": domain_clusters,
    }


def simulate_skill_acquisition(
    target_skills: list[str], db: Session
) -> dict:
    """Simulate acquiring a set of target skills and measure exact match score changes."""
    chunks = list(db.scalars(select(KBChunk)))
    candidate = CandidateIndex(chunks)

    # Synthesize candidate index with new target skills
    augmented_terms = set(candidate.terms)
    for s in target_skills:
        augmented_terms.add(_norm(s))
        canonical = _ALIASES.get(_norm(s))
        if canonical:
            augmented_terms.add(canonical)

    # A shallow copy keeps the (read-only) embedding matrix and swaps in the
    # widened term set, so the simulated candidate is the real one plus skills.
    augmented_candidate = copy(candidate)
    augmented_candidate.terms = augmented_terms
    augmented_candidate.text = (
        candidate.text + " " + " ".join(_norm(s) for s in target_skills)
    )

    preferences = db.scalar(select(Preferences))

    # Fetch active jobs and their requirements + embeddings + matches
    stmt = (
        select(Job, JobRequirements, JobEmbedding)
        .join(JobRequirements, Job.id == JobRequirements.job_id)
        .join(JobEmbedding, Job.id == JobEmbedding.job_id)
        .where(Job.status == "active")
    )
    rows = db.execute(stmt).all()

    if not rows:
        return {
            "target_skills": target_skills,
            "previous_avg_score": 0.0,
            "new_avg_score": 0.0,
            "avg_lift": 0.0,
            "unlocked_jobs_count": 0,
            "impacted_jobs": [],
        }

    old_scores = []
    new_scores = []
    impacted = []
    unlocked_count = 0

    for job, reqs, emb in rows:
        requirements_dict = {
            "required_skills": list(reqs.required_skills or []),
            "preferred_skills": list(reqs.preferred_skills or []),
            "responsibilities": list(reqs.responsibilities or []),
            "seniority": reqs.seniority,
            "min_years": reqs.min_years,
            "confidence": reqs.confidence,
        }

        # Calculate new score with augmented candidate
        new_result = compute_full_score(
            job=job,
            requirements=requirements_dict,
            job_vector=emb.embedding,
            candidate=augmented_candidate,
            preferences=preferences,
        )

        # Both sides come from the same scorer on purpose. The stored Match may
        # be a cheap-tier "estimated" score, and differencing that against a full
        # score would report the change of tier as if it were the skill's lift.
        old_score = compute_full_score(
            job=job,
            requirements=requirements_dict,
            job_vector=emb.embedding,
            candidate=candidate,
            preferences=preferences,
        )["score"]

        new_score = new_result["score"]
        lift = round(new_score - old_score, 4)

        old_scores.append(old_score)
        new_scores.append(new_score)

        # Count jobs that crossed into strong match territory (>= 0.60 or >= 0.70)
        if old_score < 0.60 and new_score >= 0.60:
            unlocked_count += 1

        if lift > 0.01:
            impacted.append(
                {
                    "job_id": job.id,
                    "company": job.company,
                    "title": job.title,
                    "old_score": round(old_score * 100, 1),
                    "new_score": round(new_score * 100, 1),
                    "score_lift": round(lift * 100, 1),
                }
            )

    impacted.sort(key=lambda x: x["score_lift"], reverse=True)

    prev_avg = (sum(old_scores) / len(old_scores)) * 100 if old_scores else 0.0
    new_avg = (sum(new_scores) / len(new_scores)) * 100 if new_scores else 0.0

    return {
        "target_skills": target_skills,
        "previous_avg_score": round(prev_avg, 1),
        "new_avg_score": round(new_avg, 1),
        "avg_lift": round(new_avg - prev_avg, 1),
        "unlocked_jobs_count": unlocked_count,
        "impacted_jobs": impacted[:10],
    }
