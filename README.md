# TaskHub API — Task Management System

A production-ready multi-tenant Task Management REST API built with **FastAPI 0.111+**, **SQLAlchemy 2.x Async**, **Alembic**, **Pydantic v2**, **PostgreSQL 18**, **Redis 7**, and **Docker**.

---

## 1. Architecture (Layered Architecture)

```text
Client Request
      │
      ▼
┌─────────────────────┐
│  Middleware & CORS  │  app/core/middleware.py (X-Request-ID, X-Process-Time, Logging)
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│     API Router      │  app/api/v1/ (Routing, OpenAPI docs, Annotated DI)
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│      Service        │  app/services/ (Business logic, RBAC, Cache, BackgroundTasks)
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│     Repository      │  app/repositories/ (Generic BaseRepository[T], Async SQLAlchemy)
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│   PostgreSQL + Redis│  PostgreSQL 18 (Persistence) + Redis 7 (Query Cache)
└─────────────────────┘
```

---

## 2. Core Features

- **Authentication & Security**: Bcrypt password hashing (enforcing 72-byte UTF-8 limit), JWT Access/Refresh tokens (`sub`, `type`, `jti`, `iat`, `exp`), atomic Refresh Token Rotation with reuse detection & full-session revocation.
- **User Management**: Profile `GET/PATCH /users/me`, password change (revokes all refresh tokens), Admin CRUD with self-deletion and last-active-admin protection.
- **Workspace & Project RBAC**: Fine-grained object-level authorization (`ADMIN`, `OWNER`, `EDITOR`, `VIEWER`) across Workspaces, Projects (including `ARCHIVED` lifecycle), and Tasks.
- **Task Workflows, Labels & Comments**: Project-scoped labels, `task_labels` many-to-many assignment (same-project enforcement), task comments (author/owner deletion), workspace-member assignee validation, status transitions, and multi-criteria filtering + pagination.
- **Redis Caching & Background Tasks**: Caches `GET /api/v1/projects/{id}/tasks` per filter/page with fail-open degradation and `SCAN`-based invalidation on task/label mutations; dispatches asynchronous email notifications via `BackgroundTasks` on task assignment.
- **OpenAPI Documentation**: Interactive Swagger UI (`/docs`) and ReDoc (`/redoc`) with HTTPBearer authentication scheme and documented `400/401/403/404/409/422` error envelopes.

---

## 3. Environment Variables

Copy `.env.example` to `.env` before running locally:

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
| :--- | :---: | :--- | :--- |
| `SECRET_KEY` | Yes | *(min 32 chars)* | JWT cryptographic signing key (fail-fast validation) |
| `DATABASE_URL` | Yes | `postgresql+asyncpg://postgres:postgres@localhost:5433/taskhub_dev` | Async PostgreSQL connection string |
| `DB_ECHO` | No | `false` | Enable SQLAlchemy SQL query logging |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection URL for caching |
| `CACHE_TTL_SECONDS` | No | `60` | Default cache expiration time in seconds |
| `LOG_LEVEL` | No | `INFO` | Application logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `ALLOWED_ORIGINS` | No | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated or JSON array of CORS origins |

---

## 4. Running with Docker Compose (Full Stack: App + PostgreSQL + Redis)

```bash
cd taskhub
docker compose up --build -d
```

This builds the multi-stage non-root `Dockerfile`, starts **PostgreSQL 18** (`db`) and **Redis 7** (`redis`), waits for both to become healthy, automatically runs `alembic upgrade head`, and starts the **TaskHub API** at:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: `GET http://localhost:8000/api/v1/health`

To stop and remove containers:

```bash
docker compose down
```

---

## 5. Local Development Setup

Requirements: **Python 3.11+**

```bash
cd taskhub
pip install -e ".[dev]"

# Start PostgreSQL & Redis containers
docker compose up -d db redis

# Apply database migrations
alembic upgrade head

# Run local dev server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 6. API Endpoints Overview

| Group | Method & Path | Description |
| :--- | :--- | :--- |
| **Health** | `GET /api/v1/health` | Service health check |
| **Auth** | `POST /api/v1/auth/register`, `/login`, `/refresh`, `/logout` | Registration, JWT tokens, atomic rotation, logout |
| **Users** | `GET/PATCH /api/v1/users/me`, `POST /users/me/change-password` | Profile & password management |
| **Users (Admin)** | `PATCH/DELETE /api/v1/users/{user_id}` | Admin user management |
| **Workspaces** | `POST/GET /api/v1/workspaces`, `GET/PATCH/DELETE /workspaces/{id}` | Workspace CRUD (Owner-only update/delete) |
| **Members** | `POST/GET /api/v1/workspaces/{id}/members`, `DELETE .../members/{user_id}` | Invite/list/remove workspace members |
| **Projects** | `POST/GET /api/v1/workspaces/{id}/projects`, `GET/PATCH/DELETE /projects/{id}` | Project CRUD & archiving |
| **Tasks** | `POST/GET /api/v1/projects/{id}/tasks`, `GET/PATCH/DELETE /api/v1/tasks/{id}` | Task CRUD, Redis-cached listing, filtering & notifications |
| **Labels** | `POST/GET /api/v1/projects/{id}/labels`, `DELETE /api/v1/labels/{id}` | Project-scoped labels CRUD |
| **Task Labels** | `POST/DELETE /api/v1/tasks/{id}/labels/{label_id}` | Attach/remove labels on tasks |
| **Comments** | `POST/GET /api/v1/tasks/{id}/comments`, `DELETE /api/v1/comments/{id}` | Task comments (author/owner deletion) |

---

## 7. Quality Checks (Testing, Linting & Typing)

```bash
# Run full automated test suite
pytest tests -v

# Lint and formatting check (Ruff)
ruff check .
ruff format --check .

# Strict static type checking (Mypy)
mypy app tests
```
