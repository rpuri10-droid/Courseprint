"""CLI: sync -> extract -> match -> bullets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

import extract as ex
import jobs as jb
import match as mt
from models import Assignment, SkillEvidence

DATA = Path(__file__).resolve().parent.parent / "data"
ASSIGNMENTS = DATA / "assignments.json"
EVIDENCE = DATA / "evidence.json"
JOBS = DATA / "jobs.json"
SAMPLE = DATA / "sample_assignments.json"


def load_assignments(path: Path) -> list[Assignment]:
    return [Assignment(**a) for a in json.loads(path.read_text())]


def load_evidence() -> list[SkillEvidence]:
    return [
        SkillEvidence(**{k: v for k, v in e.items() if k != "evidence_id"})
        for e in json.loads(EVIDENCE.read_text())
    ]


def cmd_sync(args):
    if args.sample:
        ASSIGNMENTS.write_text(SAMPLE.read_text())
        print(f"Using sample data: {len(load_assignments(ASSIGNMENTS))} assignments")
        return
    from canvas import CanvasClient

    items = CanvasClient().all_assignments()
    ASSIGNMENTS.write_text(json.dumps([a.to_dict() for a in items], indent=2))
    print(f"Synced {len(items)} assignments")


def cmd_extract(args):
    evidence = ex.extract_all(load_assignments(ASSIGNMENTS))
    EVIDENCE.write_text(json.dumps([e.to_dict() for e in evidence], indent=2))
    print(f"{len(evidence)} verified skill records")
    for e in sorted(evidence, key=lambda e: -e.confidence)[:15]:
        print(f"  {e.confidence:.2f}  {e.skill:<30} <- {e.course} / {e.assignment}")


def cmd_jobs(args):
    found = jb.fetch_all(title_filter=args.title)
    JOBS.write_text(json.dumps([j.to_dict() for j in found], indent=2))
    print(f"Fetched {len(found)} jobs")


def cmd_match(args):
    from models import Job

    jobs = [Job(**j) for j in json.loads(JOBS.read_text())]
    results = mt.match(load_evidence(), jobs, top=args.top)
    for r in results:
        j = r["job"]
        print(f"\n[{r['fit']}] {j['title']} - {j['company']} ({j['location']})\n  {j['url']}")
        print(f"  Why you fit: {r['why_fit']}")
        if r.get("gap"):
            print(f"  Gap: {r['gap']} -> {r['gap_action']}")


def cmd_bullets(args):
    for b in mt.resume_bullets(load_evidence(), args.skill):
        print(f"- {b}")


def main():
    load_dotenv()
    p = argparse.ArgumentParser(prog="proof-of-skill")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sync", help="pull Canvas assignments")
    s.add_argument("--sample", action="store_true", help="use bundled sample data")
    s.set_defaults(fn=cmd_sync)

    sub.add_parser("extract", help="build evidence-backed skills").set_defaults(fn=cmd_extract)

    j = sub.add_parser("jobs", help="fetch job postings")
    j.add_argument("--title", help="regex filter on job title, e.g. 'intern|engineer'")
    j.set_defaults(fn=cmd_jobs)

    m = sub.add_parser("match", help="rank jobs, explain fit and gap")
    m.add_argument("--top", type=int, default=10)
    m.set_defaults(fn=cmd_match)

    b = sub.add_parser("bullets", help="resume bullets from real work")
    b.add_argument("--skill", help="filter by skill substring")
    b.set_defaults(fn=cmd_bullets)

    args = p.parse_args()
    DATA.mkdir(exist_ok=True)
    args.fn(args)


if __name__ == "__main__":
    main()
