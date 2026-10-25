"""Canvas REST API client (student access token)."""
from __future__ import annotations

import os
import re
from html import unescape

import requests

from models import Assignment

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def strip_html(html: str | None) -> str:
    if not html:
        return ""
    text = TAG_RE.sub(" ", html)
    return WS_RE.sub(" ", unescape(text)).strip()


class CanvasClient:
    def __init__(self, base_url: str | None = None, token: str | None = None):
        self.base = (base_url or os.environ["CANVAS_BASE_URL"]).rstrip("/")
        token = token or os.environ["CANVAS_TOKEN"]
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"Bearer {token}"

    def _get_all(self, path: str, params: dict | None = None) -> list[dict]:
        """Follow Canvas Link-header pagination."""
        url = f"{self.base}/api/v1{path}"
        params = {"per_page": 100, **(params or {})}
        out: list[dict] = []
        while url:
            r = self.s.get(url, params=params, timeout=30)
            r.raise_for_status()
            out.extend(r.json())
            url = r.links.get("next", {}).get("url")
            params = None  # the next-link already carries the query string
        return out

    def courses(self) -> list[dict]:
        cs = self._get_all("/courses", {"enrollment_state": "active", "enrollment_type": "student"})
        return [c for c in cs if c.get("name")]

    def assignments(self, course: dict) -> list[Assignment]:
        raw = self._get_all(
            f"/courses/{course['id']}/assignments",
            {"include[]": ["submission", "rubric_settings"], "order_by": "due_at"},
        )
        out = []
        for a in raw:
            sub = a.get("submission") or {}
            rubric = [
                {"criterion": r.get("description", ""), "points": r.get("points")}
                for r in (a.get("rubric") or [])
            ]
            out.append(
                Assignment(
                    id=str(a["id"]),
                    course_id=str(course["id"]),
                    course_name=course["name"],
                    name=a.get("name", ""),
                    description=strip_html(a.get("description")),
                    rubric=rubric,
                    points_possible=a.get("points_possible"),
                    score=sub.get("score"),
                    url=a.get("html_url"),
                )
            )
        return out

    def all_assignments(self) -> list[Assignment]:
        result: list[Assignment] = []
        for c in self.courses():
            result.extend(self.assignments(c))
        return result
