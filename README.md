# Proof of Skill (working title)

Maps your Canvas coursework to evidence-backed skills, matches them to live jobs,
and explains each match by naming the real class and assignment, plus one gap to close.

## Why it's trustworthy

1. **Quotes must be verbatim.** Every extracted skill carries a quote copied from the
   assignment text. If the quote isn't found in the source, the skill is dropped.
2. **Matches must cite evidence.** A job recommendation is discarded unless it cites real
   evidence ids and names a real course or assignment.
3. **Ungraded work counts for less.** Confidence blends the claimed level with your grade.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY (and Canvas + boards for live data)
```

## Run

```bash
python src/cli.py sync --sample        # or: python src/cli.py sync   (live Canvas)
python src/cli.py extract              # evidence-backed skills
python src/cli.py jobs --title "intern|engineer"
python src/cli.py match --top 10
python src/cli.py bullets --skill "graph"
```

Set `GREENHOUSE_BOARDS` to board slugs (the part in `boards.greenhouse.io/<slug>`).

## Layout

| File | Job |
| --- | --- |
| `src/canvas.py` | Canvas API client with pagination, rubric and grade pull |
| `src/extract.py` | LLM skill extraction + verbatim-quote guardrail |
| `src/jobs.py` | Greenhouse job fetcher |
| `src/match.py` | TF-IDF recall, LLM rerank with citation checks, resume bullets |
| `src/cli.py` | Command-line entry point |

## Cubbie Skill

The Cubbie integration is packaged as
[skills/coursework-job-match/SKILL.md](skills/coursework-job-match/SKILL.md). It uses
Cubbie's connected Canvas access and public job browsing; it does not require a
separate API key. Text the public GitHub repository or the Skill folder link to
Cubbie to install it, then ask for coursework-based internship matches.

## Next steps

- Skill taxonomy (ESCO / O*NET) and a skill graph with prerequisites
- Lever and Adzuna sources; campus jobs and research postings
- SMS delivery (Twilio) on a schedule
- AWS: EventBridge + SQS + Lambda workers, DynamoDB for evidence records
- Privacy: encrypted token storage, one-click delete, no training on student data
