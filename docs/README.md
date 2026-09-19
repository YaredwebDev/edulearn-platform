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

## Textbook alignment (updated 2026-09-20)

Lessons are split so each covers **one topic from the official MoE textbook chapter list**
rather than a whole packed chapter. Example — Grade 9 Biology Unit 6 now runs
6.1 Definitions of Common Ecological Terms, 6.2 Biotic and Abiotic Components,
6.3 Ecological Levels, 6.4 Biomes, 6.5 Ecological Succession, 6.6 Ecological Relationships
(previously one 10,500-character "6.1 Ecology" lesson).

Regenerate after any content change:

    python3 split_lessons.py --report        # see what can be split
    python3 split_lessons.py                 # split mega-lessons in place
    python3 qbank.py                         # 10 questions + flashcards per lesson
    python3 make_static_site.py --out docs   # rebuild this site
