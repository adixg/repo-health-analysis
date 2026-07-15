# Checkpoint 3 — Verified Questions Evaluation

**Date:** July 2026  
**Evaluator:** Aditya Ghosh  
**Ground truth source:** Streamlit dashboard metrics, PostgreSQL (`reposense` DB), and `scripts/verify_setup.py` ingestion on six public repositories.

**Method:** For metric questions, the expected value was read from deterministic analytics (`src/analytics/`). For chat questions, the expected value was cross-checked against the Issues tab metrics and retrieved evidence chunks; answers were generated via the dashboard Chat tab (`GroundedChatAgent` + Ollama `qwen2.5:3b`).

---

| # | Question | Repo | Expected (ground truth) | System answer | Correct? | Evidence cited? |
|---|----------|------|-------------------------|---------------|----------|-----------------|
| 1 | How many stale open issues (>90 days)? | psf/requests | **141** stale open issues (Issues tab / `calculate_issue_metrics`) | Dashboard Issues tab: **141** | Yes | n/a |
| 2 | What is the issue closure rate? | fastai/fastai | **87.4%** (closure_rate = 0.874) | Dashboard Issues tab: **87%** (0.874) | Yes | n/a |
| 3 | Who is the top contributor? | explosion/spaCy | **ines** with **32.6%** share (0.326) | Dashboard Contributors tab: **ines**, ~**33%** concentration | Yes | n/a |
| 4 | How many commits in the last 6 months? | scikit-learn/scikit-learn | **531** commits | Dashboard Commits tab: **531** | Yes | n/a |
| 5 | What is the most common issue label? | psf/requests | **Bug** — 130 issues (15.8% of label assignments) | Dashboard Issues label chart: **Bug** (130) | Yes | n/a |
| 6 | Which repository has the highest PR merge rate? | (all 6 repos) | **explosion/spaCy** — **87.9%** (0.879) | Compare tab: spaCy highest merge rate | Yes | n/a |
| 7 | Is commit activity declining for this repo? | fastai/fastai | **Yes** — activity change **-28.9%** (27 commits last 6 mo vs prior period) | Commits tab shows negative activity change (~**-29%**) | Yes | n/a |
| 8 | How do stars correlate with stale open issues across repos? | (all 6 repos) | Spearman **ρ ≈ 0.086** (n=6) — weak positive association, exploratory only | Correlations tab (stars vs stale_open_issues): coefficient ≈ **0.086** | Yes | n/a |
| 9 | How many stale open issues does this repository have? | psf/requests | **141** (precomputed metric) | Chat: *"The repository has **141** stale open issues based on evidence [3]."* | Yes | Yes — cites [3] |
| 10 | What SSL or certificate verification problems do users report? | psf/requests | Issues/comments mention SSL verification errors, unfriendly error messages, and need for troubleshooting docs (e.g. issue themes around certificate verification) | Chat: Users report SSL verification errors that are not end-user friendly; suggests adding troubleshooting guidance. Cites **[2]** and **[3]**. | Yes | Yes — cites [2], [3] |

---

## Notes

- Rows 1–8 validate **deterministic analytics** (dashboard / SQL / correlation engine). The LLM is not used.
- Rows 9–10 validate **grounded chat**: the model must use precomputed metrics and retrieved evidence, not invent counts.
- Row 8 is **exploratory correlation** with only six repositories — not presented as causal.
- Chat row 9 correctly reused the precomputed stale-issue count (141) and cited retrieved evidence.
- Chat row 10 grounded its answer in issue titles/bodies about certificate verification and documentation gaps.

## Reproduction

```powershell
cd repo-health-analysis
.\.venv\Scripts\Activate.ps1
streamlit run src/dashboard/app.py
# Metrics: Issues / Commits / Contributors / Compare / Correlations tabs
# Chat: select psf/requests, ask rows 9–10 questions
pytest
```

See also [checkpoint3-evidence.md](checkpoint3-evidence.md) for screenshots and PDF exports.
