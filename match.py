"""Two-stage matching: TF-IDF recall, then an LLM rerank that must cite evidence."""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict

import anthropic
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from models import Job, SkillEvidence


def profile_text(evidence: list[SkillEvidence]) -> str:
    # Repeat stronger skills so they weigh more in TF-IDF.
    parts = []
    for e in evidence:
        parts.extend([e.skill] * (1 + int(e.confidence * 3)))
    return " ".join(parts)


def recall(evidence: list[SkillEvidence], jobs: list[Job], k: int = 15) -> list[tuple[Job, float]]:
    if not evidence or not jobs:
        return []
    docs = [profile_text(evidence)] + [f"{j.title} {j.description}" for j in jobs]
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1)
    m = vec.fit_transform(docs)
    sims = cosine_similarity(m[0], m[1:]).ravel()
    ranked = sorted(zip(jobs, sims), key=lambda x: x[1], reverse=True)
    return ranked[:k]


RERANK_SYSTEM = """You advise a student on one job posting.

You get the student's evidence records (each has an evidence_id, skill, course, assignment) and a job.
Return JSON only:
{"fit": 0-100, "why_fit": str, "evidence_ids": [str], "gap": str, "gap_action": str}

Rules:
- why_fit is 1-2 sentences and MUST name a real course and assignment from the evidence records.
- evidence_ids lists the records you relied on; use only ids you were given.
- gap is the single most important skill the job wants that no evidence record shows. If none, use "".
- gap_action is one concrete step to close it (a project, a course, a certification). Empty if no gap.
- Never claim a skill that is not in the evidence records."""


def rerank_one(client: anthropic.Anthropic, evidence: list[SkillEvidence], job: Job) -> dict | None:
    ev = [
        {k: e.to_dict()[k] for k in ("evidence_id", "skill", "level", "course", "assignment")}
        for e in evidence
    ]
    msg = f"EVIDENCE:\n{json.dumps(ev)}\n\nJOB: {job.title} at {job.company} ({job.location})\n{job.description[:3000]}"
    resp = client.messages.create(
        model=os.environ.get("MODEL", "claude-sonnet-5-5"),
        max_tokens=600,
        system=RERANK_SYSTEM,
        messages=[{"role": "user", "content": msg}],
    )
    out = _parse_obj(resp.content[0].text)
    if not out:
        return None
    valid = {e.evidence_id for e in evidence}
    cited = []
    seen = set()
    for item in out.get("evidence_ids", []):
        if item in valid and item not in seen:
            cited.append(item)
            seen.add(item)
    if not cited:  # guardrail: no citation, no recommendation
        return None
    by_id = {e.evidence_id: e for e in evidence}
    names_real_work = any(
        by_id[i].assignment.lower() in out.get("why_fit", "").lower()
        or by_id[i].course.lower() in out.get("why_fit", "").lower()
        for i in cited
    )
    if not names_real_work:
        return None
    out["evidence_ids"] = cited
    return out


def _parse_obj(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def match(evidence: list[SkillEvidence], jobs: list[Job], top: int = 10) -> list[dict]:
    client = anthropic.Anthropic()
    results = []
    for job, sim in recall(evidence, jobs, k=max(top * 2, 15)):
        r = rerank_one(client, evidence, job)
        if r:
            results.append({"job": job.to_dict(), "recall": round(float(sim), 3), **r})
    results.sort(key=lambda r: r.get("fit", 0), reverse=True)
    return results[:top]


BULLET_SYSTEM = """Write resume bullets from a student's real coursework.
Rules: one line each, past tense, start with a strong verb, no invented metrics or tools.
Only use facts present in the evidence records. Return JSON: {"bullets": [str]}"""


def resume_bullets(evidence: list[SkillEvidence], skill_filter: str | None = None, n: int = 4) -> list[str]:
    pool = [e for e in evidence if not skill_filter or skill_filter.lower() in e.skill]
    grouped = defaultdict(list)
    for e in pool:
        grouped[e.assignment_id].append(e)
    if not grouped:
        return []
    payload = [
        {
            "course": es[0].course,
            "assignment": es[0].assignment,
            "skills": [e.skill for e in es],
            "source_quotes": [e.quote for e in es],
        }
        for es in grouped.values()
    ]
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=os.environ.get("MODEL", "claude-sonnet-5-5"),
        max_tokens=800,
        system=BULLET_SYSTEM,
        messages=[{"role": "user", "content": f"Write up to {n} bullets.\n{json.dumps(payload)}"}],
    )
    out = _parse_obj(resp.content[0].text) or {}
    return out.get("bullets", [])
