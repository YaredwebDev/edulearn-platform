# EduLearn — Full Platform (deploy package)

This folder is the **entire interactive platform**: Python FastAPI backend,
SQLite database (already populated with Grades 9–11 content), SPA front end,
and the bundled study-note content.

## What's inside
- `server.py` / `db.py` / `security.py` / `admin_routes.py` / `importer.py` / `generator.py` — backend
- `static/` — single-page app (`index.html`, `app.js`, `style.css`)
- `platform.db` — SQLite database with 14 subjects / 776 lessons / flashcards / assessment bank
- `content/` — the original markdown study notes (used to rebuild the DB if needed)
- `requirements.txt`, `Procfile`, `render.yaml`, `Dockerfile`, `bootstrap.py`

## Run locally
```
pip install -r requirements.txt
python bootstrap.py        # optional: only needed if platform.db is missing/empty
uvicorn server:app --host 0.0.0.0 --port 8000
```
Open http://localhost:8000 — the SPA landing, registration, lessons, quizzes,
final exams, certificates and `/api/admin` all live here.

## Deploy options (Python-capable hosts)
### Render (easiest)
1. Push this folder to a Git repo (or use Render "Deploy from file" / blueprints).
2. New → Web Service → point at the repo.
3. Render auto-detects `render.yaml` (plan free, Python 3.12).
4. Runtime: `uvicorn server:app --host 0.0.0.0 --port $PORT`

### Railway / Fly.io
- Railway: use the `Procfile` (`web: uvicorn server:app ...`).
- Fly: `fly launch` then `fly deploy` (see `Dockerfile`).

### Docker / your server
- Build: `docker build -t edulearn .`
- Run:  `docker run -p 8000:8000 edulearn`
- Or on a VPS: install Python 3.12, run `gunicorn -w 2 -k uvicorn.workers.UvicornWorker server:app`
  behind nginx/Caddy.

## IMPORTANT — data persistence
`platform.db` is a local file. On hosts with **ephemeral storage** (Render free
tier, some containers) the file is reset on redeploys. To keep student accounts
and progress across restarts you must use **persistent storage**:
- Render: attach a Disk and put the DB there (set an env var such as
  `EDULEARN_DB=/var/data/platform.db`). The code currently uses the local
  `platform.db`, so point the process at the mounted volume, or migrate to a
  hosted SQL database.
- For a serious multi-user launch, replace the SQLite file with a hosted DB
  (PostgreSQL via SQLAlchemy, or a managed SQLite/volume) and add HTTPS,
  backups and rate limiting.

## First-run data
`platform.db` ships fully populated, so no import is normally needed. If the DB
is ever deleted/empty, `python bootstrap.py` rebuilds every subject from
`content/` and re-seeds the Grade 11 Chemistry assessment bank.

## Admin access
The admin panel is at `/api/admin` (in the SPA: bottom link / `#/admin`). Access
is gated by four security answers that are stored server-side in `security.py`.
