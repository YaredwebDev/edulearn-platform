"""FastAPI backend for the Grade 9-12 digital learning platform.
Secure token auth, per-user data isolation, quiz/progress/certificate/notification
records, and a backend-enforced admin gate."""
import os, json, secrets, random, datetime, uuid
from fastapi import FastAPI, Request, Header, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import db, security, importer, generator

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")

app = FastAPI(title="EduLearn Platform")
db.init_db()

import admin_routes
app.include_router(admin_routes.router)

# ---------------- helpers ----------------
def fail(msg, code=400):
    return JSONResponse({"ok": False, "error": msg}, status_code=code)

def jsonok(data=None, **kw):
    d = {"ok": True}
    if data is not None:
        d.update(data)
    d.update(kw)
    return JSONResponse(d)

def bearer(request: Request):
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None

def current_user(request):
    tok = bearer(request)
    if not tok:
        raise HTTPException(401, "Not authenticated")
    payload = security.verify_token(tok)
    if not payload or payload.get("role") != "student":
        raise HTTPException(401, "Not authenticated")
    u = db.query("SELECT * FROM users WHERE id=?", (payload.get("uid"),), one=True)
    if not u:
        raise HTTPException(401, "Account not found")
    return u

def admin_required(request):
    tok = bearer(request)
    if not tok:
        raise HTTPException(401, "Not authenticated")
    session = db.query("SELECT token FROM admin_sessions WHERE token=?", (tok,), one=True)
    if not session:
        raise HTTPException(401, "Not authorized")
    payload = security.verify_token(tok)
    if not payload or payload.get("role") != "admin":
        raise HTTPException(401, "Not authorized")
    return payload

def sync_lesson(uid, lesson_id):
    """Recompute status of one lesson for a user; returns dict."""
    lp = db.query("SELECT * FROM lesson_progress WHERE user_id=? AND lesson_id=?", (uid, lesson_id), one=True)
    if not lp:
        return {"status": "Not Started", "best": 0, "best_total": 0, "attempts": 0}
    return {"status": lp["status"], "best": lp["best_score"], "best_total": lp["best_total"],
            "attempts": lp["attempts"]}

def count_lessons(unit_id):
    return db.query("SELECT count(*) n FROM lessons WHERE unit_id=?", (unit_id,), one=True)["n"]

def refresh_unit(uid, unit_id):
    total = count_lessons(unit_id)
    done = db.query("SELECT count(*) n FROM lesson_progress WHERE user_id=? AND lesson_id IN "
                    "(SELECT id FROM lessons WHERE unit_id=?) AND status='Completed'", (uid, unit_id), one=True)["n"]
    unit = db.query("SELECT subject_id FROM units WHERE id=?", (unit_id,), one=True)
    completed = 1 if done >= total and total > 0 else 0
    db.execute("INSERT OR IGNORE INTO unit_progress(user_id,unit_id) VALUES(?,?)", (uid, unit_id))
    db.execute("UPDATE unit_progress SET lessons_total=?,lessons_done=?,completed=?,completed_at=? WHERE user_id=? AND unit_id=?",
               (total, done, completed, db.now() if completed else None, uid, unit_id))
    refresh_subject(uid, unit["subject_id"])

def refresh_subject(uid, subject_id):
    total_u = db.query("SELECT count(*) n FROM units WHERE subject_id=?", (subject_id,), one=True)["n"]
    done_u = db.query("SELECT count(*) n FROM unit_progress WHERE user_id=? AND unit_id IN "
                      "(SELECT id FROM units WHERE subject_id=?) AND completed=1", (uid, subject_id), one=True)["n"]
    total_l = db.query("SELECT count(*) n FROM lessons WHERE unit_id IN (SELECT id FROM units WHERE subject_id=?)", (subject_id,), one=True)["n"]
    done_l = db.query("SELECT count(*) n FROM lesson_progress WHERE user_id=? AND lesson_id IN "
                      "(SELECT id FROM lessons WHERE unit_id IN (SELECT id FROM units WHERE subject_id=?)) AND status='Completed'",
                      (uid, subject_id), one=True)["n"]
    sp = db.query("SELECT * FROM subject_progress WHERE user_id=? AND subject_id=?", (uid, subject_id), one=True)
    final_unlocked = 1 if done_u >= total_u and total_u > 0 else 0
    status = "Not Started"
    if final_unlocked:
        status = "Units Complete"
    if sp and sp["final_passed"]:
        status = "Exam Passed"
    elif done_u > 0:
        status = "In Progress"
    db.execute("INSERT OR IGNORE INTO subject_progress(user_id,subject_id) VALUES(?,?)", (uid, subject_id))
    db.execute("""UPDATE subject_progress SET units_total=?,units_done=?,lessons_total=?,lessons_done=?,
                  status=?,final_unlocked=?,final_passed=?,best_exam=?,best_exam_total=? WHERE user_id=? AND subject_id=?""",
               (total_u, done_u, total_l, done_l, status,
                final_unlocked, (sp["final_passed"] if sp else 0),
                (sp["best_exam"] if sp else 0), (sp["best_exam_total"] if sp else 0),
                uid, subject_id))

# ---- model schemas (not required for most because we read form/json manually) ----
class RegModel(BaseModel):
    full_name: str; grade: int; phone: str; age: int; school: str; password: str
class LoginModel(BaseModel):
    phone: str; password: str

# ---------------- public ----------------
@app.get("/api/meta")
def meta():
    grades = {}
    for r in db.query("SELECT grade, code, name FROM subjects ORDER BY grade, sort, id"):
        grades.setdefault(r["grade"], []).append({"code": r["code"], "name": r["name"]})
    return jsonok({"grades": {str(k): v for k, v in sorted(grades.items())}})

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.post("/api/register")
def register(p: RegModel):
    name = (p.full_name or "").strip()
    if len(name) < 3:
        return fail("Enter your full name (min 3 characters).")
    if p.grade not in (9, 10, 11, 12):
        return fail("Grade must be 9, 10, 11 or 12.")
    phone = (p.phone or "").strip()
    if not security.is_valid_phone(phone):
        return fail("Enter a valid phone number.")
    if len((p.password or "")) < 6:
        return fail("Password must be at least 6 characters.")
    exists = db.query("SELECT id FROM users WHERE phone=?", (phone,), one=True)
    if exists:
        return fail("An account with this phone number already exists. Please log in.")
    hp = security.hash_password(p.password)
    uid = db.execute("INSERT INTO users(full_name,grade,phone,age,school,role,pwd_hash,salt,created_at) "
                     "VALUES(?,?,?,?,?,?,?,?,?)",
                     (name, p.grade, phone, p.age, p.school, "student", hp["hash"], hp["salt"], db.now()))
    tok = security.sign({"uid": uid, "role": "student"})
    # welcome notification
    wbody = ("Welcome, {}. Start by choosing your grade and a subject. "
             "Good luck learning!").format(name)
    nid = db.execute(
        "INSERT INTO notifications(audience,audience_value,title,body,created_by,created_at) "
        "VALUES(?,?,?,?,NULL,?)",
        ("one", str(uid), "Welcome to EduLearn", wbody, db.now()))
    db.execute("INSERT OR IGNORE INTO user_notifications(user_id,notification_id) VALUES(?,?)", (uid, nid))
    return jsonok({"token": tok, "user": public_user(uid)})

@app.post("/api/login")
def login(p: LoginModel):
    phone = (p.phone or "").strip()
    u = db.query("SELECT * FROM users WHERE phone=?", (phone,), one=True)
    if not u:
        return fail("Account not found. Please register first.", 404)
    if not security.verify_password(p.password, u["salt"], u["pwd_hash"]):
        return fail("Incorrect password.", 401)
    if u["role"] != "student":
        return fail("Use the admin sign-in.", 403)
    tok = security.sign({"uid": u["id"], "role": "student"})
    return jsonok({"token": tok, "user": public_user(u["id"])})

def public_user(uid):
    u = db.query("SELECT id,full_name,grade,phone,age,school,created_at FROM users WHERE id=?", (uid,), one=True)
    return u

# ---------------- student authed ----------------
@app.get("/api/me")
def me(request: Request):
    u = current_user(request)
    return jsonok({"user": public_user(u["id"])})

@app.get("/api/dashboard")
def dashboard(request: Request):
    u = current_user(request)
    uid = u["id"]
    # overall across subjects (compute live)
    subs = []
    overall_done = overall_total = 0
    cert_count = 0
    for s in db.query("SELECT * FROM subjects WHERE grade=? ORDER BY name", (u["grade"],)):
        total_l = db.query("SELECT count(*) n FROM lessons l JOIN units uu ON l.unit_id=uu.id WHERE uu.subject_id=?",
                           (s["id"],), one=True)["n"]
        done_l = db.query(
            """SELECT count(*) n FROM lesson_progress lp WHERE lp.user_id=? AND lp.status='Completed'
               AND lp.lesson_id IN (SELECT l.id FROM lessons l JOIN units uu ON l.unit_id=uu.id WHERE uu.subject_id=?)""",
            (uid, s["id"]), one=True)["n"]
        sp = db.query("SELECT * FROM subject_progress WHERE user_id=? AND subject_id=?", (uid, s["id"]), one=True)
        overall_total += total_l; overall_done += done_l
        c = db.query("SELECT count(*) n FROM certificates WHERE user_id=? AND subject_id=?", (uid, s["id"]), one=True)["n"]
        cert_count += c
        status = "Not Started"
        if sp and sp["final_passed"]:
            status = "Exam Passed"
        elif done_l > 0:
            status = "In Progress"
        elif total_l == done_l and total_l > 0:
            status = "Units Complete"
        subs.append({
            "id": s["id"], "code": s["code"], "name": s["name"],
            "status": status, "pct": pct(done_l, total_l),
            "lessons_done": done_l, "lessons_total": total_l,
            "certified": bool(c),
            "final_unlocked": bool(total_l > 0 and done_l >= total_l),
        })
    # continue learning: first non-completed lesson in order
    cont = None
    for s in db.query("SELECT id FROM subjects WHERE grade=? ORDER BY name", (u["grade"],)):
        row = db.query("""SELECT l.id, l.title, l.unit_id, u.number un, u.title utitle, s.name sname, s.code scode
                          FROM lessons l JOIN units u ON l.unit_id=u.id JOIN subjects s ON u.subject_id=s.id
                          WHERE u.subject_id=? AND s.grade=?
                          AND NOT EXISTS (SELECT 1 FROM lesson_progress lp WHERE lp.user_id=? AND lp.lesson_id=l.id AND lp.status='Completed')
                          ORDER BY u.number, l.number LIMIT 1""", (s["id"], u["grade"], uid), one=True)
        if row:
            cont = row; break
    recent_q = db.query("SELECT id,scope,lesson_id,subject_id,total,correct,percent,passed,submitted_at FROM attempts "
                        "WHERE user_id=? ORDER BY id DESC LIMIT 8", (uid,))
    for a in recent_q:
        if a["scope"] == "lesson":
            le = db.query("SELECT title FROM lessons WHERE id=?", (a["lesson_id"],), one=True)
            su = db.query("SELECT s.name,s.grade FROM subjects s JOIN units u ON s.id=u.subject_id "
                          "JOIN lessons l ON u.id=l.unit_id WHERE l.id=?", (a["lesson_id"],), one=True)
            a["label"] = (su["name"] if su else "Subject") + " · " + (le["title"] if le else "")
        else:
            su = db.query("SELECT name FROM subjects WHERE id=?", (a["subject_id"],), one=True)
            a["label"] = "Final Exam · " + (su["name"] if su else "")
    certs = db.query("SELECT * FROM certificates WHERE user_id=? ORDER BY issued_at DESC", (uid,))
    notifications = user_notifications(uid)
    overall_pct = pct(overall_done, overall_total)
    return jsonok({
        "user": public_user(uid),
        "overall": {"done": overall_done, "total": overall_total, "pct": overall_pct},
        "subjects": subs, "continue": cont, "recent": recent_q,
        "certificates": certs, "notifications": notifications,
    })

def pct(a, b):
    return round((a / b) * 100) if b else 0

@app.get("/api/subjects")
def subjects(request: Request, grade: int):
    u = current_user(request)
    out = []
    for s in db.query("SELECT * FROM subjects WHERE grade=? ORDER BY name", (grade,)):
        total_l = db.query("SELECT count(*) n FROM lessons l JOIN units uu ON l.unit_id=uu.id WHERE uu.subject_id=?", (s["id"],), one=True)["n"]
        done_l = db.query("""SELECT count(*) n FROM lesson_progress lp WHERE lp.user_id=? AND lp.status='Completed'
                             AND lp.lesson_id IN (SELECT l.id FROM lessons l JOIN units uu ON l.unit_id=uu.id WHERE uu.subject_id=?)""",
                          (u["id"], s["id"]), one=True)["n"]
        sp = db.query("SELECT * FROM subject_progress WHERE user_id=? AND subject_id=?", (u["id"], s["id"]), one=True)
        status = "Not Started"
        if sp and sp["final_passed"]:
            status = "Exam Passed"
        elif done_l > 0:
            status = "In Progress"
        out.append({"id": s["id"], "name": s["name"], "code": s["code"], "status": status,
                    "pct": pct(done_l, total_l), "lessons_done": done_l, "lessons_total": total_l})
    return jsonok({"grade": grade, "subjects": out})

@app.get("/api/subject/{sid}")
def subject_view(request: Request, sid: int):
    u = current_user(request)
    s = db.query("SELECT * FROM subjects WHERE id=?", (sid,), one=True)
    if not s or s["grade"] != u["grade"]:
        return fail("Subject not available for your grade.", 404)
    sp = db.query("SELECT * FROM subject_progress WHERE user_id=? AND subject_id=?", (u["id"], sid), one=True)
    units = []
    for un in db.query("SELECT * FROM units WHERE subject_id=? ORDER BY number", (sid,)):
        up = db.query("SELECT * FROM unit_progress WHERE user_id=? AND unit_id=?", (u["id"], un["id"]), one=True)
        lessons = []
        for l in db.query("SELECT id,number,title FROM lessons WHERE unit_id=? ORDER BY number", (un["id"],)):
            lp = db.query("SELECT * FROM lesson_progress WHERE user_id=? AND lesson_id=?", (u["id"], l["id"]), one=True)
            lessons.append({"id": l["id"], "title": l["title"], "status": (lp["status"] if lp else "Not Started"),
                            "best": (lp["best_score"] if lp else 0)})
        units.append({"id": un["id"], "title": un["title"],
                      "done": (up["lessons_done"] if up else 0), "total": len(lessons),
                      "lessons": lessons})
    return jsonok({"subject": {"id": s["id"], "name": s["name"], "code": s["code"]},
                   "progress": sp, "units": units})

@app.get("/api/lesson/{lid}")
def lesson_view(request: Request, lid: int):
    u = current_user(request)
    l = db.query("SELECT l.*, u.number un, u.title utitle, u.subject_id, s.name sname, s.code scode "
                 "FROM lessons l JOIN units u ON l.unit_id=u.id JOIN subjects s ON u.subject_id=s.id WHERE l.id=?", (lid,), one=True)
    if not l:
        return fail("Lesson not found", 404)
    # navigation
    prev = db.query("SELECT id,title FROM lessons WHERE unit_id=? AND number<? ORDER BY number DESC LIMIT 1",
                    (l["unit_id"], l["number"]), one=True)
    nxt = db.query("SELECT id,title FROM lessons WHERE unit_id=? AND number>? ORDER BY number ASC LIMIT 1",
                   (l["unit_id"], l["number"]), one=True)
    total_in_unit = count_lessons(l["unit_id"])
    lp = db.query("SELECT * FROM lesson_progress WHERE user_id=? AND lesson_id=?", (u["id"], lid), one=True)
    qcnt = db.query("SELECT count(*) n FROM questions WHERE scope='lesson' AND lesson_id=? AND status!='Rejected'", (lid,), one=True)["n"]
    return jsonok({
        "lesson": {"id": l["id"], "title": l["title"], "content_html": l["content_html"],
                   "number": l["number"], "unit_title": l["utitle"], "unit_number": l["un"],
                   "subject": l["sname"], "subject_id": l["subject_id"]},
        "unit": {"id": l["unit_id"], "total": total_in_unit},
        "prev": prev, "next": nxt,
        "progress": lp,
        "quiz_count": qcnt,
    })

# ------------------------------------------------------- downloadable notes
NOTES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes")

def _notes_files():
    """The uploaded study-notes files, with the subject each one belongs to."""
    out = []
    if not os.path.isdir(NOTES_DIR):
        return out
    for name in sorted(os.listdir(NOTES_DIR)):
        if not name.lower().endswith((".html", ".htm", ".md", ".txt", ".docx", ".pdf", ".zip")):
            continue
        path = os.path.join(NOTES_DIR, name)
        stem = os.path.splitext(name)[0]
        grade = None
        m = re.search(r"(?:grade|g)\s*(9|10|11|12)", stem, re.I)
        if m:
            grade = int(m.group(1))
        subject = stem.split("_")[0].strip().title() if "_" in stem else ""
        out.append({"name": name, "grade": grade, "subject": subject,
                    "size": os.path.getsize(path),
                    "url": "/api/notes/" + name})
    return out

@app.get("/api/notes")
def notes_index(request: Request, grade: int = None, subject_id: int = None):
    u = current_user(request)
    files = _notes_files()
    if subject_id:
        subj = db.query("SELECT name, grade FROM subjects WHERE id=?", (subject_id,), one=True)
        if subj:
            stem = subj["name"].lower()[:4]
            files = [f for f in files
                     if f["subject"].lower().startswith(stem) and f["grade"] == subj["grade"]]
    elif grade:
        files = [f for f in files if f["grade"] == grade]
    for f in files:                       # keep the subject's own grade first
        f["match"] = True
    return jsonok({"files": files})

@app.get("/api/notes/{name}")
def notes_download(request: Request, name: str):
    """Serve one notes file for download. Only plain names inside notes/ are allowed."""
    u = current_user(request)
    safe = os.path.basename(name)
    path = os.path.join(NOTES_DIR, safe)
    if not os.path.isfile(path):
        return fail("File not found", 404)
    media = "text/html" if safe.lower().endswith((".html", ".htm")) else "application/octet-stream"
    with open(path, "rb") as fh:
        blob = fh.read()
    return Response(content=blob, media_type=media,
                    headers={"Content-Disposition": 'attachment; filename="%s"' % safe})

# ---------------------------------------------------------------- AI tutor ("Ask")
_chat_ready = {"built": False}

def _ensure_chat_index():
    """Build the search index once, on first use (keeps start-up fast)."""
    if _chat_ready["built"]:
        return
    try:
        import chat
        chat.ensure_tables()
        have = db.query("SELECT count(*) n FROM lesson_fts", one=True)["n"]
        lessons = db.query("SELECT count(*) n FROM lessons", one=True)["n"]
        if have != lessons:
            chat.build_index(verbose=False)
        _chat_ready["built"] = True
    except Exception as e:
        print("chat index error:", e)

@app.post("/api/chat")
async def chat_ask(request: Request):
    """Ask a question; the answer is taken from the student's own notes, with citations."""
    u = current_user(request)
    body = await request.json()
    q = (body.get("question") or "").strip()
    if len(q) < 3:
        return fail("Please type a question.")
    if len(q) > 400:
        return fail("That question is too long — please shorten it.")
    try:
        import chat
        _ensure_chat_index()
        grade = body.get("grade") or u.get("grade")
        subject_id = body.get("subject_id")
        res = chat.ask(q, grade=grade, subject_id=subject_id)
        return jsonok(res)
    except Exception as e:
        return fail("The tutor is unavailable right now (%s)." % e, 503)

@app.get("/api/chat/status")
def chat_status(request: Request):
    u = current_user(request)
    _ensure_chat_index()
    try:
        import chat
        n = db.query("SELECT count(*) n FROM lesson_fts", one=True)["n"]
        return jsonok({"ok": True, "lessons_indexed": n,
                       "provider": (os.environ.get("CHAT_PROVIDER") or "off")})
    except Exception as e:
        return jsonok({"ok": False, "error": str(e)})

@app.get("/api/lesson/{lid}/quiz")
def lesson_quiz(request: Request, lid: int):
    u = current_user(request)
    qs = db.query("SELECT id,prompt,qtype,choices,answer_index,difficulty,concept "
                  "FROM questions WHERE scope='lesson' AND lesson_id=? AND status!='Rejected' "
                  "ORDER BY sort,id", (lid,))
    return jsonok({"lesson_id": lid, "questions": [sanitize_question(q) for q in qs]})

def sanitize_question(q):
    choices = json.loads(q["choices"]) if isinstance(q["choices"], str) else q["choices"]
    return {"id": q["id"], "prompt": q["prompt"], "qtype": q["qtype"],
            "choices": choices, "difficulty": q["difficulty"], "concept": q["concept"]}

@app.post("/api/lesson/{lid}/submit")
async def lesson_submit(request: Request, lid: int):
    u = current_user(request)
    body = await request.json()
    answers = body.get("answers", {}) or {}   # {qid: chosen_index}
    qs = db.query("SELECT id,qtype,choices,answer_index,explanation,prompt FROM questions "
                  "WHERE scope='lesson' AND lesson_id=? AND status!='Rejected'", (lid,))
    total = len(qs)
    correct = 0
    detail = []
    for q in qs:
        sel = answers.get(str(q["id"]))
        sel = int(sel) if sel not in (None, "", -1) else -1
        is_c = (sel == q["answer_index"])
        correct += 1 if is_c else 0
        detail.append({
            "qid": q["id"], "prompt": q["prompt"], "qtype": q["qtype"],
            "choices": json.loads(q["choices"]) if isinstance(q["choices"], str) else q["choices"],
            "correct_index": q["answer_index"], "chosen": sel, "correct": is_c,
            "explanation": q["explanation"],
        })
    percent = round((correct / total) * 100) if total else 0
    passed = 1 if percent >= 80 else 0   # lesson pass threshold 80%
    att_id = db.execute("INSERT INTO attempts(user_id,scope,lesson_id,subject_id,total,correct,percent,passed,answers,started_at,submitted_at) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (u["id"], "lesson", lid, None, total, correct, percent, passed,
                         json.dumps(answers), db.now(), db.now()))
    lp = db.query("SELECT * FROM lesson_progress WHERE user_id=? AND lesson_id=?", (u["id"], lid), one=True)
    attempts = (lp["attempts"] if lp else 0) + 1
    if passed:
        status = "Completed"          # a pass is permanent toward certification
    elif lp and lp["status"] == "Completed":
        status = "Completed"          # do not regress an already-passed lesson
    elif lp and (lp["status"] == "Quiz Failed" or attempts > 1):
        status = "Quiz Failed"        # repeated failure
    else:
        status = "Review Required"    # first failed attempt
    best = max(lp["best_score"] if lp else 0, correct)
    completed_ts = db.now() if passed else (lp["completed_at"] if (lp and lp["completed_at"]) else None)
    db.execute("INSERT OR REPLACE INTO lesson_progress(user_id,lesson_id,status,best_score,best_total,attempts,last_at,completed_at) "
               "VALUES(?,?,?,?,?,?,?,?)",
               (u["id"], lid, status, best, total, attempts, db.now(), completed_ts))
    le = db.query("SELECT unit_id FROM lessons WHERE id=?", (lid,), one=True)
    if le:
        refresh_unit(u["id"], le["unit_id"])
    return jsonok({"total": total, "correct": correct, "percent": percent, "passed": passed,
                   "attempts": attempts, "detail": detail})

def user_notifications(uid):
    rows = db.query("""SELECT n.id, n.title, n.body, n.created_at, COALESCE(un.read,0) AS read
                       FROM notifications n JOIN user_notifications un ON un.notification_id=n.id
                       WHERE un.user_id=? ORDER BY n.id DESC LIMIT 30""", (uid,))
    for r in rows:
        r["read"] = bool(r["read"])
    return rows

@app.get("/api/notifications")
def list_notifications(request: Request):
    u = current_user(request)
    return jsonok({"notifications": user_notifications(u["id"])})

@app.post("/api/notifications/{nid}/read")
def mark_read(request: Request, nid: int):
    u = current_user(request)
    db.execute("UPDATE user_notifications SET read=1 WHERE user_id=? AND notification_id=?", (u["id"], nid))
    return jsonok()

@app.get("/api/flashcards/{lid}")
def flashcards(request: Request, lid: int):
    u = current_user(request)
    fc = db.query("SELECT id,front,back FROM flashcards WHERE lesson_id=? ORDER BY sort,id", (lid,))
    return jsonok({"lesson_id": lid, "flashcards": fc})

# ---------------- final exam ----------------
def _subject_approved_pool(sid):
    return db.query("SELECT id,prompt,qtype,choices,answer_index,explanation FROM questions "
                    "WHERE subject_id=? AND scope='final' AND status!='Rejected' ORDER BY id", (sid,)) or \
           db.query("SELECT id,prompt,qtype,choices,answer_index,explanation FROM questions "
                    "WHERE subject_id=? AND scope='lesson' AND status='Approved' ORDER BY RANDOM() LIMIT 125", (sid,))

@app.get("/api/subject/{sid}/exam")
def get_exam(request: Request, sid: int):
    u = current_user(request)
    s = db.query("SELECT * FROM subjects WHERE id=? AND grade=?", (sid, u["grade"]), one=True)
    if not s:
        return fail("Subject not found", 404)
    sp = db.query("SELECT * FROM subject_progress WHERE user_id=? AND subject_id=?", (u["id"], sid), one=True)
    if not sp or not sp["final_unlocked"]:
        return fail("Complete every unit and lesson of this subject to unlock the final examination.", 403)
    return jsonok({"subject": s["name"], "questions_count": 125})

@app.post("/api/subject/{sid}/exam/questions")
def get_exam_questions(request: Request, sid: int):
    u = current_user(request)
    s = db.query("SELECT * FROM subjects WHERE id=? AND grade=?", (sid, u["grade"]), one=True)
    if not s:
        return fail("Subject not found", 404)
    sp = db.query("SELECT * FROM subject_progress WHERE user_id=? AND subject_id=?", (u["id"], sid), one=True)
    if not sp or not sp["final_unlocked"]:
        return fail("Locked.", 403)
    # prefer reviewed questions, then top up from the generated lesson bank
    pool = db.query("SELECT id,prompt,qtype,choices,answer_index,difficulty,concept FROM questions "
                    "WHERE subject_id=? AND status='Approved' ORDER BY RANDOM()", (sid,))
    if len(pool) < 125:
        extra = db.query("SELECT id,prompt,qtype,choices,answer_index,difficulty,concept FROM questions "
                         "WHERE subject_id=? AND status NOT IN ('Approved','Rejected') ORDER BY RANDOM()", (sid,))
        have = {q["id"] for q in pool}
        pool += [q for q in extra if q["id"] not in have]
    if len(pool) > 125:
        pool = random.sample(pool, 125)
    # freeze the delivered paper so it can be scored against exactly this set
    db.execute("UPDATE exam_sessions SET returned=1 WHERE user_id=? AND subject_id=? AND returned=0", (u["id"], sid))
    session_id = db.execute(
        "INSERT INTO exam_sessions(user_id,subject_id,question_ids,returned,created_at) VALUES(?,?,?,0,?)",
        (u["id"], sid, json.dumps([q["id"] for q in pool]), db.now()))
    return jsonok({"count": len(pool), "session_id": session_id,
                   "questions": [sanitize_question(q) for q in pool]})

@app.post("/api/subject/{sid}/exam/submit")
async def submit_exam(request: Request, sid: int):
    u = current_user(request)
    s = db.query("SELECT * FROM subjects WHERE id=? AND grade=?", (sid, u["grade"]), one=True)
    if not s:
        return fail("Subject not found", 404)
    sp = db.query("SELECT * FROM subject_progress WHERE user_id=? AND subject_id=?", (u["id"], sid), one=True)
    if not sp or not sp["final_unlocked"]:
        return fail("Locked.", 403)
    body = await request.json(); answers = body.get("answers", {}) or {}
    session = None
    if body.get("session_id"):
        session = db.query("SELECT * FROM exam_sessions WHERE id=? AND user_id=? AND subject_id=? AND returned=0",
                           (body["session_id"], u["id"], sid), one=True)
    if not session:                 # recover the newest paper handed to this student
        session = db.query("SELECT * FROM exam_sessions WHERE user_id=? AND subject_id=? AND returned=0 "
                           "ORDER BY id DESC LIMIT 1", (u["id"], sid), one=True)
    if session:
        qids = json.loads(session["question_ids"])
        marks = ",".join("?" * len(qids))
        qs = db.query("SELECT id,answer_index FROM questions WHERE id IN (%s)" % marks, tuple(qids)) if qids else []
        started = session["created_at"]
        db.execute("UPDATE exam_sessions SET returned=1, submitted_at=? WHERE id=?", (db.now(), session["id"]))
    else:                           # paper opened before this change
        qs = db.query("SELECT id,answer_index FROM questions WHERE subject_id=? AND status!='Rejected'", (sid,))
        started = None
    total = len(qs)
    correct = 0
    for q in qs:
        sel = answers.get(str(q["id"]))
        sel = int(sel) if sel not in (None, "", -1) else -1
        if sel == q["answer_index"]:
            correct += 1
    percent = round((correct / total) * 100) if total else 0
    needed = 100 if total >= 125 else max(1, round(total * 0.8))   # 100/125 standard
    passed_cert = correct >= needed
    db.execute("INSERT INTO attempts(user_id,scope,subject_id,total,correct,percent,passed,answers,started_at,submitted_at) "
               "VALUES(?,?,?,?,?,?,?,?,?,?)",
               (u["id"], "final", sid, total, correct, percent, 1 if passed_cert else 0,
                json.dumps(answers), started, db.now()))
    if passed_cert:
        existing = db.query("SELECT id FROM certificates WHERE user_id=? AND subject_id=?", (u["id"], sid), one=True)
        if not existing:
            cert_id = issue_certificate(u["id"], sid, s, correct, total)
        else:
            cert_id = db.query("SELECT cert_id FROM certificates WHERE user_id=? AND subject_id=?", (u["id"], sid), one=True)["cert_id"]
        db.execute("UPDATE subject_progress SET final_passed=1,best_exam=?,best_exam_total=?,status='Exam Passed' WHERE user_id=? AND subject_id=?",
                   (correct, total, u["id"], sid))
        notify_issue(u["id"], s)
        return jsonok({"passed_cert": True, "correct": correct, "total": total, "percent": percent,
                       "needed": needed, "cert_id": cert_id})
    db.execute("UPDATE subject_progress SET best_exam=?,best_exam_total=? WHERE user_id=? AND subject_id=?",
               (max(sp["best_exam"], correct) if sp else correct, total, u["id"], sid))
    return jsonok({"passed_cert": False, "correct": correct, "total": total, "percent": percent,
                   "needed": needed, "message": "You need at least %d of %d to earn the certificate." % (needed, total)})

def issue_certificate(uid, sid, s, correct, total):
    u = db.query("SELECT * FROM users WHERE id=?", (uid,), one=True)
    cert_id = "CERT-{}-{:05d}".format(datetime.date.today().year, random.randint(0, 99999))
    db.execute("INSERT INTO certificates(cert_id,user_id,subject_id,grade,full_name,exam_score,exam_total,issued_at) "
               "VALUES(?,?,?,?,?,?,?,?)", (cert_id, uid, sid, s["grade"], u["full_name"], correct, total, db.now()))
    return cert_id

def notify_issue(uid, s):
    nbody = ("Congratulations! You completed the final examination for {} and earned your "
             "certificate. View it from your dashboard.").format(s["name"])
    nid = db.execute(
        "INSERT INTO notifications(audience,audience_value,title,body,created_by,created_at) "
        "VALUES(?,?,?,?,0,?)",
        ("one", str(uid), "Certificate ready", nbody, db.now()))
    db.execute("INSERT OR IGNORE INTO user_notifications(user_id,notification_id) VALUES(?,?)", (uid, nid))

@app.get("/api/certificates")
def my_certs(request: Request):
    u = current_user(request)
    rows = db.query("""SELECT c.*, s.name sname FROM certificates c JOIN subjects s ON c.subject_id=s.id
                       WHERE c.user_id=? ORDER BY c.issued_at DESC""", (u["id"],))
    return jsonok({"certificates": rows})

# ---------------- certificate verification (public) ----------------
@app.get("/api/certificate/{cert_id}")
def cert_lookup(request: Request, cert_id: str):
    c = db.query("SELECT c.cert_id,c.full_name,c.grade,c.exam_score,c.exam_total,c.issued_at,s.name sname "
                 "FROM certificates c JOIN subjects s ON c.subject_id=s.id WHERE c.cert_id=?", (cert_id,), one=True)
    if not c:
        return jsonok({"valid": False})
    return jsonok({"valid": True, "certificate": c})

# ---------------- static SPA ----------------
@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))
@app.get("/app")
def index2():
    return FileResponse(os.path.join(STATIC, "index.html"))

# ---------------- unit PDF download ----------------
@app.get("/api/unit/{uid}/pdf")
def unit_pdf(request: Request, uid: int):
    u = current_user(request)
    unit = db.query("SELECT * FROM units WHERE id=?", (uid,), one=True)
    if not unit:
        return fail("Unit not found", 404)
    lessons = db.query("SELECT title,content_html FROM lessons WHERE unit_id=? ORDER BY number", (uid,))
    html = build_unit_pdf_html(unit, lessons)
    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html).write_pdf()
        fname = "Unit{}-{}.pdf".format(unit["number"], re_slug(unit["title"]))
        return Response(content=pdf_bytes, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{fname}"'})
    except Exception as e:
        return fail("PDF generation error: " + str(e), 500)

import re
def re_slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "-", s)[:40].strip("-")

def build_unit_pdf_html(unit, lessons):
    body = "".join(f"<h2>{l['title']}</h2>{l['content_html']}" for l in lessons)
    return f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
    <style>body{{font-family:Georgia,serif;font-size:11pt;line-height:1.55;margin:24pt}}
    h1{{color:#0f3d6b}} h2{{color:#1b6aa8;border-bottom:2px solid #cfe0ef;padding-bottom:3px}}
    table{{border-collapse:collapse;width:100%}} td,th{{border:1px solid #ccc;padding:5px}}
    blockquote{{background:#f4f7fa;border-left:5px solid #f0b429;margin:8px 0;padding:8px 12px}}
    .note{{color:#333}}</style></head><body>
    <h1>{unit['title']}</h1>
    {body}
    </body></html>"""

app.mount("/static", StaticFiles(directory=STATIC), name="static")
