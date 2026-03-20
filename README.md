# TaskFlow API

Production-ready multi-user task management SaaS backend.

**Stack:** FastAPI · PostgreSQL · SQLAlchemy ORM · Alembic · JWT (access + refresh) · bcrypt · Pydantic v2 · Uvicorn

---

## Folder Structure

```
taskflow_api/
├── app/
│   ├── core/
│   │   ├── config.py          # pydantic-settings — all env vars
│   │   ├── security.py        # bcrypt + JWT helpers
│   │   ├── dependencies.py    # FastAPI auth dependencies
│   │   ├── middleware.py      # request logging + timing
│   │   ├── exceptions.py      # centralised error handlers
│   │   └── logging.py         # structured logging setup
│   ├── db/
│   │   ├── base.py            # declarative Base + model imports
│   │   └── session.py         # engine, SessionLocal, get_db
│   ├── models/
│   │   ├── user.py            # User ORM model
│   │   └── task.py            # Task ORM model
│   ├── schemas/
│   │   ├── user.py            # Pydantic request/response schemas
│   │   └── task.py            # Pydantic request/response schemas
│   ├── services/
│   │   ├── auth_service.py    # register, login, refresh, upgrade
│   │   ├── task_service.py    # CRUD for tasks
│   │   └── user_service.py    # admin user management
│   ├── routers/
│   │   ├── auth.py            # /api/v1/auth/*
│   │   ├── tasks.py           # /api/v1/tasks/*
│   │   └── users.py           # /api/v1/users/*  (admin)
│   └── main.py                # app factory, middleware, routers
├── alembic/
│   ├── versions/
│   │   └── 001_initial.py     # initial DB migration
│   ├── env.py
│   └── script.py.mako
├── scripts/
│   └── seed_admin.py          # create first admin user
├── alembic.ini
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## 1. Local Setup (without Docker)

### Prerequisites
- Python 3.12+
- PostgreSQL 14+

### Step 1 — Clone and create virtualenv
```bash
git clone <your-repo>
cd taskflow_api

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2 — Configure environment
```bash
cp .env.example .env
```

Edit `.env`:
```env
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/taskflow_db
SECRET_KEY=<output of: openssl rand -hex 32>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
APP_ENV=development
DEBUG=true
ALLOWED_ORIGINS=http://localhost:3000
```

### Step 3 — Create the database
```bash
psql -U postgres -c "CREATE DATABASE taskflow_db;"
```

### Step 4 — Run database migrations
```bash
alembic upgrade head
```

### Step 5 — Seed the admin user
```bash
python scripts/seed_admin.py
# Default admin: admin@taskflow.dev / Admin1234
```

### Step 6 — Start the server
```bash
uvicorn app.main:app --reload --port 8000
```

API is live at **http://localhost:8000**
Interactive docs: **http://localhost:8000/docs**

---

## 2. Docker Setup (recommended)

```bash
cp .env.example .env
# Edit .env — set SECRET_KEY and DATABASE_URL pointing to the db service:
# DATABASE_URL=postgresql://postgres:postgres@db:5432/taskflow_db

docker compose up --build
```

Migrations run automatically on startup.
Seed the admin manually after first start:
```bash
docker compose exec api python scripts/seed_admin.py
```

---

## 3. API Endpoints Summary

| Method | Path | Auth | Role |
|--------|------|------|------|
| POST | /api/v1/auth/register | — | — |
| POST | /api/v1/auth/login | — | — |
| POST | /api/v1/auth/refresh | — | — |
| GET | /api/v1/auth/me | ✅ | any |
| POST | /api/v1/auth/upgrade | ✅ | any |
| POST | /api/v1/tasks | ✅ | any |
| GET | /api/v1/tasks | ✅ | any |
| GET | /api/v1/tasks/{id} | ✅ | any |
| PATCH | /api/v1/tasks/{id} | ✅ | any |
| DELETE | /api/v1/tasks/{id} | ✅ | any |
| GET | /api/v1/users | ✅ | admin |
| GET | /api/v1/users/{id} | ✅ | admin |
| DELETE | /api/v1/users/{id} | ✅ | admin |
| GET | /health | — | — |

---

## 4. Testing with curl

Replace `ACCESS_TOKEN` and `REFRESH_TOKEN` with values from the login response.

### Register
```bash
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","full_name":"Alice Smith","password":"Secret12"}' \
  | python -m json.tool
```

### Login
```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"Secret12"}' \
  | python -m json.tool
```

Save the tokens:
```bash
# Bash convenience
export ACCESS_TOKEN="<access_token from login>"
export REFRESH_TOKEN="<refresh_token from login>"
```

### Get current user
```bash
curl -s http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python -m json.tool
```

### Refresh access token
```bash
curl -s -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$REFRESH_TOKEN\"}" \
  | python -m json.tool
```

### Upgrade to Premium
```bash
curl -s -X POST http://localhost:8000/api/v1/auth/upgrade \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python -m json.tool
```

### Create a task
```bash
curl -s -X POST http://localhost:8000/api/v1/tasks \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Launch NEXORION MVP",
    "description": "Complete backend and deploy to production",
    "status": "in_progress",
    "due_date": "2026-06-01T00:00:00Z"
  }' | python -m json.tool
```

### List tasks (paginated)
```bash
curl -s "http://localhost:8000/api/v1/tasks?page=1&page_size=10" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python -m json.tool
```

### Filter tasks by status
```bash
curl -s "http://localhost:8000/api/v1/tasks?status=in_progress" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python -m json.tool
```

### Get a task by ID
```bash
curl -s http://localhost:8000/api/v1/tasks/1 \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python -m json.tool
```

### Update a task (partial)
```bash
curl -s -X PATCH http://localhost:8000/api/v1/tasks/1 \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "done"}' \
  | python -m json.tool
```

### Delete a task
```bash
curl -s -X DELETE http://localhost:8000/api/v1/tasks/1 \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -o /dev/null -w "%{http_code}\n"
# Expected: 204
```

### Admin — list all users
```bash
# Login as admin first
export ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@taskflow.dev","password":"Admin1234"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  | python -m json.tool
```

### Admin — delete a user
```bash
curl -s -X DELETE http://localhost:8000/api/v1/users/2 \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -o /dev/null -w "%{http_code}\n"
# Expected: 204
```

### Health check
```bash
curl -s http://localhost:8000/health | python -m json.tool
```

---

## 5. Alembic Migration Commands

```bash
# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Rollback all the way to empty DB
alembic downgrade base

# Generate a new migration after changing models
alembic revision --autogenerate -m "add_column_xyz"

# Show current revision
alembic current

# Show full migration history
alembic history --verbose
```

---

## 6. Postman Setup

1. Create a new collection: **TaskFlow API**
2. Set base URL variable: `{{base_url}}` = `http://localhost:8000/api/v1`
3. After login, save the access token to a collection variable `{{access_token}}`
4. On all protected requests, set the Authorization header to:
   `Bearer {{access_token}}`
5. Use the "Tests" tab on the login request to auto-save tokens:
```javascript
const res = pm.response.json();
pm.collectionVariables.set("access_token", res.access_token);
pm.collectionVariables.set("refresh_token", res.refresh_token);
```

---

## 7. Production Checklist

- [ ] Set `SECRET_KEY` to a long random string (`openssl rand -hex 32`)
- [ ] Set `APP_ENV=production` and `DEBUG=false`
- [ ] Set `ALLOWED_ORIGINS` to your exact frontend domain(s)
- [ ] Use a managed PostgreSQL instance (AWS RDS, Supabase, etc.)
- [ ] Run behind a reverse proxy (Nginx / Caddy) with HTTPS
- [ ] Set `--workers` in Uvicorn to `2 × CPU cores + 1`
- [ ] Ship logs to an aggregator (Datadog, CloudWatch, Grafana Loki)
- [ ] Add rate limiting (slowapi or a gateway like Kong)
- [ ] Replace the payment simulation with real Stripe/M-Pesa webhook handlers
