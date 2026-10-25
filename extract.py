"""Evidence-first skill extraction.

Every skill must carry a verbatim quote from the assignment text. Quotes that
cannot be found in the source are dropped, so the profile cannot claim skills
the coursework doesn't show.
"""
from __future__ import annotations

import json
import os
import re

import anthropic

from models import Assignment, SkillEvidence

SYSTEM = """You extract demonstrable skills from a student's coursework.

Rules:
- Only list a skill if the assignment text clearly required it. Do not guess.
- Each skill needs a `quote`: an exact, contiguous span copied from the assignment text.
- `skill` is a short, normalized noun phrase (e.g. "REST API design", "graph algorithms").
- `level`: "familiar" (read/used briefly), "working" (built something with it), "strong" (core of a substantial deliverable).
- `rubric_criterion`: the rubric line that best matches, or null.
- Return JSON only: {"skills": [{"skill": str, "level": str, "quote": str, "rubric_criterion": str|null}]}
- If nothing qualifies, return {"skills": []}."""

LEVEL_WEIGHT = {"familiar": 0.4, "working": 0.7, "strong": 0.9}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def quote_is_verbatim(quote: str, source: str) -> bool:
    q = _norm(quote)
    return len(q) >= 12 and q in _norm(source)


def normalize_skill(skill: str) -> str:
    return re.sub(r"\s+", " ", skill).strip().lower()


def _confidence(level: str, a: Assignment) -> float:
    base = LEVEL_WEIGHT.get(level, 0.4)
    ratio = a.grade_ratio()
    if ratio is None:
        return round(base * 0.8, 2)  # ungraded work is weaker evidence
    return round(base * (0.5 + 0.5 * ratio), 2)


def parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {"skills": []}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"skills": []}


def extract_for_assignment(client: anthropic.Anthropic, a: Assignment) -> list[SkillEvidence]:
    source = a.source_text()
    if len(source) < 40:  # nothing to ground a claim in
        return []
    resp = client.messages.create(
        model=os.environ.get("MODEL", "claude-sonnet-5-5"),
        max_tokens=1500,
        system=SYSTEM,
        messages=[{"role": "user", "content": f"Course: {a.course_name}\n\n{source}"}],
    )
    data = parse_json(resp.content[0].text)
    out: list[SkillEvidence] = []
    for s in data.get("skills", []):
        if not quote_is_verbatim(s.get("quote", ""), source):
            continue  # guardrail: unverifiable claim
        level = s.get("level", "familiar")
        out.append(
            SkillEvidence(
                skill=normalize_skill(s["skill"]),
                level=level,
                course=a.course_name,
                assignment=a.name,
                assignment_id=a.id,
                quote=s["quote"].strip(),
                rubric_criterion=s.get("rubric_criterion"),
                confidence=_confidence(level, a),
            )
        )
    return out


def extract_all(assignments: list[Assignment]) -> list[SkillEvidence]:
    client = anthropic.Anthropic()
    out: list[SkillEvidence] = []
    for a in assignments:
        out.extend(extract_for_assignment(client, a))
    return out
