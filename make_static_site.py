"""Generate a complete STATIC version of the platform for GitHub Pages / phone browsing.

Every page is plain HTML+CSS+JS - no server, no login - so the course can be opened in
any browser, including a phone. Content comes straight from the database; lesson
progress and quiz scores are stored in the browser (localStorage).

Output (default ./docs):
    index.html              landing + every grade/subject (links, progress ring)
    s/<subject>.html        unit + lesson tree with progress ticks
    l/<lesson>.html         Learn / Flashcards / Assessment tabs, quiz scored in-page
    assets/style.css        the real platform stylesheet
    assets/site.js          tabs, quiz engine, progress
    preview.html            the entire thing as one self-contained file

    python3 make_static_site.py
    python3 make_static_site.py --out docs --grades 9,10
"""
import argparse, html, json, os, re, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
esc = lambda s: html.escape(str(s if s is not None else ""), quote=True)
LETTERS = "ABCDEFGH"


# --------------------------------------------------------------------- helpers
def subj_path(sid):
    return "s/%d.html" % sid


def lesson_path(lid):
    return "l/%d.html" % lid


def head(title, rel="..", desc=""):
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · EduLearn</title>
<meta name="theme-color" content="#2e54d4">
<meta name="description" content="{esc(desc or "Ethiopian secondary school lessons, assessments and flashcards — lesson by lesson, free on any phone.")}">
<link rel="apple-touch-icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><rect width='64' height='64' rx='14' fill='%232e54d4'/><text x='32' y='44' font-family='Helvetica,Arial,sans-serif' font-size='30' font-weight='700' fill='%23fff' text-anchor='middle'>EL</text></svg>">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><rect width='64' height='64' rx='14' fill='%232e54d4'/><text x='32' y='44' font-family='Helvetica,Arial,sans-serif' font-size='30' font-weight='700' fill='%23fff' text-anchor='middle'>EL</text></svg>">
<link rel="stylesheet" href="{rel}/assets/style.css">
<script>try{{const m=document.cookie.match(/el_theme=([a-z]+)/);if(m&&m[1]==='dark')document.documentElement.dataset.theme='dark';}}catch(e){{}}</script>
</head><body>
<header class="topbar"><div class="wrap">
  <a class="brand" href="{rel}/index.html" style="color:inherit;text-decoration:none"><div class="logo">EL</div>EduLearn</a>
  <nav class="navlinks">
    <a href="{rel}/index.html">Home</a>
    <a href="javascript:void(0)" onclick="EL.toggleTheme()">Theme</a>
  </nav>
</div></header>
<main class="wrap" style="padding-bottom:70px">"""


FOOT = """</main>
<footer class="footer"><div class="wrap">
  <div><b style="color:#fff">EduLearn</b><br>Grade 9–12 interactive digital learning platform.</div>
  <div class="muted" style="color:#90a9c2">Static edition · progress is saved in this browser</div>
</div></footer>
<script src="{rel}/assets/site.js"></script>
</body></html>"""


def foot(rel=".."):
    return FOOT.replace("{rel}", rel)


# per-subject colours for the icon tiles (same palette as the app)
TILE = {"bio": ("#e8f8ee", "#12a150"), "chem": ("#fff5e2", "#e08b00"), "phys": ("#e8f0fe", "#1b6be4"),
        "engl": ("#fdeee4", "#e8590c"), "math": ("#f0ecfe", "#7048e8"), "agri": ("#e2f6f9", "#0c8599"),
        "hist": ("#fdf3da", "#a16207"), "geo": ("#e3f5f8", "#0b7285"), "econ": ("#eaf8ee", "#2b8a3e"),
        "citz": ("#fdeaf2", "#c2255c"), "civics": ("#fdeaf2", "#c2255c"), "ict": ("#eaf0ff", "#3b5bdb")}


# --------------------------------------------------------------------- index
def build_index(out):
    grades = {}
    for s in db.query("""SELECT s.id,s.grade,s.code,s.name,
                                (SELECT count(*) FROM lessons l JOIN units u ON l.unit_id=u.id WHERE u.subject_id=s.id) lessons,
                                (SELECT count(*) FROM units u WHERE u.subject_id=s.id) units
                         FROM subjects s ORDER BY s.grade, s.sort, s.name"""):
        grades.setdefault(s["grade"], []).append(s)
    total_l = db.query("SELECT count(*) n FROM lessons", one=True)["n"]
    total_q = db.query("SELECT count(*) n FROM questions WHERE scope='lesson'", one=True)["n"]
    total_f = db.query("SELECT count(*) n FROM flashcards", one=True)["n"]
    total_s = db.query("SELECT count(DISTINCT id) n FROM subjects", one=True)["n"]
    comma = lambda n: "{:,}".format(int(n or 0))
    grades_ready = sorted(grades)
    first_subj = grades[grades_ready[0]][0] if grades_ready else None
    ready = sorted(grades)
    def tile(name, code, big=False):
        bg, fg = TILE.get(code, ("#e8f0fe", "#1b6be4"))
        return (f'<div class="subj-tile" style="background:{bg};color:{fg}">{esc(name[:2]).upper()}</div>')

    # one grid per grade; the tabs show one at a time (all visible without JS)
    grids = []
    for g in ready:
        subs = "".join(f'''<div class="subjcard">
          <div class="subj-top">{tile(s["name"], s["code"])}
            <div><div class="subj-name">{esc(s["name"])}</div><div class="subj-grade">Grade {g}</div></div>
          </div>
          <div class="subj-meta"><span><b>{s["units"]}</b> units</span>
            <span><b>{s["lessons"]}</b> lessons</span><span><b>10</b> questions each</span></div>
          <a class="btn btn-primary subj-btn" href="{subj_path(s["id"])}">Open subject</a>
        </div>''' for s in grades[g])
        hidden = "" if g == ready[0] else " hidden"
        grids.append(f'<div class="subj-grid" data-grade="{g}"{hidden}>{subs}</div>')
    tabs = "".join(f'<button class="gtab{" on" if g == ready[0] else ""}" data-g="{g}" onclick="lbaTab({g})">Grade {g}</button>'
                   for g in ready) + ('<button class="gtab off" data-g="12" onclick="lbaTab(12)">Grade 12 · soon</button>' if 12 not in ready else "")
    g12 = ('<div class="lp-empty" id="g12note" hidden><b>Grade 12 is not published yet.</b><p>Grades 9, 10 and 11 are ready to study now. Grade 12 will appear here as soon as its subjects are loaded.</p></div>' if 12 not in ready else "")
    first_link = subj_path(first_subj["id"]) if first_subj else "#"
    first_name = esc(first_subj["name"]) if first_subj else "a subject"

    body = f'''
<section class="lp-hero"><div class="wrap lp-hero-grid">
  <div class="lp-hero-copy">
    <span class="lp-eyebrow">Grade 9–11 · Ethiopian curriculum</span>
    <h1>Study for your <span class="hl">exams</span> — and what comes after.</h1>
    <p class="lp-lede">Every unit and sub-unit of the textbook, lesson by lesson, with an
    assessment after each one and flashcards for the terms. On any phone, at no cost.</p>
    <div class="lp-cta">
      <a class="btn btn-primary btn-lg" href="{first_link}">Start with {first_name}</a>
      <a class="btn btn-ghost btn-lg" href="#subjects">Browse subjects</a>
    </div>
    <div class="lp-trust">No account needed · Works on any phone · Your progress is kept in this browser</div>
  </div>
  <div class="lp-hero-art">
    <div class="mock">
      <div class="mock-head"><span class="mock-dot"></span><b>How to use this edition</b><span class="mock-chip">free</span></div>
      <div class="mock-row"><span>1 · Open a subject</span><span class="muted">{comma(total_s)} to choose from</span></div>
      <div class="mock-row"><span>2 · Read a lesson</span><span class="muted">{comma(total_l)} lessons</span></div>
      <div class="mock-row"><span>3 · Flip the flashcards</span><span class="muted">{comma(total_f)} cards</span></div>
      <div class="mock-row now"><span>4 · Take its assessment</span><span class="mock-chip">10 questions</span></div>
      <div class="mock-foot">
        <div><b>10</b><span>questions per lesson</span></div>
        <div><b>80%</b><span>to pass</span></div>
        <div><b>125</b><span>final exam</span></div>
      </div>
    </div>
    <div class="mock-badge">Certificate on completion</div>
  </div>
</div></section>

<section class="lp-benefits"><div class="wrap">
  <h2 class="lp-h2">Make the next result feel reachable.</h2>
  <div class="lp-chips">
    <span class="lp-chip"><i class="bdot" style="background:#1b6be4"></i>Pass your exams</span>
    <span class="lp-chip"><i class="bdot" style="background:#e08b00"></i>Revise after class</span>
    <span class="lp-chip"><i class="bdot" style="background:#12a150"></i>Practise every lesson</span>
    <span class="lp-chip"><i class="bdot" style="background:#7048e8"></i>Study in your own time</span>
  </div>
</div></section>

<section class="lp-block"><div class="wrap">
  <h2 class="lp-h2">One subject, four ways to understand it.</h2>
  <p class="lp-sub">Read it, revise it, test it, then check the part that did not land.</p>
  <div class="lp-grid4">
    <div class="lp-fcard"><div class="ftile" style="background:#e8f0fe;color:#1b6be4">L</div>
      <b>Lessons</b><p>The textbook content for the exact grade, subject, unit and sub-unit you are on.</p></div>
    <div class="lp-fcard"><div class="ftile" style="background:#fff5e2;color:#e08b00">N</div>
      <b>Notes</b><p>The structured study notes for your subject, ready to read and download.</p></div>
    <div class="lp-fcard"><div class="ftile" style="background:#e8f8ee;color:#12a150">Q</div>
      <b>Quizzes</b><p>Ten questions after every lesson, so you see what stuck before exam week.</p></div>
    <div class="lp-fcard"><div class="ftile" style="background:#f0ecfe;color:#7048e8">A</div>
      <b>Flashcards</b><p>The terms, definitions and formulas to memorise, one card at a time.</p></div>
  </div>
</div></section>

<section class="lp-split alt"><div class="wrap lp-split-grid">
  <div>
    <h2 class="lp-h2 left">Every lesson ends with a check.</h2>
    <div class="checklist">
      <div class="check"><span class="ck">✓</span><div><b>Ten questions, drawn from the lesson.</b>
        <p>Nothing is asked that the lesson did not cover.</p></div></div>
      <div class="check"><span class="ck">✓</span><div><b>You see why an answer was wrong.</b>
        <p>Every question comes with the reason, so the next attempt is better than the last.</p></div></div>
      <div class="check"><span class="ck">✓</span><div><b>Retake it as often as you need.</b>
        <p>Score 80% to pass the lesson and only your best score is kept.</p></div></div>
    </div>
  </div>
  <div class="chat-mock">
    <div class="cm-q">What is the difference between a cell wall and a cell membrane?</div>
    <div class="cm-a"><span class="cm-tag">Worked example</span>
      The cell wall is a rigid outer layer found in plant cells, while the cell membrane
      controls what enters and leaves the cell.
      <div class="cm-cite"><b>Unit 3 · Cells</b><span>Biology · Grade 9</span></div>
    </div>
  </div>
</div></section>

<section class="lp-block" id="subjects"><div class="wrap">
  <h2 class="lp-h2">Pick a subject by colour, icon, and grade.</h2>
  <p class="lp-sub">{len(ready)} grades · {comma(total_s)} subjects · {comma(total_l)} lessons</p>
  <div class="gtabs">{tabs}</div>
  {''.join(grids)}{g12}
</div></section>

<section class="lp-stats"><div class="wrap">
  <div class="lp-statrow">
    <div><b>{comma(total_s)}</b><span>subjects</span></div>
    <div><b>{comma(total_l)}</b><span>lessons</span></div>
    <div><b>{comma(total_q)}</b><span>practice questions</span></div>
    <div><b>{comma(total_f)}</b><span>flashcards</span></div>
  </div>
</div></section>

<section class="lp-split"><div class="wrap lp-split-grid flip">
  <div class="certmini">
    <div class="certmini-in"><div class="certmini-seal">EL</div>
      <div class="certmini-title">Certificate of Completion</div>
      <div class="certmini-name">Student Name</div>
      <div class="certmini-sub">Biology · Grade 9</div>
      <div class="certmini-foot"><span>Score 108 / 125</span><span>ID CERT-2026-95834</span></div>
    </div>
  </div>
  <div>
    <h2 class="lp-h2 left">Finish with a certificate that can be verified.</h2>
    <p class="lp-sub left">Pass every lesson, then sit the 125-question final examination for the subject.
    Score 100 or more and the certificate carries the name, the subject, the score and a unique ID.</p>
    <div class="checklist">
      <div class="check"><span class="ck">✓</span><div><b>Anyone can check it is genuine.</b>
        <p>A school, a parent or an employer can verify it with the ID — no account needed.</p></div></div>
      <div class="check"><span class="ck">✓</span><div><b>This edition is the reading side.</b>
        <p>Accounts, final examinations and certificates live on the full platform, which is free too.</p></div></div>
    </div>
    <div class="lp-cta"><a class="btn btn-primary btn-lg" href="{first_link}">Start now</a></div>
  </div>
</div></section>

<section class="lp-block"><div class="wrap">
  <h2 class="lp-h2">Questions students ask</h2>
  <p class="lp-sub">Straight answers before you start.</p>
  <div class="faq">
    <details><summary>Does this cost anything, or need an account?</summary><p>No. This edition is open — open a subject and begin reading. An account is only needed on the full platform, for certificates.</p></details>
    <details><summary>Do I need a computer?</summary><p>No. It is built for a phone and works on a normal mobile connection.</p></details>
    <details><summary>What happens if I fail an assessment?</summary><p>Nothing is lost. You are shown why each answer was wrong and can retake it as often as you like. Only your best score is kept.</p></details>
    <details><summary>Is this the real textbook?</summary><p>Yes — the lessons come from the Ministry of Education textbooks, arranged lesson by lesson to match the official units.</p></details>
    <details><summary>Which grades are here?</summary><p>Grades 9, 10 and 11 are complete. Grade 12 is being added.</p></details>
  </div>
</div></section>

<section class="lp-final"><div class="wrap lp-final-in">
  <h2>Start the study streak that gets you there.</h2>
  <p>Read a lesson, answer its questions, pass it, and move on. The whole curriculum is open here.</p>
  <a class="btn btn-amber btn-lg" href="{first_link}">Start studying now</a>
</div></section>
'''
    body += """<script>
function lbaTab(g){
  document.querySelectorAll('.gtab').forEach(function(b){ b.classList.toggle('on', +b.dataset.g===+g); });
  var target = document.querySelector('.subj-grid[data-grade="'+g+'"]');
  document.querySelectorAll('.subj-grid[data-grade]').forEach(function(p){ p.hidden = (+p.dataset.g!==+g); });
  var note = document.getElementById('g12note'); if(note) note.hidden = !!target;
}
</script>"""

    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(head("Grade 9–11 courses", ".", "Every Ethiopian secondary school lesson for Grades 9–11, each with its own assessment and flashcards. Free, phone-first, no account needed.") + body + foot("."))
    return total_l, total_q


# --------------------------------------------------------------------- subject
def build_subject(out, subject):
    sid = subject["id"]
    units = db.query("SELECT id,number,title FROM units WHERE subject_id=? ORDER BY number", (sid,))
    blocks = []
    for u in units:
        lessons = db.query("SELECT id,number,title FROM lessons WHERE unit_id=? ORDER BY number", (u["id"],))
        rows = "".join(f'''<a class="lesson" href="../{lesson_path(l["id"])}" data-lesson="{l["id"]}">
          <div class="st" data-mark="{l["id"]}">{l["number"]}</div>
          <div class="nm">Lesson {l["number"]}. {esc(l["title"])}</div>
          <span class="pill pill-not" data-pill="{l["id"]}">◌ Not started</span></a>''' for l in lessons)
        blocks.append(f'''<div class="unit"><div class="head">
          <span class="pill pill-prog" data-unitpill="{u["id"]}">0/{len(lessons)}</span>
          <div class="tt">{esc(u["title"])}</div>
          <div style="width:150px"><div class="pbar"><div class="pfill" style="width:0%" data-unitbar="{u["id"]}"></div></div></div>
        </div><div class="lessons" data-unit="{u["id"]}" data-count="{len(lessons)}">{rows}</div></div>''')
    body = f'''
<div class="crumb"><a href="../index.html">Home</a> › <b>{esc(subject["name"])}</b></div>
<div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap">
  <div style="font-size:40px">📘</div>
  <div style="flex:1;min-width:220px">
    <h1 style="margin:0">Grade {subject["grade"]} {esc(subject["name"])}</h1>
    <div class="muted">{len(units)} units · {sum(1 for b in blocks)} unit blocks · lesson-by-lesson with assessments</div>
  </div>
</div>
<div class="card mt16" style="padding:14px 18px"><div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
  <div style="font-weight:700">Subject progress</div>
  <div style="flex:1;max-width:320px"><div class="pbar"><div class="pfill blue" style="width:0%" data-subbar="{sid}"></div></div></div>
  <span class="muted" data-subprog="{sid}">0 lessons completed</span>
</div></div>
<div class="unitlist mt24">{''.join(blocks)}</div>'''
    with open(os.path.join(out, subj_path(sid)), "w", encoding="utf-8") as fh:
        fh.write(head("%s Grade %d" % (subject["name"], subject["grade"]), "..") + body + foot(".."))


# --------------------------------------------------------------------- lesson
def build_lesson(out, lesson):
    lid = lesson["id"]
    qs = db.query("""SELECT id,qtype,prompt,choices,answer_index,explanation,difficulty,concept
                     FROM questions WHERE scope='lesson' AND lesson_id=? ORDER BY sort,id""", (lid,))
    cards = db.query("SELECT front,back FROM flashcards WHERE lesson_id=? ORDER BY sort,id", (lid,))
    total = db.query("SELECT count(*) n FROM lessons WHERE unit_id=?", (lesson["uid"],), one=True)["n"]
    prev = db.query("SELECT id,title FROM lessons WHERE unit_id=? AND number<? ORDER BY number DESC LIMIT 1",
                    (lesson["uid"], lesson["number"]), one=True)
    nxt = db.query("SELECT id,title FROM lessons WHERE unit_id=? AND number>? ORDER BY number LIMIT 1",
                   (lesson["uid"], lesson["number"]), one=True)
    quiz = [{"q": q["prompt"], "c": json.loads(q["choices"]), "a": q["answer_index"],
             "why": q["explanation"], "d": q["difficulty"], "k": q["concept"] or ""} for q in qs]
    tabs = "".join(f'<button class="subtab {"on" if k == "learn" else ""}" data-tab="{k}">{lab}</button>'
                   for k, lab in (("learn", "Learn"), ("flash", f"Flashcards ({len(cards)})"),
                                  ("quiz", f"Assessment ({len(quiz)} Q)")))
    fc_html = ""
    if cards:
        fc_html = ('<div class="fcard-wrap" onclick="EL.flip()"><div class="fcard" id="fc">'
                   f'<div class="face" id="fcf">{esc(cards[0]["front"])}</div>'
                   f'<div class="face back" id="fcb">{esc(cards[0]["back"])}</div></div></div>'
                   '<div style="display:flex;justify-content:space-between;align-items:center;margin-top:18px">'
                   '<button class="btn btn-ghost" onclick="EL.fcPrev()">← Prev</button>'
                   '<span class="muted" id="fci">1 / ' + str(len(cards)) + '</span>'
                   '<button class="btn btn-primary" onclick="EL.fcNext()">Next →</button></div>')
    else:
        fc_html = "<p class='muted'>No flashcards for this lesson.</p>"
    body = f'''
<div class="crumb"><a href="../index.html">Home</a> › <a href="../{subj_path(lesson["sid"])}">{esc(lesson["sname"])}</a> › <b>{esc(lesson["utitle"])}</b></div>
<div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
  <div style="flex:1;min-width:200px">
    <span class="muted" style="font-size:12px">UNIT {lesson["un"]} · LESSON {lesson["number"]} OF {total} · GRADE {lesson["grade"]} {esc(lesson["sname"]).upper()}</span>
    <h1 style="margin:2px 0 0;font-size:24px">{esc(lesson["title"])}</h1>
  </div>
  <span class="pill pill-not" id="statuspill" data-lstatus="{lid}">◌ Not started</span>
</div>
<div class="pbar" style="margin:8px 0 14px"><div class="pfill blue" style="width:{round((lesson["number"]-1)/max(1,total)*100)}%"></div></div>
<div class="subtabs">{tabs}</div>
<div id="panel-learn" class="tabpanel"><div class="lessonContent">{lesson["content_html"] or ""}</div>
  <div class="card mt16"><b>Summary</b><p class="muted">Read the lesson, memorise the key terms with the Flashcards tab,
  then take the assessment — 80% passes the lesson.</p></div></div>
<div id="panel-flash" class="tabpanel hide">{fc_html}</div>
<div id="panel-quiz" class="tabpanel hide"><div id="quizhost"></div></div>
<div style="display:flex;justify-content:space-between;gap:10px;margin-top:26px;flex-wrap:wrap">
  {f'<a class="btn btn-ghost" href="../{lesson_path(prev["id"])}">← Previous</a>' if prev else '<span></span>'}
  {f'<a class="btn btn-primary" href="../{lesson_path(nxt["id"])}">Next lesson →</a>' if nxt else f'<a class="btn btn-primary" href="../{subj_path(lesson["sid"])}">Unit complete — view subject →</a>'}
</div>
<script id="lesson-data" type="application/json">{json.dumps({"id": lid, "cards": cards, "quiz": quiz})}</script>'''
    with open(os.path.join(out, lesson_path(lid)), "w", encoding="utf-8") as fh:
        fh.write(head(lesson["title"], "..") + body + foot(".."))


# --------------------------------------------------------------------- assets
SITE_JS = r"""/* EduLearn static edition - tabs, quiz engine, progress (localStorage) */
const EL = (() => {
  const KEY = 'edulearn_static_v1';
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; } };
  const save = (d) => { try { localStorage.setItem(KEY, JSON.stringify(d)); } catch (e) {} };
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const data = () => { const el = document.getElementById('lesson-data'); return el ? JSON.parse(el.textContent) : null; };

  function toggleTheme() {
    const dark = document.documentElement.dataset.theme === 'dark';
    document.documentElement.dataset.theme = dark ? '' : 'dark';
    document.cookie = 'el_theme=' + (dark ? 'light' : 'dark') + ';path=/;max-age=31536000';
  }

  /* ---------------- subject + index progress ---------------- */
  function refreshProgress() {
    const done = load();
    document.querySelectorAll('[data-prog],[data-subprog],[data-unitpill],[data-subbar],[data-subprog],[data-unitbar],[data-mark],[data-pill]').forEach(el => {});
    // subject page rows
    document.querySelectorAll('[data-lesson]').forEach(row => {
      const id = row.dataset.lesson, rec = done[id];
      const mark = row.querySelector('[data-mark]'), pill = row.querySelector('[data-pill]');
      if (rec && mark) { mark.classList.add('done'); mark.textContent = '✓'; }
      if (rec && pill) { pill.className = 'pill pill-done'; pill.textContent = (rec.p ? '✓ ' + rec.p + '%' : '✓ Done'); }
    });
    // unit bars
    document.querySelectorAll('[data-unit]').forEach(u => {
      const total = +u.dataset.count || 0;
      let d = 0; u.querySelectorAll('[data-lesson]').forEach(r => { if (done[r.dataset.lesson]) d++; });
      const bar = document.querySelector('[data-unitbar="' + u.dataset.unit + '"]');
      if (bar) bar.style.width = (total ? Math.round(d / total * 100) : 0) + '%';
      const pill = document.querySelector('[data-unitpill="' + u.dataset.unit + '"]');
      if (pill) { pill.textContent = d + '/' + total; if (d === total && total) { pill.className = 'pill pill-done'; } }
    });
    // subject summary
    const sbar = document.querySelector('[data-subbar]');
    if (sbar) {
      const rows = [...document.querySelectorAll('[data-lesson]')];
      const d = rows.filter(r => done[r.dataset.lesson]).length;
      sbar.style.width = (rows.length ? Math.round(d / rows.length * 100) : 0) + '%';
      const lab = document.querySelector('[data-subprog]');
      if (lab) lab.textContent = d + ' / ' + rows.length + ' lessons completed';
    }
    // index cards
    document.querySelectorAll('a.card[data-subj]').forEach(card => {});
  }

  /* ---------------- lesson page ---------------- */
  function initLesson() {
    const d = data(); if (!d) return;
    const done = load(), rec = done[d.id];
    const pill = document.getElementById('statuspill');
    if (rec && pill) { pill.className = 'pill pill-done'; pill.textContent = '✓ Passed ' + (rec.p || '') + '%'; }
    // tabs
    document.querySelectorAll('.subtab[data-tab]').forEach(b => b.onclick = () => showTab(b.dataset.tab));
    // flashcards
    let i = 0, show = false;
    const fc = document.getElementById('fc');
    if (d.cards && d.cards.length) {
      window.__fc = () => ({ i, cards: d.cards });
    }
    EL_state = { i: 0 };
    // quiz
    const qstate = { step: 0, sel: {}, submitted: false };
    function renderQuiz() {
      const host = document.getElementById('quizhost'); if (!host) return;
      if (!d.quiz.length) { host.innerHTML = "<div class='card'><b>Assessment</b><p class='muted'>No questions for this lesson yet.</p></div>"; return; }
      if (qstate.submitted) { renderResult(); return; }
      const q = d.quiz[qstate.step], sel = qstate.sel[qstate.step];
      const opts = q.c.map((c, j) => `<div class="opt ${sel === j ? 'sel' : ''}" onclick="EL.pick(${j})">
        <span class="k">${LETTERS[j]}</span><div>${esc(c)}</div></div>`).join('');
      const answered = Object.keys(qstate.sel).length;
      host.innerHTML = `<div class="card"><div style="display:flex;gap:8px;align-items:center">
          <span class="pill pill-prog">Question ${qstate.step + 1} of ${d.quiz.length}</span>
          <span class="muted" style="font-size:12px">${esc(q.k)} · ${esc(q.d)}</span></div>
          <div class="pbar mt8"><div class="pfill" style="width:${Math.round(answered / d.quiz.length * 100)}%"></div></div></div>
        <div class="qcard"><h3 style="margin:6px 0 10px">${esc(q.q)}</h3>${opts}
        <div style="display:flex;justify-content:space-between;margin-top:16px;gap:8px">
          <button class="btn btn-ghost" ${qstate.step === 0 ? 'disabled' : ''} onclick="EL.nav(-1)">← Back</button>
          ${qstate.step === d.quiz.length - 1 ? '<button class="btn btn-primary" onclick="EL.submit()">Submit assessment ✓</button>'
            : '<button class="btn btn-primary" onclick="EL.nav(1)">Next →</button>'}
        </div></div>`;
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    function renderResult() {
      const host = document.getElementById('quizhost');
      let right = 0; d.quiz.forEach((q, j) => { if (qstate.sel[j] === q.a) right++; });
      const pct = Math.round(right / d.quiz.length * 100), passed = pct >= 80;
      const review = d.quiz.map((q, j) => {
        const ok = qstate.sel[j] === q.a;
        return `<div class="qcard"><div style="font-weight:700;margin-bottom:6px">${ok ? '✅' : '❌'} ${esc(q.q)}</div>
          <div class="reviewbox ${ok ? '' : 'err'}"><b>Your answer:</b> ${qstate.sel[j] == null ? 'Not answered' : esc(q.c[qstate.sel[j]])}</div>
          <div class="reviewbox"><b>Correct answer (${'ABCDEFGH'[q.a]}):</b> ${esc(q.c[q.a])}<br><br><b>Why:</b> ${esc(q.why || 'Covered in the lesson above.')}</div></div>`;
      }).join('');
      host.innerHTML = `<div class="center fadein" style="padding:10px 0">
          <h2>${passed ? 'Lesson completed 🎉' : 'Not passed yet'}</h2>
          <p>You scored <b>${right} / ${d.quiz.length}</b> (${pct}%). The pass mark is <b>80%</b>.</p>
          ${passed ? '<p class="muted">This lesson is now marked complete in this browser.</p>' : '<p class="muted">Review the explanations below, re-read the lesson, then retake.</p>'}
          <button class="btn btn-primary mt8" onclick="EL.retake()">Retake the assessment</button>
        </div><h3 class="mt16">Assessment review</h3>${review}`;
      const best = done[d.id] && done[d.id].p ? done[d.id].p : 0;
      if (passed) { done[d.id] = { p: Math.max(best, pct) }; save(done); }
      if (pill) { pill.className = passed ? 'pill pill-done' : 'pill pill-rev'; pill.textContent = passed ? '✓ Passed ' + pct + '%' : '↻ Review'; }
    }
    window.EL_pick = (j) => { qstate.sel[qstate.step] = j; renderQuiz(); };
    window.EL_nav = (dd) => { qstate.step = Math.max(0, Math.min(d.quiz.length - 1, qstate.step + dd)); renderQuiz(); };
    window.EL_submit = () => { qstate.submitted = true; renderResult(); };
    window.EL_retake = () => { qstate.submitted = false; qstate.sel = {}; qstate.step = 0; renderQuiz(); };
    showTab('learn');
    renderQuiz();
  }

  function showTab(k) {
    document.querySelectorAll('.tabpanel').forEach(p => p.classList.add('hide'));
    const p = document.getElementById('panel-' + k); if (p) p.classList.remove('hide');
    document.querySelectorAll('.subtab[data-tab]').forEach(b => b.classList.toggle('on', b.dataset.tab === k));
  }

  const api = {
    toggleTheme,
    showTab: (k) => showTab(k),
    pick: (j) => window.EL_pick && window.EL_pick(j),
    nav: (d) => window.EL_nav && window.EL_nav(d),
    submit: () => window.EL_submit && window.EL_submit(),
    retake: () => window.EL_retake && window.EL_retake(),
    flip: () => { const c = document.getElementById('fc'); if (c) c.classList.toggle('flip'); },
    fcPrev: () => fcStep(-1),
    fcNext: () => fcStep(1),
  };
  let fidx = 0, fcards = [];
  function fcStep(d) {
    if (!fcards.length) return;
    fidx = Math.max(0, Math.min(fcards.length - 1, fidx + d));
    const c = document.getElementById('fc'); if (c) c.classList.remove('flip');
    document.getElementById('fcf').textContent = fcards[fidx].front;
    document.getElementById('fcb').textContent = fcards[fidx].back;
    const n = document.getElementById('fci'); if (n) n.textContent = (fidx + 1) + ' / ' + fcards.length;
  }
  const LETTERS = 'ABCDEFGH';
  document.addEventListener('DOMContentLoaded', () => {
    const d = data();
    if (d) { fcards = d.cards || []; initLesson(); } else { refreshProgress(); }
  });
  return api;
})();
"""

EXTRA_CSS = r"""
/* static-edition extras */
a.card.click{display:block;color:inherit;text-decoration:none;transition:.15s}
a.card.click:hover{transform:translateY(-2px);box-shadow:var(--shadow-lg);text-decoration:none}
a.lesson{color:inherit;text-decoration:none}
a.lesson:hover{background:var(--soft);text-decoration:none}
.tabpanel.hide{display:none}
html[data-theme="dark"]{--bg:#0f1420;--surface:#171e2c;--line:#26314a;--line2:#2f3c59;--ink:#e8ecf6;--mut:#9aa7c0;--soft:#1c2434;--soft2:#202a3d}
html[data-theme="dark"] body{background:var(--bg);color:var(--ink)}
html[data-theme="dark"] .card,html[data-theme="dark"] .qcard,html[data-theme="dark"] .unit{background:var(--surface);border-color:var(--line)}
html[data-theme="dark"] .opt{background:var(--surface);border-color:var(--line)}
html[data-theme="dark"] .opt.sel{background:var(--soft2)}
html[data-theme="dark"] h1,html[data-theme="dark"] h2,html[data-theme="dark"] h3,html[data-theme="dark"] h4{color:var(--ink)}
html[data-theme="dark"] .fcard .face{background:var(--surface);border-color:var(--line)}
html[data-theme="dark"] .reviewbox{background:var(--soft);border-color:var(--line)}
html[data-theme="dark"] .muted{color:var(--mut)}
html[data-theme="dark"] .lessonContent code{background:#222c40}
html[data-theme="dark"] .lessonContent table{background:var(--surface)}
html[data-theme="dark"] .lessonContent th{background:var(--soft)}
html[data-theme="dark"] .hero{background:linear-gradient(135deg,#16203a,#1b2748)}
@media (max-width:640px){
  .wrap{padding:0 14px}
  .hero h1{font-size:24px}
  .navlinks{font-size:13px}
  .qcard{padding:16px}
  .lesson .nm{font-size:13.5px}
}
"""


def build_assets(out):
    os.makedirs(os.path.join(out, "assets"), exist_ok=True)
    with open(os.path.join(BASE, "static", "style.css"), encoding="utf-8") as fh:
        css = fh.read()
    with open(os.path.join(out, "assets", "style.css"), "w", encoding="utf-8") as fh:
        fh.write(css + "\n" + EXTRA_CSS)
    with open(os.path.join(out, "assets", "site.js"), "w", encoding="utf-8") as fh:
        fh.write(SITE_JS)


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(BASE, "docs"))
    ap.add_argument("--grades", default="")
    args = ap.parse_args()
    db.init_db()
    out = os.path.abspath(args.out)
    if os.path.isdir(out):
        for name in ("index.html", "assets", "s", "l"):
            p = os.path.join(out, name)
            if os.path.isdir(p):
                shutil.rmtree(p)
            elif os.path.exists(p):
                os.remove(p)
    os.makedirs(os.path.join(out, "s"), exist_ok=True)
    os.makedirs(os.path.join(out, "l"), exist_ok=True)
    grades = [int(x) for x in re.findall(r"\d+", args.grades)] or None
    where = "WHERE grade IN (%s)" % ",".join("?" * len(grades)) if grades else ""
    subjects = db.query("SELECT id,grade,code,name FROM subjects %s ORDER BY grade,name" % where,
                        tuple(grades) if grades else ())
    build_assets(out)
    tl, tq = build_index(out)
    n_lessons = 0
    for s in subjects:
        build_subject(out, s)
        lw = "WHERE u.subject_id=?"
        for l in db.query("""SELECT l.id,l.title,l.number,l.content_html,u.id uid,u.number un,u.title utitle,
                                    s.id sid,s.name sname,s.grade,s.code scode
                             FROM lessons l JOIN units u ON l.unit_id=u.id JOIN subjects s ON u.subject_id=s.id
                             WHERE u.subject_id=? ORDER BY u.number,l.number""", (s["id"],)):
            l["uid"] = l["uid"]
            build_lesson(out, l)
            n_lessons += 1
        print("  %-12s grade %-2s -> %d lessons" % (s["name"], s["grade"],
              db.query("SELECT count(*) n FROM lessons l JOIN units u ON l.unit_id=u.id WHERE u.subject_id=?",
                       (s["id"],), one=True)["n"]))
    print("static site:", out)
    print("  subjects: %d | lessons: %d | index says %d lessons / %d questions" % (len(subjects), n_lessons, tl, tq))
    print("  open: file://%s/index.html" % out)


if __name__ == "__main__":
    main()
