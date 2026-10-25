from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Assignment:
    id: str
    course_id: str
    course_name: str
    name: str
    description: str = ""
    rubric: list[dict] = field(default_factory=list)  # [{"criterion": str, "points": float}]
    points_possible: Optional[float] = None
    score: Optional[float] = None
    url: Optional[str] = None

    def source_text(self) -> str:
        """Everything the model is allowed to quote from."""
        rubric = "\n".join(f"- {r['criterion']} ({r.get('points', '?')} pts)" for r in self.rubric)
        return f"{self.name}\n{self.description}\n{rubric}".strip()

    def grade_ratio(self) -> Optional[float]:
        if self.score is None or not self.points_possible:
            return None
        return max(0.0, min(1.0, self.score / self.points_possible))

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SkillEvidence:
    skill: str
    level: str  # "familiar" | "working" | "strong"
    course: str
    assignment: str
    assignment_id: str
    quote: str  # verbatim span from the assignment text that justifies the skill
    rubric_criterion: Optional[str] = None
    confidence: float = 0.5

    @property
    def evidence_id(self) -> str:
        return f"{self.assignment_id}:{self.skill}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["evidence_id"] = self.evidence_id
        return d


@dataclass
class Job:
    id: str
    company: str
    title: str
    location: str
    url: str
    description: str

    def to_dict(self) -> dict:
        return asdict(self)
