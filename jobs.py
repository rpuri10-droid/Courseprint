"""Job sources. Start with Greenhouse public boards; add Lever/Adzuna later."""
from __future__ import annotations

import os
import re
from html import unescape

import requests

from models import Job

TAG_RE = re.compile(r"<[^>]+>")


def _clean(html: str) -> str:
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", unescape(unescape(html or "")))).strip()


def fetch_greenhouse(board: str) -> list[Job]:
    r = requests.get(
        f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
        params={"content": "true"},
        timeout=30,
    )
    r.raise_for_status()
    jobs = []
    for j in r.json().get("jobs", []):
        company = (
            j.get("company_name")
            or (j.get("company") or {}).get("name")
            or ((j.get("offices") or [{}])[0]).get("name")
            or board
        )
        location = (j.get("location") or {}).get("name") or ((j.get("offices") or [{}])[0]).get("location")
        jobs.append(
            Job(
                id=f"gh:{board}:{j['id']}",
                company=company,
                title=j.get("title", ""),
                location=location,
                url=j.get("absolute_url", ""),
                description=_clean(j.get("content", "")),
            )
        )
    return jobs


def fetch_all(boards: list[str] | None = None, title_filter: str | None = None) -> list[Job]:
    boards = boards or [b.strip() for b in os.environ.get("GREENHOUSE_BOARDS", "").split(",") if b.strip()]
    jobs: list[Job] = []
    for b in boards:
        try:
            jobs.extend(fetch_greenhouse(b))
        except requests.RequestException as e:
            print(f"[jobs] skipped board {b}: {e}")
    if title_filter:
        try:
            pat = re.compile(title_filter, re.I)
        except re.error:
            print(f"[jobs] invalid title filter {title_filter!r}; ignoring filter")
        else:
            jobs = [j for j in jobs if pat.search(j.title)]
    return jobs
