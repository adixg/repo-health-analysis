# RepoSense

RepoSense is a GitHub Repository Intelligence Agent that combines deterministic repository analytics with a locally running LLM. The system is intended to help users understand repository health by collecting data from public GitHub repositories, calculating project-health metrics, indexing repository text for retrieval, and exposing repository information through MCP tools.

The project is being developed as an individual project for Georgia Tech CS 4365/6365: Introduction to Enterprise Computing.

## Project Motivation

Software teams often need to assess the health of a GitHub repository by examining issues, pull requests, commits, contributors, releases, and documentation. GitHub provides this information across many separate pages, which makes repository evaluation time-consuming.

Existing repository dashboards mainly provide fixed visualizations, while general-purpose LLM assistants may produce unsupported answers if they are not connected to exact repository data. RepoSense addresses this by separating deterministic analytics from natural-language interpretation.

The system will calculate metrics using repository data and allow a local LLM to explain those results using verifiable evidence.

## Main Objectives

RepoSense will:

* collect structured data from public GitHub repositories,
* store repository data locally,
* calculate repository-health metrics,
* compare multiple repositories,
* retrieve relevant documentation, issues, and pull requests,
* expose repository operations through MCP servers,
* use a locally running LLM to answer evidence-grounded questions,
* generate an exportable repository-health report,
* explore correlations between repository-health metrics and popularity measures such as stars and forks.

The correlation analysis will be exploratory and will not be presented as evidence of causation.

## Planned System Architecture

```text
GitHub REST API
        |
        v
Repository Ingestion Service
        |
        v
PostgreSQL Database
        |
        +----------------------+
        |                      |
        v                      v
Repository Analytics      Semantic Retrieval
Engine                    and Embeddings
        |                      |
        +----------+-----------+
                   |
                   v
               MCP Servers
                   |
                   v
          Local LLM through Ollama
                   |
                   v
        Dashboard and Report Export
```

## Planned Components

### 1. Repository Data Ingestion

The ingestion pipeline will collect:

* repository metadata,
* issues,
* issue comments,
* pull requests,
* pull-request comments,
* commits,
* contributors,
* releases,
* README files,
* documentation files.

The pipeline will support pagination, local caching, incremental synchronization, retry logic, and rate-limit handling.

### 2. Repository Analytics Engine

The analytics engine will calculate metrics such as:

* open and closed issue counts,
* issue closure rate,
* median issue resolution time,
* stale issue percentage,
* pull-request merge rate,
* median pull-request review time,
* monthly commit activity,
* release frequency,
* active contributor count,
* contributor concentration,
* label and issue-category distributions.

The system may also generate an explainable repository-health summary. The underlying metrics and score weights will remain visible to the user.

### 3. Semantic Retrieval

Repository text will be chunked and indexed for retrieval. Sources may include:

* README files,
* documentation,
* issue descriptions,
* issue comments,
* pull-request descriptions,
* release notes.

This will allow the local LLM to retrieve supporting evidence before answering repository questions.

### 4. MCP Tools

Planned MCP tools include:

```text
get_repository_summary
get_open_issues
get_recent_commits
get_pull_requests
get_contributor_activity
calculate_health_metrics
find_stale_issues
detect_activity_decline
compare_repositories
search_documentation
find_related_issues
retrieve_supporting_evidence
```

The LLM will use MCP tools to retrieve exact data rather than estimate repository metrics itself.

### 5. Local LLM

The project will use a locally running model through Ollama. The LLM will be responsible for:

* selecting appropriate MCP tools,
* interpreting computed metrics,
* summarizing repository evidence,
* comparing repositories,
* generating readable reports.

The LLM will not be responsible for directly calculating repository statistics.

### 6. Dashboard

The planned dashboard will include:

* repository overview,
* issue and pull-request analytics,
* commit and release activity,
* contributor activity,
* repository comparison,
* evidence-grounded chat,
* MCP tool-call trace,
* exportable health report.

## Planned Technical Stack

* Python
* GitHub REST API
* PostgreSQL
* pandas
* SQLAlchemy
* FastAPI
* MCP Python SDK
* Ollama
* Qwen, Llama, or another local model
* pgvector or ChromaDB
* Streamlit
* SciPy or statsmodels
* matplotlib or Plotly
* Docker Compose
* pytest

## Cross-Repository Analysis

RepoSense will be tested across multiple public repositories.

The project will explore whether repository-health metrics are associated with popularity measures such as:

* stars,
* forks,
* watchers.

Possible relationships include:

* issue resolution time versus stars,
* pull-request merge rate versus stars,
* release frequency versus forks,
* contributor concentration versus popularity,
* commit activity versus repository growth.

Repositories differ in age, size, programming language, domain, and governance structure. These factors may make direct comparisons misleading. The analysis will therefore use normalized metrics where possible and clearly report limitations.

## Limitations and Risk Mitigation

### GitHub API Rate Limits

Collecting paginated issues, comments, pull requests, commits, and contributor histories across several repositories may require many API requests.

Planned mitigation:

* authenticated API requests,
* local response caching,
* incremental synchronization,
* conditional requests where possible,
* retry logic with exponential backoff,
* request logging,
* partial-failure recovery.

### Repository Differences

Repositories vary greatly in size, age, domain, activity level, and development style.

Planned mitigation:

* normalize time-based metrics,
* compare similar repositories where possible,
* report sample sizes,
* separate raw and normalized results,
* avoid causal conclusions.

### Repository Health Definition

Repository health cannot be represented perfectly by one score.

Planned mitigation:

* expose individual metrics,
* show score weights,
* allow users to inspect supporting evidence,
* avoid relying only on a single health score.

### Local LLM Performance

Local models may have lower response quality or higher latency than hosted models.

Planned mitigation:

* precompute repository metrics,
* retrieve supporting evidence before generation,
* use the LLM mainly for interpretation,
* record response latency,
* evaluate factual accuracy and unsupported claims.

## Evaluation Plan

The system will be evaluated using manually verified repository questions.

Planned metrics include:

* ingestion time,
* number of records collected,
* API request count,
* database query latency,
* MCP tool-selection accuracy,
* factual answer accuracy,
* retrieval relevance,
* citation and evidence correctness,
* unsupported-claim rate,
* local LLM response latency.

The final evaluation will use approximately 20 to 30 repository questions.

Example questions:

```text
How many issues have been open for more than 90 days?
Who are the most active contributors?
Has commit activity declined during the last six months?
What are the most common issue categories?
Which repository appears healthier and why?
What evidence supports the repository-health assessment?
```

## Project Milestones

### Checkpoint 1: Project Definition and Planning

* finalize project scope,
* define architecture,
* select technical stack,
* identify metrics,
* document limitations,
* create the public GitHub repository,
* define milestones and evaluation strategy.

### Checkpoint 2: Ingestion, Database, and Analytics

* test authenticated GitHub API access,
* ingest a sample repository,
* implement PostgreSQL schema,
* support multiple repositories,
* add caching and incremental updates,
* calculate initial repository metrics,
* build initial dashboard views,
* add unit tests.

**Progress:** in progress — repository and issue ingestion, PostgreSQL storage, initial issue metrics, Streamlit dashboard, FastAPI endpoints, and unit tests are implemented locally. Pull requests, commits, contributors, and release ingestion remain open.

### Checkpoint 3: MCP, Local LLM, and Final Evaluation

* implement MCP tools,
* integrate Ollama,
* add semantic retrieval,
* add repository comparison,
* perform exploratory correlation analysis,
* evaluate verified questions,
* add report export,
* containerize the system,
* prepare the final demonstration and report.

## Current Status

The project has moved from planning into **Checkpoint 2 implementation**. The core ingestion → storage → metrics pipeline is working on real public repositories.

### Completed

**Checkpoint 1**

* project idea selected,
* project scope defined,
* high-level architecture created,
* planned metrics identified,
* technical stack selected,
* risks and limitations documented,
* public GitHub repository created.

**Checkpoint 2 (partial)**

* authenticated GitHub REST API access (`GitHubClient`, token via `.env`),
* repository metadata ingestion for multiple repos,
* issue ingestion with pagination, local response caching, and incremental sync,
* PostgreSQL schema (`repositories`, `issues`) via SQLAlchemy,
* initial issue-health metrics: open/closed counts, closure rate, stale issues (90+ days), median resolution time,
* Streamlit dashboard with repository overview and issue metrics,
* FastAPI service with `/health`, `/repositories`, and `/metrics/issues`,
* setup script (`scripts/verify_setup.py`) and unit tests (`pytest`, 7 tests),
* Phase 1 evaluation repos configured: `octocat/Hello-World`, `fastai/fastai`, `explosion/spaCy`, `psf/requests`.

### In progress / next

* pull-request ingestion and PR merge rate,
* commit and contributor ingestion,
* monthly commit activity charts,
* release frequency metrics,
* richer dashboard views and repository comparison,
* additional tests and checkpoint evidence documentation.

### Planned for Checkpoint 3

* MCP tool servers,
* Ollama integration and semantic retrieval,
* cross-repository correlation analysis,
* report export and full system containerization.

## Getting Started

### Prerequisites

* Python 3.10+
* PostgreSQL (local install or Docker Compose)
* GitHub personal access token with `public_repo` scope

### Setup

```bash
git clone https://github.com/adixg/repo-health-analysis.git
cd repo-health-analysis
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
```

Add your credentials to `.env`:

```env
GITHUB_TOKEN=your_token_here
POSTGRES_USER=reposense
POSTGRES_PASSWORD=reposense
POSTGRES_DB=reposense
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
SAMPLE_REPOS=octocat/Hello-World,fastai/fastai,explosion/spaCy,psf/requests
```

Start PostgreSQL (if using Docker):

```bash
docker compose up -d
```

Run setup and ingestion:

```bash
python scripts/verify_setup.py
pytest
streamlit run src/dashboard/app.py
```

Optional API:

```bash
uvicorn src.api.main:app --reload
```

### Reproducible evidence

After a successful run of `verify_setup.py`, you should see:

* authenticated GitHub user printed to the console,
* PostgreSQL tables created,
* multiple repositories ingested,
* issue counts synced per repository.

Example SQL check:

```sql
SELECT r.full_name, COUNT(i.id) AS issue_count
FROM repositories r
LEFT JOIN issues i ON i.repository_id = r.id
GROUP BY r.full_name
ORDER BY issue_count DESC;
```

## Repository Structure

The current repository structure is:

```text
repo-health-analysis/
├── README.md
├── requirements.txt
├── pyproject.toml
├── docker-compose.yml
├── .env.example
├── scripts/
│   ├── verify_setup.py
│   └── run_dashboard.py
├── src/
│   ├── config.py
│   ├── ingestion/          # GitHub client, repo + issue ingest
│   ├── database/           # SQLAlchemy models and session
│   ├── analytics/          # Issue health metrics
│   ├── retrieval/          # placeholder (Checkpoint 3)
│   ├── mcp_servers/        # placeholder (Checkpoint 3)
│   ├── api/                # FastAPI service
│   └── dashboard/          # Streamlit app
├── tests/
├── data/                   # local API cache (gitignored contents)
├── docs/
└── outputs/
```

This structure may change as the project develops.

## Course Information

* Course: CS 4365/6365 — Introduction to Enterprise Computing
* Institution: Georgia Institute of Technology
* Term: Summer 2026
* Project Type: Individual
* Student: Aditya Ghosh

## License

This repository is currently intended for academic and educational use.
