import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import extract as ex
import jobs as jb
import match as mt
from models import Assignment, Job, SkillEvidence

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample_assignments.json"


def load():
    return [Assignment(**a) for a in json.loads(SAMPLE.read_text())]


def test_verbatim_quote_accepted():
    a = load()[0]
    assert ex.quote_is_verbatim("detects prerequisite cycles using depth-first search", a.source_text())


def test_fabricated_quote_rejected():
    a = load()[0]
    assert not ex.quote_is_verbatim("implemented a Kubernetes operator in Go", a.source_text())


def test_short_quote_rejected():
    a = load()[0]
    assert not ex.quote_is_verbatim("graph", a.source_text())


def test_confidence_rewards_grade_and_penalizes_ungraded():
    a = load()[0]
    graded = ex._confidence("working", a)
    a.score = None
    assert graded > ex._confidence("working", a)


def _evidence():
    return [
        SkillEvidence("graph algorithms", "strong", "CSE 310 Data Structures and Algorithms",
                      "Project 3: Course Scheduler", "1001", "cycles using depth-first search", None, 0.8),
        SkillEvidence("docker", "working", "CSE 464 Software Quality Assurance",
                      "Assignment 2: CI Pipeline and Test Automation", "1003", "Dockerized service", None, 0.6),
    ]


def test_recall_prefers_relevant_job():
    jobs = [
        Job("a", "Acme", "Graphic Designer", "Remote", "u", "Photoshop branding illustration typography"),
        Job("b", "Beta", "Backend Intern", "Remote", "u", "graph algorithms docker services backend"),
    ]
    ranked = mt.recall(_evidence(), jobs, k=2)
    assert ranked[0][0].id == "b"


class _FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.messages = self

    def create(self, **kw):
        class R:  # minimal response shape
            content = [type("C", (), {"text": json.dumps(self.payload)})()]
        return R()


def _job():
    return Job("b", "Beta", "Backend Intern", "Remote", "u", "graph algorithms")


def test_rerank_drops_uncited_recommendation():
    payload = {"fit": 90, "why_fit": "Great fit.", "evidence_ids": ["nope:nope"], "gap": "", "gap_action": ""}
    assert mt.rerank_one(_FakeClient(payload), _evidence(), _job()) is None


def test_rerank_drops_recommendation_without_real_assignment_name():
    payload = {"fit": 90, "why_fit": "You are a strong engineer.", "evidence_ids": ["1001:graph algorithms"],
               "gap": "", "gap_action": ""}
    assert mt.rerank_one(_FakeClient(payload), _evidence(), _job()) is None


def test_rerank_keeps_grounded_recommendation():
    payload = {"fit": 88, "why_fit": "Your Project 3: Course Scheduler in CSE 310 used graph search.",
               "evidence_ids": ["1001:graph algorithms", "bogus"], "gap": "AWS", "gap_action": "Deploy it on Lambda"}
    out = mt.rerank_one(_FakeClient(payload), _evidence(), _job())
    assert out and out["evidence_ids"] == ["1001:graph algorithms"]


def test_rerank_deduplicates_cited_evidence():
    payload = {"fit": 88, "why_fit": "Your Project 3: Course Scheduler in CSE 310 used graph search.",
               "evidence_ids": ["1001:graph algorithms", "1001:graph algorithms"], "gap": "", "gap_action": ""}
    out = mt.rerank_one(_FakeClient(payload), _evidence(), _job())
    assert out and out["evidence_ids"] == ["1001:graph algorithms"]


def test_fetch_greenhouse_uses_company_name_not_board_slug(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "jobs": [{
                    "id": "123",
                    "title": "Platform Engineer",
                    "location": {"name": "Remote"},
                    "absolute_url": "https://example.com/job/123",
                    "content": "Build systems",
                    "company_name": "Example Labs",
                }]
            }

    monkeypatch.setattr(jb.requests, "get", lambda *args, **kwargs: FakeResponse())
    jobs = jb.fetch_greenhouse("example-board")
    assert jobs and jobs[0].company == "Example Labs"
