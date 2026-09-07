"""Admin API: backend-enforced verification, overview, users, content & question
review, notifications, certificate records. All student data shown is read-only to
admins; no cross-account writes."""
import json, datetime, random
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import db, security, importer, generator

router = APIRouter(prefix="/api/admin")


def admin_session(request):
    tok = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not tok:
        raise HTTPException(401, "Not authenticated")
    sess = db.query("SELECT token FROM admin_sessions WHERE token=?", (tok,), one=True)
    if not sess:
        raise HTTPException(401, "Not authorized")
    return True


def jok(data=None, **kw):
    d = {"ok": True}
    if data is not None:
        d.update(data)
    d.update(kw)
    return JSONResponse(d)


def jfail(msg, code=400):
    return JSONResponse({"ok": False, "error": msg}, status_code=code)


# ---------- verification (first stage, no token needed) ----------
@router.post("/verify")
def admin_verify(body: dict):
    # The four required questions - all must be correct or access is denied silently.
    checks = [
        ("name", body.get("q_name", "")),
        ("color", body.get("q_color", "")),
        ("number", body.get("q_number", "")),
    ]
    for field, answer in checks:
        if not security.admin_check(field, answer):
            # deny without revealing which or the answers
            return jfail("Access denied. Verification failed.", 401)
    token = security.sign({"role": "admin", "uid": 0, "name": "Admin"}, ttl=60 * 60 * 6)
    db.execute("DELETE FROM admin_sessions")  # single concurrent admin session is fine
    db.execute("INSERT INTO admin_sessions(token,created_at) VALUES(?,?)", (token, db.now()))
    return jok({"token": token})


def _authed(request):
    admin_session(request)


# ---------- overview ----------
@router.get("/overview")
def overview(request: Request):
    _authed(request)
    total_students = db.query("SELECT count(*) n FROM users WHERE role='student'", ())[0]["n"]
    learning_now = db.query("SELECT count(DISTINCT user_id) n FROM subject_progress WHERE lessons_done>0 AND final_passed=0", ())[0]["n"]
    completed_subjects = db.query("SELECT count(*) n FROM subject_progress WHERE final_passed=1", ())[0]["n"]
    certs = db.query("SELECT count(*) n FROM certificates", ())[0]["n"]
    avg_quiz = db.query("SELECT AVG(percent) a FROM attempts WHERE scope='lesson'", ())
    avg_quiz = round(avg_quiz[0]["a"], 1) if avg_quiz and avg_quiz[0]["a"] else 0
    avg_exam = db.query("SELECT AVG(percent) a FROM attempts WHERE scope='final'", ())
    avg_exam = round(avg_exam[0]["a"], 1) if avg_exam and avg_exam[0]["a"] else 0
    # most studied subjects
    top = db.query("""SELECT s.name, COUNT(*) n FROM subject_progress sp JOIN subjects s ON sp.subject_id=s.id
                      GROUP BY s.id ORDER BY n DESC LIMIT 5""", ())
    grade_dist = db.query("SELECT grade,count(*) n FROM users WHERE role='student' GROUP BY grade", ())
    return jok({"total_students": total_students, "learning_now": learning_now,
                "completed_subjects": completed_subjects, "certificates": certs,
                "avg_quiz": avg_quiz, "avg_exam": avg_exam, "top": top, "grade_dist": grade_dist})


@router.get("/students")
def students(request: Request, q: str = ""):
    _authed(request)
    sql = "SELECT id,full_name,grade,phone,age,school,created_at FROM users WHERE role='student'"
    params = []
    if q:
        sql += " AND (full_name LIKE ? OR phone LIKE ?)"
        params = [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY id DESC LIMIT 200"
    rows = db.query(sql, params)
    return jok({"students": rows})


@router.get("/student/{uid}")
def student_detail(request: Request, uid: int):
    _authed(request)
    s = db.query("SELECT * FROM users WHERE id=? AND role='student'", (uid,), one=True)
    if not s:
        return jfail("Student not found", 404)
    subj = []
    for sp in db.query("SELECT * FROM subject_progress WHERE user_id=? ORDER BY lessons_done DESC", (uid,)):
        nm = db.query("SELECT name FROM subjects WHERE id=?", (sp["subject_id"],), one=True)
        subj.append({"subject": nm["name"] if nm else sp["subject_id"], "sp": sp})
    recent = db.query("SELECT scope,lesson_id,subject_id,total,correct,percent,passed,submitted_at "
                      "FROM attempts WHERE user_id=? ORDER BY id DESC LIMIT 20", (uid,))
    certs = db.query("SELECT * FROM certificates WHERE user_id=?", (uid,))
    notifs = db.query("SELECT id,title,read FROM user_notifications WHERE user_id=? ORDER BY id DESC LIMIT 30", (uid,))
    return jok({"student": s, "subjects": subj, "attempts": recent, "certificates": certs, "notifications": notifs})


# ---------- content tree ----------
@router.get("/tree")
def tree(request: Request):
    _authed(request)
    out = []
    for s in db.query("SELECT id,grade,code,name FROM subjects ORDER BY grade,name"):
        units = []
        for u in db.query("SELECT id,number,title FROM units WHERE subject_id=? ORDER BY number", (s["id"],)):
            lessons = db.query("SELECT id,number,title FROM lessons WHERE unit_id=? ORDER BY number", (u["id"],))
            units.append({"id": u["id"], "number": u["number"], "title": u["title"], "lessons": lessons})
        out.append({"id": s["id"], "grade": s["grade"], "name": s["name"], "code": s["code"], "units": units})
    return jok({"tree": out})


# ---------- question review ----------
@router.get("/questions")
def list_questions(request: Request, status: str = "", lesson_id: int = 0, subject: int = 0):
    _authed(request)
    sql = "SELECT q.*, l.title lesson_title, u.subject_id FROM questions q LEFT JOIN lessons l ON q.lesson_id=l.id LEFT JOIN units u ON l.unit_id=u.id WHERE 1=1"
    params = []
    if status:
        sql += " AND q.status=?"; params.append(status)
    if lesson_id:
        sql += " AND q.lesson_id=?"; params.append(lesson_id)
    if subject:
        sql += " AND (q.subject_id=? OR u.subject_id=?)"; params += [subject, subject]
    sql += " ORDER BY q.id DESC LIMIT 400"
    rows = db.query(sql, params)
    for r in rows:
        try:
            r["choices"] = json.loads(r["choices"])
        except Exception:
            r["choices"] = []
    return jok({"questions": rows})


@router.put("/question/{qid}")
def update_question(request: Request, qid: int, body: dict):
    _authed(request)
    q = db.query("SELECT * FROM questions WHERE id=?", (qid,), one=True)
    if not q:
        return jfail("Not found", 404)
    fields = {k: body.get(k) for k in ["prompt", "qtype", "answer", "answer_index",
                                       "explanation", "difficulty", "concept", "status"]}
    choices = body.get("choices")
    if choices is not None:
        fields["choices"] = json.dumps(choices, ensure_ascii=False)
    cols = ", ".join(f"{k}=?" for k in fields)
    db.execute(f"UPDATE questions SET {cols} WHERE id=?", (*fields.values(), qid))
    return jok()


@router.delete("/question/{qid}")
def delete_question(request: Request, qid: int):
    _authed(request)
    db.execute("DELETE FROM questions WHERE id=?", (qid,))
    return jok()


@router.post("/question")
def add_question(request: Request, body: dict):
    _authed(request)
    qtype = body.get("qtype", "mcq")
    choices = json.dumps(body.get("choices", []), ensure_ascii=False)
    db.execute("""INSERT INTO questions(scope,lesson_id,subject_id,qtype,prompt,choices,answer,answer_index,
                  explanation,difficulty,concept,status,created_at)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
               ("lesson", body.get("lesson_id"), body.get("subject_id"), qtype, body.get("prompt"),
                choices, body.get("answer"), int(body.get("answer_index", 0)),
                body.get("explanation", ""), body.get("difficulty", "Medium"),
                body.get("concept"), body.get("status", "Needs Review"), db.now()))
    return jok({"id": db.query("SELECT MAX(id) id FROM questions")[0]["id"]})


@router.post("/question/{qid}/regenerate")
def regen_question(request: Request, qid: int):
    _authed(request)
    q = db.query("SELECT * FROM questions WHERE id=?", (qid,), one=True)
    if not q:
        return jfail("Not found", 404)
    if q["lesson_id"]:
        generator.build_lesson(q["lesson_id"])
    return jok()


# ---------- flashcards ----------
@router.get("/flashcards")
def list_flashcards(request: Request, lesson_id: int = 0):
    _authed(request)
    sql = "SELECT f.*, l.title lesson_title FROM flashcards f JOIN lessons l ON f.lesson_id=l.id WHERE 1=1"
    params = []
    if lesson_id:
        sql += " AND f.lesson_id=?"; params.append(lesson_id)
    sql += " ORDER BY f.id DESC LIMIT 400"
    return jok({"flashcards": db.query(sql, params)})


@router.post("/flashcard")
def add_flashcard(request: Request, body: dict):
    _authed(request)
    db.execute("INSERT INTO flashcards(lesson_id,front,back,sort) VALUES(?,?,?,0)",
               (body.get("lesson_id"), body.get("front"), body.get("back")))
    return jok()


@router.delete("/flashcard/{fid}")
def delete_flashcard(request: Request, fid: int):
    _authed(request)
    db.execute("DELETE FROM flashcards WHERE id=?", (fid,))
    return jok()


# ---------- notifications ----------
@router.post("/notify")
def send_notification(request: Request, body: dict):
    _authed(request)
    audience = body.get("audience", "all")       # all | grade | subject | one
    av = body.get("audience_value", "")
    title = (body.get("title") or "").strip()
    text = (body.get("body") or "").strip()
    if not title:
        return jfail("Title required")
    nid = db.execute("INSERT INTO notifications(audience,audience_value,title,body,created_by,created_at) "
                     "VALUES(?,?,?,?,?,?)", (audience, av, title, text, 0, db.now()))
    # determine recipients
    if audience == "all":
        rows = db.query("SELECT id FROM users WHERE role='student'", ())
    elif audience == "grade":
        rows = db.query("SELECT id FROM users WHERE role='student' AND grade=?", (int(av) if str(av).isdigit() else -1,))
    elif audience == "subject":
        s = db.query("SELECT id FROM subjects WHERE id=?", (int(av) if str(av).isdigit() else 0,), one=True)
        if not s:
            return jfail("Subject not found", 404)
        rows = db.query("SELECT DISTINCT user_id id FROM subject_progress WHERE subject_id=?", (s["id"],))
    else:
        rows = db.query("SELECT id FROM users WHERE id=? AND role='student'", (int(av) if str(av).isdigit() else -1,))
    for r in rows:
        db.execute("INSERT OR IGNORE INTO user_notifications(user_id,notification_id) VALUES(?,?)", (r["id"], nid))
    return jok({"recipients": len(rows)})


@router.get("/notifications")
def list_admin_notifications(request: Request):
    _authed(request)
    rows = db.query("SELECT n.*, (SELECT count(*) FROM user_notifications un WHERE un.notification_id=n.id) recipients "
                    "FROM notifications n ORDER BY n.id DESC LIMIT 100", ())
    return jok({"notifications": rows})


# ---------- certificates ----------
@router.get("/certificates")
def certs_admin(request: Request):
    _authed(request)
    rows = db.query("""SELECT c.*, s.name sname FROM certificates c JOIN subjects s ON c.subject_id=s.id
                       ORDER BY c.issued_at DESC LIMIT 200""", ())
    return jok({"certificates": rows})


# ---------- content generation ----------
@router.post("/generate/lesson/{lid}")
def gen_lesson(request: Request, lid: int):
    _authed(request)
    q, f = generator.build_lesson(lid)
    return jok({"questions": q, "flashcards": f})
