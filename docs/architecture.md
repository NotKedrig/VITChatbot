# VITian Chatbot — Local POC Architecture

## Overview

VITian Chatbot is a **fully local** multi-agent, retrieval-grounded conversational
assistant for academic, placement, and career guidance at VIT.  The system is built
as a proof-of-concept (POC) whose primary goals are:

1. **Research validity** — produce real, non-fabricated statistical evidence for five
   architectural claims (Experiments 1–5 defined in the master plan).
2. **Working application** — a locally runnable chatbot built from the exact components
   that were evaluated, not a separate simplified demo.

No AWS services are implemented or benchmarked in this POC.
See [`future_aws_deployment.md`](./future_aws_deployment.md) for the production mapping.

---

## System Diagram

```
                 ┌─────────────────────┐
                 │  React + Vite UI     │   (Phase 9)
                 └──────────┬──────────┘
                            │  HTTP/REST
                            ▼
                 ┌─────────────────────┐
                 │      FastAPI         │   (Phases 0–9)
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────────────┐
                 │  LangGraph Supervisor Agent  │  LLM-based intent classification
                 │  (+ rule-based baseline)     │  (replaces AWS Lex V2 locally)
                 └────┬──────────┬──────┬──────┘
                      │          │      │        │
                      ▼          ▼      ▼        ▼
               Company       Planner  Progress  Notification
               Research       Agent    Agent      Agent
                Agent            │        │          │
                  │              └───┬────┘          │
                  ▼                  ▼               ▼
           ChromaDB +           PostgreSQL      Local Scheduler
           PostgreSQL           (Student        (APScheduler)
         (KB + citations)        State)
```

---

## Technology Stack

| Layer | Technology | Notes |
|---|---|---|
| Web framework | **FastAPI** | REST API, async |
| Orchestration | **LangGraph** | Typed state graph, Supervisor pattern |
| Vector store | **ChromaDB** (local dir) | Persistent local directory — no separate server |
| Relational DB | **PostgreSQL** | Student state, chunk metadata, run metadata |
| Embeddings | **sentence-transformers** | Local, no embedding API cost; provider-abstracted |
| LLM | Provider-abstracted (`app/llm/provider.py`) | Default: one hosted model at low/fixed temperature |
| Scheduling | **APScheduler** | In-process; replaces EventBridge + SNS locally |
| Notifications | Log line + optional local SMTP | Not a production notification service |
| Containerisation | **Docker Compose** | Postgres + app; Chroma is a local directory mount |
| Frontend | **React + Vite + TypeScript** | Phase 9 only |

---

## Key Design Decisions

### 1. Local Chroma (directory mode) instead of a Chroma server

A separate Chroma container adds network overhead and complexity without benefit
for a single-replica POC.  The `chroma_data/` directory is mounted into the app
container and Chroma reads/writes it directly.

### 2. Provider-abstracted LLM and embeddings

`app/llm/provider.py` exposes a single `.complete(prompt, **kwargs)` interface.
`app/llm/embeddings.py` mirrors this pattern for embeddings.  Swapping providers
requires only a config change, never a code change in agent or RAG modules.

### 3. Model/version recording

Every LLM call logs the fully-qualified model name, temperature, and a UTC
timestamp via `app/logging_config.log_llm_call`.  The same fields appear in
every results CSV row, enabling reproducibility tracing as required by Section
10.2 of the master plan.

### 4. SQLite response cache (`app/llm/cache.py`)

Responses are cached by `(prompt_hash, model, temperature)` in a local SQLite
file.  Re-running an experiment during debugging does not re-incur API cost.
Cache can be bypassed with `use_cache=False`.

### 5. Paired experimental design

All five experiments use paired designs (same query/session/student under both
systems) to remove between-unit variance, enabling McNemar's test and Wilcoxon
signed-rank as appropriate.  See master plan Sections 5–6 for full methodology.

---

## Repository Structure

```
vitian-chatbot/
├── docker-compose.yml          # Postgres + app
├── Dockerfile
├── .env.example                # All env vars documented
├── requirements.txt            # Python deps (no boto3/AWS SDKs)
├── pyproject.toml              # pytest config
├── app/
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # pydantic-settings config
│   ├── logging_config.py       # Structured logging + log_llm_call helper
│   ├── llm/
│   │   ├── cache.py            # (prompt_hash, model, temperature) → SQLite cache
│   │   ├── provider.py         # LLM abstraction (Phase 2+)
│   │   └── embeddings.py       # Embedding abstraction (Phase 1+)
│   ├── agents/                 # Supervisor + specialised agents (Phases 3–8)
│   ├── rag/                    # Ingestion, chunking, retrieval, citations (Phase 1+)
│   ├── db/state/               # SQLAlchemy ORM models (Phase 1+)
│   └── scheduler/              # APScheduler-based notifier (Phase 8+)
├── prompts/                    # Versioned prompt files (Phase 2+)
├── evaluation/
│   ├── datasets/               # Versioned, frozen evaluation datasets
│   ├── rubrics/                # Written, inspectable scoring rubrics
│   └── metrics/                # Deterministic scoring code
├── experiments/                # Experiment runner scripts
├── results/                    # Raw per-observation CSVs (never hand-edited)
├── analysis/charts/            # Statistical outputs and charts
├── tests/                      # pytest test suite
└── docs/                       # This file + future_aws_deployment.md
```

---

## Phase Roadmap

| Phase | Description | Key deliverable |
|---|---|---|
| 0 | Repo & infra scaffold | FastAPI /health, Postgres, logging, cache |
| 1 | Knowledge base & RAG | ChromaDB ingestion, both chunking strategies |
| 2 | Experiment 1 | RAG vs Vanilla LLM — factual accuracy |
| 3 | Supervisor & routing | LangGraph Supervisor + rule-based baseline |
| 4 | Company Research + Planner agents | Full LangGraph nodes |
| 5 | Experiment 3 | Multi-agent vs Monolithic LLM |
| 6 | Experiment 4 | Fixed-size vs semantic chunking |
| 7 | Progress Agent + Adaptive Planner | Experiment 5 (paired sim design) |
| 8 | Notifications | APScheduler-based local reminders |
| 9 | Frontend + dashboard | React + Vite UI, research results display |

---

## Running Locally

### Without Docker

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy and configure environment
cp .env.example .env
# Edit .env — at minimum set OPENAI_API_KEY (or your provider's key)

# 4. Start Postgres separately (or use Docker Compose for just postgres)
docker-compose up -d postgres

# 5. Run the app
uvicorn app.main:app --reload

# 6. Run tests
pytest
```

### With Docker Compose

```bash
cp .env.example .env
# Edit .env

docker-compose up --build
```

Health check: `curl http://localhost:8000/health`
