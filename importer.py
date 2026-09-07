"""Import existing markdown study notes into the platform as Grade -> Subject -> Unit -> Lesson.

Each *_notes folder maps to a (grade, subject). Each unitN.md file is one Unit whose
'## Section' headings become the lessons. Original educational content is preserved.

Usage:
    python3 importer.py --dry            # show what would be imported
    python3 importer.py                  # import all discovered subjects
    python3 importer.py --only 11        # only grade 11
"""
import os, re, argparse
import markdown as mdlib
import db

_NAME_TO_CODE = {"Chemistry": "chem", "Biology": "bio", "Physics": "phys",
                 "English": "english", "Mathematics": "math", "Agriculture": "agric"}
_SUBJ_NAME = {v: k for k, v in _NAME_TO_CODE.items()}
_PREFIX_NAME = {"chem": "Chemistry", "bio": "Biology", "phys": "Physics",
                "engl": "English", "english": "English", "math": "Mathematics",
                "agri": "Agriculture", "agric": "Agriculture"}
_CANON = {"bio": "Biology", "biology": "Biology", "phys": "Physics", "physics": "Physics",
          "chem": "Chemistry", "chemistry": "Chemistry", "engl": "English",
          "english": "English", "math": "Mathematics", "mathematics": "Mathematics",
          "agri": "Agriculture", "agric": "Agriculture", "agriculture": "Agriculture"}

MD = mdlib.Markdown(extensions=["tables", "fenced_code", "sane_lists"])


def render(md_text):
    MD.reset()
    return MD.convert(md_text or "")


def _resolve(folder, name):
    """Return (grade, code, canonical_name). (0,'','') if not resolvable."""
    m = re.match(r"([a-z]+)(\d+)_notes$", name)
    if m:
        code, grade = m.group(1), int(m.group(2))
        return grade, code, _PREFIX_NAME.get(code, name[:-6].title())
    combined = [f for f in os.listdir(folder) if "Complete_Notes.md" in f]
    gm = re.search(r"Grade\s*(\d+)", combined[0]) if combined else None
    if not gm:
        for f in os.listdir(folder):
            gm = re.search(r"Grade\s*(\d+)", f)
            if gm:
                break
    if not gm:
        return 0, "", ""
    grade = int(gm.group(1))
    base = name.replace("_notes", "").replace("_", " ").strip().lower()
    canonical = _CANON.get(base, "")
    if not canonical:
        return 0, "", ""
    return grade, _NAME_TO_CODE[canonical], canonical


def discover(root):
    out = []
    for name in sorted(os.listdir(root)):
        folder = os.path.join(root, name)
        if not os.path.isdir(folder) or not name.endswith("_notes"):
            continue
        grade, code, canonical = _resolve(folder, name)
        if grade == 0:
            continue
        out.append((folder, grade, code, canonical))
    return out


def parse_unit_file(path):
    """Return (unit_title, lessons) where lessons = list[(title, markdown_body)]."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    lines = text.split("\n")
    unit_title = ""
    lessons = []
    cur_title, cur = None, []
    for raw in lines:
        s = raw.rstrip()
        m = re.match(r"^# (.*)", s)
        if m and not unit_title:
            unit_title = m.group(1).strip()
            continue
        m2 = re.match(r"^## (.*)", s)
        if m2:
            if cur_title:
                lessons.append((cur_title, "\n".join(cur).strip()))
            cur_title = m2.group(1).strip()
            cur = []
        else:
            cur.append(s)
    if cur_title and "\n".join(cur).strip():
        lessons.append((cur_title, "\n".join(cur).strip()))
    if not unit_title:
        unit_title = os.path.basename(path).replace(".md", "")
    return unit_title, lessons


def _lesson_key(title):
    m = re.search(r"(\d+)\.(\d+)", title)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m2 = re.match(r"\s*(\d+)[.)\s]", title)
    if m2:
        return (int(m2.group(1)), 0)
    return (9999, 0)


def import_subject_folder(folder, grade, code, name, dry=False, log=print):
    files = [f for f in os.listdir(folder) if re.match(r"^unit\d+\.md$", f)]
    files.sort(key=lambda f: int(re.search(r"\d+", f).group()))
    if not files:
        return None
    log(f"Grade {grade}  {name}  ({code})  ->  {len(files)} unit files")
    if dry:
        return (grade, code, name, len(files))
    row = db.query("SELECT id FROM subjects WHERE grade=? AND code=?", (grade, code), one=True)
    if row:
        subject_id = row["id"]
        db.execute("UPDATE subjects SET name=?, description=? WHERE id=?",
                   (name, f"Grade {grade} {name} — full textbook study notes.", subject_id))
        # clear old content for idempotent re-import
        db.execute("DELETE FROM units WHERE subject_id=?", (subject_id,))
        db.execute("DELETE FROM questions WHERE subject_id=?", (subject_id,))
        db.execute("DELETE FROM flashcards WHERE lesson_id IN (SELECT id FROM lessons WHERE unit_id IN (SELECT id FROM units WHERE subject_id=?))", (subject_id,))
        db.execute("DELETE FROM lessons WHERE unit_id IN (SELECT id FROM units WHERE subject_id=?)", (subject_id,))
        db.execute("DELETE FROM unit_progress WHERE unit_id IN (SELECT id FROM units WHERE subject_id=?)", (subject_id,))
        db.execute("DELETE FROM subject_progress WHERE subject_id=?", (subject_id,))
        db.execute("DELETE FROM lesson_progress WHERE lesson_id IN (SELECT id FROM lessons WHERE unit_id IN (SELECT id FROM units WHERE subject_id=?))", (subject_id,))
    else:
        subject_id = db.execute(
            "INSERT INTO subjects(grade,code,name,description,sort) VALUES(?,?,?,?,?)",
            (grade, code, name, f"Grade {grade} {name} — full textbook study notes.", 0))

    unit_no = 0
    lesson_total = 0
    for fname in files:
        unit_no += 1
        unit_title, lessons = parse_unit_file(os.path.join(folder, fname))
        unit_title = re.sub(r"^Unit\s*\d*\s*[:.\-]?\s*", "", unit_title).strip() or f"Unit {unit_no}"
        unit_title = f"Unit {unit_no} — {unit_title}"
        unit_id = db.execute("INSERT INTO units(subject_id,number,title,sort) VALUES(?,?,?,?)",
                             (subject_id, unit_no, unit_title, unit_no))
        # order lessons by natural key; but keep file order (subsections already ordered). Keep as read.
        for ln, (ltitle, body) in enumerate(lessons, start=1):
            if not body.strip():
                continue
            db.execute(
                "INSERT INTO lessons(unit_id,number,title,content_md,content_html,sort) VALUES(?,?,?,?,?,?)",
                (unit_id, ln, ltitle, body, render(body), ln))
            lesson_total += 1
    log(f"     -> {unit_no} units, {lesson_total} lessons")
    return (grade, code, name, unit_no)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/home/user")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--only", default=None, help="grades, comma separated e.g. 11,9,10")
    args = ap.parse_args()
    db.init_db()
    entries = discover(args.root)
    only = set(int(x) for x in args.only.split(",")) if args.only else None
    print(f"Discovered {len(entries)} subject folders")
    done = 0
    for folder, grade, code, name in entries:
        if only and grade not in only:
            continue
        r = import_subject_folder(folder, grade, code, name, dry=args.dry)
        if r:
            done += 1
    print(f"Imported {done} subjects (dry={args.dry}).")


if __name__ == "__main__":
    main()
