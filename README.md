# 🧠 GitSense — Autonomous AI Agent for Codebase Intelligence

[![Python](https://img.shields.io/badge/Python-3.11-3776ab?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61dafb?logo=react&logoColor=black)](https://react.dev)
[![Claude](https://img.shields.io/badge/Claude-Sonnet-cc785c?logo=anthropic&logoColor=white)](https://anthropic.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ed?logo=docker&logoColor=white)](https://docker.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)](https://postgresql.org)

> **GitSense is NOT a code assistant or chatbot.**
>
> GitSense is an autonomous AI agent that runs 24/7, silently watching a GitHub repository. It proactively detects problems, surfaces intelligence, and alerts engineers before issues become crises — without being asked.

---

## 🎬 What It Does

When a developer opens a pull request, GitSense wakes up. In seconds, it:

1. **Fetches and parses the full diff** from GitHub API
2. **Runs semantic search** across the entire codebase to detect blast radius — what else could break
3. **Queries historical intelligence** — has this file been problematic before? Who last touched it?
4. **Scans for technical debt** — long functions, magic numbers, missing docs, hardcoded values
5. **Detects merge conflicts** with all currently open PRs
6. **Invokes Claude** with a masterfully engineered multi-step prompt to reason like a Principal Engineer
7. **Posts a structured analysis** back to the PR with risk level, recommendations, and reviewer suggestions
8. **Fires Slack/email alerts** for HIGH and CRITICAL risk PRs

Then it goes back to watching.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         GitSense                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  GitHub ──webhook──► FastAPI ──► Celery Worker ──► Claude API  │
│                          │              │                       │
│                          │         ┌───┴──────────────┐        │
│                          │         │  PR Agent Pipeline│        │
│                          │         │  1. Diff Analysis │        │
│                          │         │  2. Blast Radius  │        │
│                          │         │  3. History Query │        │
│                          │         │  4. Debt Scoring  │        │
│                          │         │  5. Conflict Check│        │
│                          │         │  6. Claude Analyze│        │
│                          │         │  7. Post to GitHub│        │
│                          │         └───────────────────┘        │
│                          │              │                       │
│                       PostgreSQL    ChromaDB                   │
│                       (metadata)   (embeddings)                │
│                                                                 │
│  React Dashboard ◄──── REST API + WebSocket ◄──── Redis PubSub │
│                                                                 │
│  Celery Beat ──► Health checks (6h) ──► HealthHistory table    │
│               ──► Stale PR detection (1h)                      │
│               ──► Incremental re-index (6h)                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Quick Start

### Prerequisites
- Docker + Docker Compose
- GitHub personal access token (repo scope)
- Anthropic API key

### 1. Clone and configure

```bash
git clone https://github.com/yourusername/gitsense.git
cd gitsense
cp .env.example .env
# Edit .env with your API keys
```

### 2. Start everything

```bash
docker-compose up --build
```

That's it. One command starts:
- PostgreSQL database
- Redis (Celery broker)
- FastAPI backend (port 8000)
- Celery worker (analysis, indexing, monitoring, notifications queues)
- Celery beat scheduler
- React frontend (port 3000)

### 3. Access the dashboard

Open [http://localhost:3000](http://localhost:3000)

### 4. Add a repository

1. Go to **Settings** in the dashboard
2. Enter your GitHub repo URL
3. Click **Index Now** to build the semantic search index
4. Configure the GitHub webhook (instructions in Settings page)

### 5. Configure GitHub Webhook

In your GitHub repo → Settings → Webhooks → Add webhook:
- **Payload URL**: `http://your-server:8000/webhook/github`
- **Content type**: `application/json`
- **Secret**: Your `GITHUB_WEBHOOK_SECRET` value
- **Events**: Pull requests, Pushes, Issues

Now open a PR and watch GitSense analyze it live on the Events page.

---

## 📁 Project Structure

```
gitsense/
├── backend/
│   ├── app/
│   │   ├── agent/
│   │   │   ├── pr_agent.py          # Claude multi-step analysis engine
│   │   │   └── comment_formatter.py # Rich markdown PR comment builder
│   │   ├── api/
│   │   │   ├── webhook.py           # GitHub webhook receiver + HMAC verification
│   │   │   └── routes.py            # Full REST API (repos, PRs, stats, events)
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic settings
│   │   │   ├── celery_app.py        # Celery + beat scheduler
│   │   │   ├── logging.py           # Structured JSON logging
│   │   │   └── websocket.py         # WebSocket connection manager
│   │   ├── db/
│   │   │   ├── models.py            # SQLAlchemy models (5 tables)
│   │   │   └── session.py           # DB engine + session factory
│   │   ├── services/
│   │   │   ├── github_service.py    # GitHub API wrapper (PRs, comments, labels)
│   │   │   └── vector_store.py      # ChromaDB + sentence-transformers
│   │   ├── tasks/
│   │   │   ├── pr_analysis.py       # 7-step PR intelligence Celery task
│   │   │   ├── indexing.py          # Full + incremental repo indexing
│   │   │   ├── monitoring.py        # Health scoring + stale PR detection
│   │   │   └── notifications.py     # Slack + email notification tasks
│   │   ├── utils/
│   │   │   └── chunker.py           # Python AST + JS/TS regex code chunker
│   │   └── main.py                  # FastAPI app + WebSocket + Redis pubsub
│   ├── alembic/                     # Database migrations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Overview.jsx         # Health gauge + trend chart + PR feed
│       │   ├── PRIntelligence.jsx   # Filterable PR analysis list
│       │   ├── PRDetail.jsx         # Full PR analysis view
│       │   ├── Insights.jsx         # File heatmap + risk distribution + engineers
│       │   ├── Events.jsx           # Real-time WebSocket event stream
│       │   └── Settings.jsx         # Repo management + webhook instructions
│       ├── components/
│       │   ├── dashboard/           # HealthGauge, StatsBar, PRFeed
│       │   ├── pr/                  # PRAnalysisCard with all analysis sections
│       │   ├── events/              # EventStream with live agent steps
│       │   └── common/              # Sidebar navigation
│       └── lib/
│           ├── api.js               # Typed API client + WebSocket factory
│           └── utils.js             # Risk colors, date formatting, helpers
├── docker-compose.yml               # Full stack, one-command startup
├── .env.example                     # All environment variables documented
└── README.md
```

---

## 🔌 API Reference

Full interactive docs available at `http://localhost:8000/docs`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/webhook/github` | GitHub webhook receiver (HMAC verified) |
| `GET` | `/api/repositories` | List monitored repos |
| `POST` | `/api/repositories` | Add repo to monitor |
| `POST` | `/api/repositories/{id}/index` | Trigger indexing |
| `GET` | `/api/repositories/{id}/status` | Indexing progress |
| `GET` | `/api/prs` | List analyzed PRs (filter by risk, author, repo) |
| `GET` | `/api/prs/{id}` | Full PR analysis detail |
| `GET` | `/api/health-history/{repo_id}` | Health score over time |
| `GET` | `/api/events` | Recent webhook events |
| `GET` | `/api/stats` | Dashboard statistics |
| `WS` | `/ws/events` | Live agent event stream |

---

## 🛡️ Security

- **Webhook signature verification**: Every incoming GitHub webhook is verified via HMAC-SHA256
- **No secrets in code**: All credentials via environment variables
- **SQL injection protection**: All DB operations via SQLAlchemy ORM with parameterized queries
- **Rate limit handling**: GitHub API errors caught and retried with exponential backoff

---

## 🎯 Skills Demonstrated

This project was built to showcase production-level engineering across multiple domains:

### Agentic AI Architecture
- Multi-step reasoning pipeline with Claude as the analysis engine
- Carefully engineered system prompt instructing Claude to reason as a Principal Engineer
- Structured JSON output enforcement with graceful fallback parsing
- Context assembly from 5 different data sources before Claude invocation

### Event-Driven Systems
- GitHub Webhooks → FastAPI → Celery task queue
- Redis pub/sub for broadcasting agent steps from workers to WebSocket clients
- Celery Beat for scheduled background jobs (health checks, stale detection, re-indexing)
- Duplicate event detection via delivery ID idempotency

### Vector Search & Embeddings
- sentence-transformers (all-MiniLM-L6-v2) for code chunk embedding
- ChromaDB for persistent vector storage with cosine similarity search
- Python AST-based chunking for semantic function/class boundaries
- Incremental re-indexing — only changed files since last index

### GitHub API Depth
- PR diffs, file change history, commit authors, issue linking
- Automated PR comment posting with rich markdown formatting
- Automated label creation and application
- Open PR conflict detection

### Systems Design
- Separation of concerns: API → Task Queue → Worker → Notification
- Health score calculation with multi-factor penalty model
- Blast radius detection via semantic similarity across entire codebase
- Five distinct Celery queues for workload isolation

### Frontend Engineering
- React 18 with React Router for SPA navigation
- Real-time WebSocket feed with auto-reconnect
- Recharts for health score trend visualization
- Animated SVG health gauge with CSS transitions
- Dark mode design with Tailwind CSS custom theme

### DevOps
- Six-service Docker Compose with health checks and dependency ordering
- Alembic database migrations
- Structured JSON logging throughout
- Environment-driven configuration with Pydantic Settings

---

## 📊 Dashboard Screenshots

*[Screenshots would be placed here in a deployed project — the dashboard features a dark mode health gauge, real-time event stream showing agent processing steps, filterable PR intelligence feed with risk badges, and file hotspot heatmaps.]*

---

## 📝 License

MIT
