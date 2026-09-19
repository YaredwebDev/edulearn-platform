"""Turn a folder of structured notes files into a complete lesson-by-lesson course.

One command does the whole job:
    1. backs up the current database
    2. imports every notes file  (Grade -> Subject -> Unit -> Lesson, content preserved)
    3. builds the assessment bank: 10 questions per lesson + flashcards
    4. prints a report of units / lessons / questions per subject

Usage
-----
    python3 build_course.py --notes /home/user/uploads
    python3 build_course.py --notes DIR --only 9,10        # just these grades
    python3 build_course.py --notes DIR --merge            # keep existing lessons
    python3 build_course.py --notes DIR --dry              # preview, write nothing
    python3 build_course.py --questions-only               # regenerate the bank only

The DB is chosen by the EDULEARN_DB environment variable (default: ./platform.db).
"""
import argparse, os, shutil, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db  # noqa: E402

EXTS = (".html", ".htm", ".md", ".txt", ".zip", ".docx", ".pdf")


def backup_db():
    path = db.DB_PATH
    if not os.path.exists(path):
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = "%s.backup-%s" % (path, stamp)
    shutil.copy2(path, dest)
    return dest


SKIP_DIRS = {".git", "docs", "__pycache__", ".venv", "node_modules", ".cache", "static", ".arena"}


def looks_like_notes(name):
    """True only for real study-notes files, so running against the whole repo is safe.

    Accepts names that carry a subject word and/or a grade, or say 'notes'.
    """
    low = name.lower()
    if any(k in low for k in ("notes", "structured", "textbook", "handout", "summary")):
        return True
    subject = any(k in low for k in ("bio", "chem", "phys", "math", "english", "engl",
                                     "agric", "geo", "hist", "civic", "it"))
    grade = bool(__import__("re").search(r"(grade|gr)\s*[_\-]?\d", low))
    return subject and grade


def collect_files(folder):
    """Notes files in the folder, searched recursively but never picking up the app itself."""
    found = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for f in sorted(files):
            if f.lower().endswith(EXTS) and not f.startswith(".") and looks_like_notes(f):
                found.append(os.path.join(root, f))
    return found


def import_notes(folder, only=None, replace=True, dry=False):
    files = collect_files(folder)
    if not files:
        print("No notes files found in %s (expected .html/.htm/.md/.txt)" % folder)
        return []
    import notes_import
    summaries = []
    for path in files:
        name, ext = os.path.splitext(os.path.basename(path))
        if ext.lower() in (".md", ".txt"):          # plain markdown notes
            summaries.append(notes_import.import_document(path, replace=replace, dry=dry))
            continue
        grade, _code, _name = notes_import.guess_subject(path)
        if only and grade not in only:
            continue
        summaries.append(notes_import.import_document(path, replace=replace, dry=dry))
    return summaries


def report():
    print("\n" + "=" * 78)
    print("%-6s %-12s %-7s %-8s %-10s %-9s" % ("grade", "subject", "units", "lessons", "questions", "flashcards"))
    print("-" * 78)
    total_l = total_q = 0
    for s in db.query("SELECT id, grade, code, name FROM subjects ORDER BY grade, name"):
        units = db.query("SELECT count(*) n FROM units WHERE subject_id=?", (s["id"],), one=True)["n"]
        lessons = db.query("""SELECT count(*) n FROM lessons l JOIN units u ON l.unit_id=u.id
                              WHERE u.subject_id=?""", (s["id"],), one=True)["n"]
        questions = db.query("""SELECT count(*) n FROM questions q JOIN lessons l ON q.lesson_id=l.id
                                JOIN units u ON l.unit_id=u.id WHERE u.subject_id=?""", (s["id"],), one=True)["n"]
        cards = db.query("""SELECT count(*) n FROM flashcards f JOIN lessons l ON f.lesson_id=l.id
                            JOIN units u ON l.unit_id=u.id WHERE u.subject_id=?""", (s["id"],), one=True)["n"]
        total_l += lessons
        total_q += questions
        print("%-6s %-12s %-7d %-8d %-10d %-9d" % (s["grade"], s["name"][:12], units, lessons, questions, cards))
    print("-" * 78)
    print("TOTAL lessons: %d   |   TOTAL questions: %d" % (total_l, total_q))
    thin = db.query("""SELECT l.id, l.title, count(q.id) n FROM lessons l
                       LEFT JOIN questions q ON q.lesson_id=l.id AND q.scope='lesson'
                       GROUP BY l.id HAVING n < 10 ORDER BY n LIMIT 25""")
    if thin:
        print("\nLessons with fewer than 10 questions (author more in the admin panel):")
        for t in thin:
            print("  %5d  %-60s %d" % (t["id"], t["title"][:60], t["n"]))
    else:
        print("\nEvery lesson has a full set of 10 assessment questions. ✅")
    print("=" * 78)


def main():
    ap = argparse.ArgumentParser(description="Build a complete lesson-by-lesson course from notes files.")
    ap.add_argument("--notes", help="folder containing the notes files")
    ap.add_argument("--only", default="", help="comma separated grades, e.g. 9,10")
    ap.add_argument("--merge", action="store_true", help="keep existing lessons instead of replacing them")
    ap.add_argument("--dry", action="store_true", help="preview only, nothing is written")
    ap.add_argument("--questions-only", action="store_true", help="skip the import, rebuild the question bank")
    ap.add_argument("--n", type=int, default=10, help="questions per lesson (default 10)")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    db.init_db()
    print("Database:", db.DB_PATH)
    only = [int(x) for x in __import__("re").findall(r"\d+", args.only)] or None

    if not args.no_backup and not args.dry:
        b = backup_db()
        print("Backup:", b)

    if not args.questions_only:
        if not args.notes:
            print("Nothing to import: pass --notes DIR (or --questions-only)")
            return
        print("\n[1/2] Importing notes from %s" % args.notes)
        res = import_notes(args.notes, only=only, replace=not args.merge, dry=args.dry)
        print("      files: %d | units: %d | lessons: %d"
              % (len(res), sum(r.get("units", 0) for r in res), sum(r.get("lessons", 0) for r in res)))
        for r in res:
            if not r.get("ok"):
                print("      !! skipped %s (%s)" % (r.get("file"), r.get("error")))
        if args.dry:
            print("(dry run - nothing written)")
            return

    print("\n[2/2] Building the assessment bank (%d questions per lesson)" % args.n)
    import qbank
    st = qbank.build_scope(n=args.n)
    print("      lessons: %d | complete: %d | short: %d | new questions: %d | flashcards: %d"
          % (st["lessons"], st["full"], st["short"], st["questions"], st["flashcards"]))
    print("      flashcard text repaired:", qbank.scrub_flashcards())
    report()


if __name__ == "__main__":
    main()
