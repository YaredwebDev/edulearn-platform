"""Build a self-contained static snapshot of the platform (real content, real styling).

The snapshot opens in any browser / file viewer, needs no server and no login, and is
handy when the sandbox preview cannot be displayed. It shows the real screens a student
walks through: landing, dashboard, subject tree, a lesson with its content, flashcards
and the 10-question assessment - all rendered from the live database.

    python3 make_snapshot.py                # writes ../platform-preview.html
    python3 make_snapshot.py --out FILE     # choose the destination
    python3 make_snapshot.py --lesson 777   # pick which lesson to feature
"""
import argparse, html, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db  # noqa: E402

esc = lambda s: html.escape(str(s if s is not None else ""))


def load_css():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "style.css")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def pick_lesson(preferred=None):
    if preferred:
        row = db.query("""SELECT l.id,l.title,l.number,u.number un,u.title ut,u.id uid,
                                 s.name sname,s.code scode,s.grade,s.id sid
                          FROM lessons l JOIN units u ON l.unit_id=u.id JOIN subjects s ON u.subject_id=s.id
                          WHERE l.id=?""", (preferred,), one=True)
        if row:
            return row
    return db.query("""SELECT l.id,l.title,l.number,u.number un,u.title ut,u.id uid,
                              s.name sname,s.code scode,s.grade,s.id sid
                       FROM lessons l JOIN units u ON l.unit_id=u.id JOIN subjects s ON u.subject_id=s.id
                       WHERE s.code='chem' AND s.grade=9
                       ORDER BY u.number,l.number LIMIT 1""", one=True)


def topbar(user=None):
    links = ('<a href="#">Dashboard</a><a href="#">Certificates</a><a href="#">Verify</a>'
             if user else '<a href="#">Verify a certificate</a><a class="btn btn-primary" href="#">Start Learning</a>')
    return f'''<header class="topbar"><div class="wrap">
    <div class="brand"><div class="logo">EL</div>EduLearn</div>
    <nav class="navlinks">{links}</nav></div></header>'''


def section(n, title, note, body):
    return f'''<section class="block"><div class="wrap">
    <div class="shotlabel"><span class="shotnum">{n}</span><b>{esc(title)}</b><span class="muted">— {note}</span></div>
    <div class="shot">{body}</div></div></section>'''


def build_lesson_block(lesson):
    lid = lesson["id"]
    content = db.query("SELECT content_html FROM lessons WHERE id=?", (lid,), one=True)["content_html"] or ""
    total = db.query("SELECT count(*) n FROM lessons WHERE unit_id=?", (lesson["uid"],), one=True)["n"]
    nxt = db.query("SELECT id,title FROM lessons WHERE unit_id=? AND number>? ORDER BY number LIMIT 1",
                   (lesson["uid"], lesson["number"]), one=True)
    prev = db.query("SELECT id,title FROM lessons WHERE unit_id=? AND number<? ORDER BY number DESC LIMIT 1",
                    (lesson["uid"], lesson["number"]), one=True)
    tabs = "".join(f'<button class="subtab {"on" if k == "learn" else ""}">{lab}</button>'
                   for k, lab in (("learn", "Learn"), ("flash", "Flashcards"), ("quiz", "Assessment")))
    pct = round((lesson["number"] - 1) / max(1, total) * 100)
    return f'''<div style="max-width:920px;margin:0 auto">
    <div class="crumb"><a href="#">Home</a> › <a href="#">Dashboard</a> ›
      <a href="#">{esc(lesson["sname"])}</a> › <b>{esc(lesson["ut"])}</b></div>
    <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
      <div style="flex:1;min-width:200px">
        <span class="muted" style="font-size:12px">UNIT {lesson["un"]} · LESSON {lesson["number"]} OF {total} · GRADE {lesson["grade"]} {esc(lesson["sname"]).upper()}</span>
        <h1 style="margin:2px 0 0;font-size:26px">{esc(lesson["title"])}</h1></div>
      <span class="pill pill-not">◌ Not started</span></div>
    <div class="pbar" style="margin:8px 0 14px"><div class="pfill blue" style="width:{pct}%"></div></div>
    <div class="subtabs">{tabs}</div>
    <div class="lessonContent">{content}</div>
    <div style="display:flex;justify-content:space-between;margin-top:22px">
      <button class="btn btn-ghost">← Previous</button>
      <button class="btn btn-primary">{'Next lesson →' if nxt else 'Unit complete — view subject →'}</button></div></div>'''


def build_quiz_block(lesson):
    qs = db.query("""SELECT id,qtype,prompt,choices,answer_index,explanation,difficulty,concept
                     FROM questions WHERE scope='lesson' AND lesson_id=? ORDER BY sort LIMIT 10""", (lesson["id"],))
    if not qs:
        return "<p class='muted'>No questions for this lesson yet.</p>"
    letters = "ABCD"
    cards = []
    for i, q in enumerate(qs, 1):
        ch = json.loads(q["choices"])
        ans = q["answer_index"]
        opts = "".join(
            f'<div class="opt {"correct" if j == ans else ""}"><span class="k">{letters[j]}</span>'
            f'<div>{esc(c)}</div>{"&nbsp;✓" if j == ans else ""}</div>' for j, c in enumerate(ch))
        cards.append(f'''<div class="qcard">
      <div style="display:flex;gap:8px;align-items:center">
        <span class="pill pill-prog">Question {i} of {len(qs)}</span>
        <span class="muted" style="font-size:12px">{esc(q["concept"])} · {esc(q["difficulty"])}</span></div>
      <h3 style="margin:10px 0 8px">{esc(q["prompt"]).replace(chr(10), "<br>")}</h3>
      {opts}
      <div class="reviewbox"><b>Why:</b> {esc(q["explanation"])}</div></div>''')
    return ("<div style='max-width:820px;margin:0 auto'>"
            "<div class='card'><b>Assessment — 10 questions, 80% to pass</b>"
            "<p class='muted' style='margin:6px 0 0'>Generated from this lesson's own text. "
            "Below, each question is shown with its correct option marked ✓ and the explanation "
            "a student sees when they get it wrong.</p></div>"
            + "".join(cards) + "</div>")


def build_flashcards(lesson):
    cards = db.query("SELECT front,back FROM flashcards WHERE lesson_id=? ORDER BY sort LIMIT 4", (lesson["id"],))
    if not cards:
        return "<p class='muted'>No flashcards for this lesson yet.</p>"
    out = ["<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px'>"]
    for c in cards:
        out.append(f'''<div class="card" style="min-height:150px;display:flex;flex-direction:column;justify-content:center">
          <div style="font-weight:700;color:var(--brand-deep);text-align:center">{esc(c["front"])}</div>
          <div class="muted" style="margin-top:10px;font-size:13.5px;text-align:center">{esc(c["back"])}</div></div>''')
    out.append("</div>")
    return "".join(out)


def build_landing():
    grades = {}
    for r in db.query("""SELECT s.grade, s.code, s.name,
                                (SELECT count(*) FROM lessons l JOIN units u ON l.unit_id=u.id
                                 WHERE u.subject_id=s.id) lessons
                         FROM subjects s ORDER BY s.grade, s.sort, s.name"""):
        grades.setdefault(r["grade"], []).append(r)
    blocks = []
    for g in sorted(grades):
        chips = "".join(f'<span class="chip">{esc(s["name"])} · {s["lessons"]} lessons</span>'
                        for s in grades[g])
        blocks.append(f'<div class="card"><h3>Grade {g}</h3>'
                      f'<div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">{chips}</div></div>')
    return f'''<div class="hero"><div class="wrap">
      <div class="badge-hero"><span class="chip">Interactive digital teacher</span>
      <span class="chip">Certificate on completion</span><span class="chip">Progress tracking</span></div>
      <h1>Master your Grade 9–12 subjects, lesson by lesson.</h1>
      <p class="lede">EduLearn turns your complete textbooks into an interactive classroom — study each lesson,
      quiz yourself, revise with flashcards, and earn a professional certificate when you master a subject.</p>
      <div class="cta-row"><button class="btn btn-primary" style="font-size:15px">Begin registration</button>
      <button class="btn btn-ghost" style="background:#fff;color:#0f3d6b">How it works</button></div></div></div>
      <div class="wrap" style="margin-top:26px"><h2 class="sec">Choose your grade</h2>
      <div class="grid g3">{''.join(blocks)}</div></div>'''


def build_dashboard():
    user = db.query("SELECT full_name,grade FROM users ORDER BY id LIMIT 1", one=True)
    if not user:
        return "<p class='muted'>No student accounts in the database.</p>"
    subs = db.query("""SELECT s.name,s.code,s.grade,
                              (SELECT count(*) FROM lessons l JOIN units u ON l.unit_id=u.id WHERE u.subject_id=s.id) total
                       FROM subjects s WHERE s.grade=? ORDER BY s.name""", (user["grade"],))
    cards = []
    for s in subs:
        cards.append(f'''<div class="card"><div style="display:flex;align-items:center;gap:10px">
          <div class="logo" style="width:34px;height:34px;font-size:13px">{esc(s["name"][:2]).upper()}</div>
          <div><b>{esc(s["name"])}</b><div class="muted" style="font-size:12px">Grade {s["grade"]}</div></div></div>
          <div class="pbar" style="margin:12px 0 6px"><div class="pfill" style="width:0%"></div></div>
          <div class="muted" style="font-size:12.5px">0 / {s["total"]} lessons · <span class="pill pill-not">◌ Not started</span></div></div>''')
    return f'''<div style="max-width:1000px;margin:0 auto">
      <h1 style="margin:0 0 4px">Welcome back, {esc(user["full_name"])}</h1>
      <p class="muted" style="margin:0 0 18px">Grade {user["grade"]} student · progress is saved on every lesson you pass.</p>
      <div class="grid g2">{''.join(cards)}</div></div>'''


def build_subject(lesson):
    units = db.query("SELECT id,number,title FROM units WHERE subject_id=? ORDER BY number", (lesson["sid"],))
    out = [f'''<div style="max-width:1000px;margin:0 auto">
      <div class="crumb"><a href="#">Home</a> › <a href="#">Dashboard</a> › <b>{esc(lesson["sname"])}</b></div>
      <h1 style="margin:0">Grade {lesson["grade"]} {esc(lesson["sname"])}</h1>
      <p class="muted">{esc(lesson["sname"])} lesson-by-lesson with quizzes, flashcards, and certification.</p>
      <button class="btn btn-primary" style="margin:14px 0">Start learning — {esc(lesson["title"])} →</button>''']
    for u in units:
        lessons = db.query("SELECT id,number,title FROM lessons WHERE unit_id=? ORDER BY number", (u["id"],))
        rows = []
        for l in lessons:
            done = "done" if l["id"] < lesson["id"] else ""
            mark = "✓" if done else l["number"]
            pill = '<span class="pill pill-done">✓ Done</span>' if done else '<span class="pill pill-not">◌ Not started</span>'
            rows.append(f'<div class="lesson"><div class="st {done}">{mark}</div>'
                        f'<div class="nm">Lesson {l["number"]}. {esc(l["title"])}</div>{pill}</div>')
        out.append(f'''<div class="unit"><div class="head"><span class="pill pill-prog">0/{len(lessons)}</span>
          <div class="tt">{esc(u["title"])}</div>
          <div style="width:150px"><div class="pbar"><div class="pfill" style="width:0%"></div></div></div>
          <button class="btn btn-ghost btn-sm">⬇ Unit PDF</button></div>
          <div class="lessons">{''.join(rows)}</div></div>''')
    out.append("</div>")
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "platform-preview.html"))
    ap.add_argument("--lesson", type=int)
    args = ap.parse_args()
    db.init_db()
    lesson = pick_lesson(args.lesson)
    if not lesson:
        print("No lessons in the database.")
        return
    stats = db.query("""SELECT (SELECT count(*) FROM subjects) subjects, (SELECT count(*) FROM lessons) lessons,
                               (SELECT count(*) FROM questions) questions, (SELECT count(*) FROM flashcards) flashcards""",
                     one=True)
    qcount = db.query("SELECT count(*) n FROM questions WHERE scope='lesson' AND lesson_id=?", (lesson["id"],), one=True)["n"]
    body = "".join([
        section(1, "The landing page", "what a new visitor sees", build_landing()),
        section(2, "A student's dashboard", "their grade's subjects, ready to open", build_dashboard()),
        section(3, "Inside a subject", f"{esc(lesson['sname'])} Grade {lesson['grade']} — every unit, every lesson",
                build_subject(lesson)),
        section(4, "A lesson", f"{esc(lesson['title'])} — the real lesson text from the database",
                build_lesson_block(lesson)),
        section(5, "Flashcards", "generated from that lesson's own terms", build_flashcards(lesson)),
        section(6, f"The assessment", f"{qcount} questions for this lesson, 80% to pass, every one explained",
                build_quiz_block(lesson)),
    ])
    css = load_css()
    doc = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EduLearn — platform snapshot</title>
<style>
{css}
/* ---- snapshot-only chrome ---- */
body{{padding-bottom:60px}}
.snaphead{{background:var(--grad);color:#fff;padding:26px 0 30px}}
.snaphead h1{{color:#fff;margin:0 0 6px;font-size:26px}}
.snaphead p{{margin:0;color:#dbe4ff;max-width:820px}}
.snapstats{{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}}
.snapstats span{{background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.25);border-radius:999px;
  padding:5px 12px;font-size:12.5px;font-weight:600}}
.shotlabel{{display:flex;align-items:center;gap:10px;margin:0 0 12px;font-size:15px}}
.shotnum{{background:var(--brand);color:#fff;width:24px;height:24px;border-radius:50%;display:inline-flex;
  align-items:center;justify-content:center;font-size:12.5px;font-weight:700;flex:none}}
.shot{{border:1px solid var(--line);border-radius:16px;overflow:hidden;background:var(--bg);box-shadow:var(--shadow)}}
.shot>section .wrap,.shot .hero .wrap{{padding-top:18px}}
.note-box{{background:var(--warn-soft);border:1px solid #f0dcb4;color:#6b4a06;border-radius:12px;
  padding:12px 16px;margin:18px auto;max-width:1000px;font-size:13.5px}}
</style></head><body>
<div class="snaphead"><div class="wrap">
  <h1>EduLearn — platform snapshot</h1>
  <p>A static, offline view of the real platform rendered from the live database. Every unit, lesson,
  question and flashcard below is genuine content — not a mockup. The interactive version runs on the
  preview server with logins, progress tracking and certificates.</p>
  <div class="snapstats">
    <span>{stats["subjects"]} subjects</span><span>{stats["lessons"]} lessons</span>
    <span>{stats["questions"]} assessment questions</span><span>{stats["flashcards"]} flashcards</span>
    <span>10 questions per lesson</span><span>80% pass · 100/125 to certify</span>
  </div></div></div>
<div class="note-box"><div class="wrap"><b>Note:</b> this file is a read-only snapshot for viewing.
Buttons and links are inert here — in the running app they navigate between screens and remember progress.</div></div>
{body}
<div class="footer"><div class="wrap"><div><b style="color:#fff">EduLearn</b><br>Grade 9–12 interactive digital learning platform.</div>
<div class="muted" style="color:#90a9c2">Learn → Practice → Test → Understand mistakes → Retake → Progress → Complete → Get Certified</div></div></div>
</body></html>'''
    out = os.path.abspath(args.out)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print("snapshot:", out, "|", round(len(doc) / 1024), "KB",
          "| featuring lesson:", lesson["id"], lesson["title"])


if __name__ == "__main__":
    main()
