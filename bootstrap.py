"""One-time setup: build the SQLite database from the bundled study notes if empty.
Run:  python bootstrap.py
This makes the package self-contained so a fresh host can rebuild data."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import db

db.init_db()
n = db.query("SELECT count(*) n FROM subjects")[0]["n"]
q = db.query("SELECT count(*) n FROM questions")[0]["n"]
print(f"subjects={n} questions={q}")

if n == 0 and os.path.isdir("content"):
    import importer
    seen = 0
    for folder, grade, code, name in importer.discover("content"):
        r = importer.import_subject_folder(folder, grade, code, name)
        if r:
            seen += 1
    print(f"Imported {seen} subjects from content/")
    n = db.query("SELECT count(*) n FROM subjects")[0]["n"]

if q == 0:
    try:
        import author_chem   # seeds the Grade 11 Chemistry assessment bank
    except Exception as e:
        print("author_chem skipped:", e)

print("READY")
