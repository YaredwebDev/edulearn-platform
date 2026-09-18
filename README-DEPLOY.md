# EduLearn — Full Platform (deploy package)

This folder is the **entire interactive platform**: Python FastAPI backend,
SQLite database (already populated with Grades 9–11 content), SPA front end,
and the bundled study-note content.

## What's inside
- `server.py` / `db.py` / `security.py` / `admin_routes.py` — backend
- `notes_import.py` — structured-notes importer (Grade → Subject → Unit → Lesson)
- `qbank.py` — assessment builder (10 questions + flashcards per lesson)
- `build_course.py` — one-command pipeline: notes files → complete course
- `static/` — single-page app (`index.html`, `app.js`, `style.css`)
- `platform.db` — SQLite database with 14 subjects / 776 lessons / **7,760 assessment questions** / flashcards
- `importer.py`, `generator.py`, `author_chem.py`, `bootstrap.py` — original content/seed tooling
- `requirements.txt`, `Procfile`, `render.yaml`, `Dockerfile`

## Building the course from your notes files
Put the notes files in a folder (`*.html`, `*.md` or `*.txt`, named e.g.
`Chemistry_Grade9_Structured.html`) and run one command:

```
python3 build_course.py --notes /path/to/notes      # backup → import → 10 questions/lesson → report
python3 build_course.py --notes DIR --only 9,10     # only these grades
python3 build_course.py --notes DIR --dry           # preview: shows units/lessons, writes nothing
python3 build_course.py --questions-only            # rebuild the question bank only
```

* Existing student accounts, progress and certificates for a subject are **re-carried**
  across the content swap lesson-by-lesson; use `--merge` to keep the old lessons instead.
* The importer understands real `<h*>` headings, pseudo-headings (`<p><strong>Unit 2 …`)
  and flat documents whose lessons are numbered `3.2 …` (units are inferred from the number).
* Every lesson body is stored verbatim, so the reader, flashcards, unit PDFs and quizzes all work.
* Question generation is grounded in the lesson text only: definitions, quoted statements,
  deliberately-altered statements and worked calculations. Nothing is invented.
* Admin review lives at `/api/admin` → *Question bank* (approve / edit / add your own).
  Approved questions are never overwritten by a rebuild — the generator only tops up.

Environment: set `EDULEARN_DB` to point at a database on persistent storage.

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
`platform.db` ships fully populated (14 subjects, 776 lessons, 7,760 questions),
so no import is normally needed. If the DB is ever deleted/empty, rebuild it from
your notes folder with `python3 build_course.py --notes DIR`.

## Admin access
The admin panel is at `/api/admin` (in the SPA: bottom link / `#/admin`). Access
is gated by four security answers that are stored server-side in `security.py`.
