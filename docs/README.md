# EduLearn — static edition (phone-friendly)

This folder is a complete, server-free copy of the course, generated from the database by
`make_static_site.py`:

- `index.html` — landing page: every grade and subject, with progress
- `s/<id>.html` — a subject: its units and all lessons, with completion ticks
- `l/<id>.html` — a lesson: **Learn / Flashcards / Assessment** tabs. The assessment is
  scored in the page — 80% passes — with the explanation for every question, and
  prev/next navigation between lessons
- `preview.html` — the same content as one single self-contained file (styling inlined)
- `assets/` — the real platform stylesheet plus the small script that runs tabs,
  the quiz and progress

Progress and best scores are stored in the browser (`localStorage`), so no login is needed.
The full platform (accounts, progress sync, certificates, teacher tools) runs from
`server.py`; this folder is the browsable mirror.

## Turning this into a public URL (GitHub Pages)

Repo → **Settings → Pages** → *Source*: **Deploy from a branch** →
*Branch*: `arena/01a0b4b5-edulearn-platform`, *Folder*: **/docs** → **Save**.

A minute later the course is live at `https://yaredwebdev.github.io/edulearn-platform/`
and opens on any phone.
