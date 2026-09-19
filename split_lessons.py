"""Split mega-lessons into real lesson-by-lesson content, aligned to the textbook.

Some lessons in the database carry a whole chapter's worth of material under one heading
(for example "6.1 Ecology" holds definitions, biotic/abiotic factors, ecological levels,
ecosystems, biomes and succession - six separate topics in the official textbook).

This tool breaks such lessons at their `### x.y.z` sub-headings so each textbook topic
becomes its own lesson with its own flashcards and 10-question assessment. The original
lesson row is reused for the first part, so student progress and attempt history survive;
the remaining parts are inserted as new lessons and every lesson in the unit is renumbered
sequentially.

    python3 split_lessons.py --report                 # show what would be split
    python3 split_lessons.py --min-chars 6000 --dry   # preview the new structure
    python3 split_lessons.py --min-chars 6000         # apply
    python3 split_lessons.py --lesson 215             # one lesson only
"""
import argparse, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db  # noqa: E402

try:
    import markdown as mdlib
    MD = mdlib.Markdown(extensions=["tables", "fenced_code", "sane_lists"])
except Exception:                                     # graceful fallback
    MD = None


def render(md_text):
    if MD is None:
        return "<p>" + re.sub(r"\n{2,}", "</p><p>", md_text or "") + "</p>"
    MD.reset()
    return MD.convert(md_text or "")


NUM_PREFIX = re.compile(r"^\s*\d+(?:\.\d+)*\s*[.)]?\s+")


def strip_number(title):
    """'6.1.1 Definitions of Common Ecological Terms' -> 'Definitions of Common Ecological Terms'."""
    return NUM_PREFIX.sub("", (title or "").strip()).strip() or (title or "").strip()


def split_markdown(md, min_part=350):
    """Break a lesson body at '### ' headings.

    Returns [(title, body_md)]. Text before the first sub-heading becomes the first part
    (kept when substantial, otherwise merged into the first topic).
    """
    lines = (md or "").split("\n")
    parts = []            # (title, [lines])
    prefix = []
    cur_title, cur = None, None
    for line in lines:
        m = re.match(r"^\s*###\s+(.*)$", line)
        if m:
            if cur_title is not None:
                parts.append((cur_title, cur))
            cur_title, cur = m.group(1).strip(), []
        elif cur is None:
            prefix.append(line)
        else:
            cur.append(line)
    if cur_title is not None:
        parts.append((cur_title, cur))

    if len(parts) < 2:                     # nothing to split
        return []

    pre = "\n".join(prefix).strip()
    out = []
    if pre and len(pre) >= min_part:
        out.append((None, pre))            # an introductory part
    for title, body in parts:
        text = "\n".join(body).strip()
        if not text:
            continue
        out.append((title, text))

    if pre and len(pre) < min_part and out:      # fold a thin intro into the first topic
        first_title, first_body = out[0]
        out[0] = (first_title, (pre + "\n\n" + first_body).strip())

    # merge very small parts into the previous one so no lesson is a stub
    merged = []
    for title, body in out:
        if merged and len(body) < min_part:
            pt, pb = merged[-1]
            merged[-1] = (pt, (pb + "\n\n" + ("### " + title + "\n\n" if title else "") + body).strip())
        else:
            merged.append((title, body))
    return merged if len(merged) >= 2 else []


def plan_lesson(lesson, min_chars):
    if (len(lesson["content_md"] or "") < min_chars):
        return None
    parts = split_markdown(lesson["content_md"])
    return parts or None


def report(min_chars, lesson_id=None, dry=False, verbose=True):
    where = "WHERE l.id=?" if lesson_id else ""
    rows = db.query("""SELECT l.id, l.number, l.title, l.content_md, l.unit_id,
                              u.number un, u.title ut, s.name sname, s.grade
                       FROM lessons l JOIN units u ON l.unit_id=u.id JOIN subjects s ON u.subject_id=s.id
                       %s ORDER BY u.subject_id, u.number, l.number""" % where,
                    (lesson_id,) if lesson_id else ())
    total_new = 0
    for l in rows:
        parts = plan_lesson(l, min_chars)
        if not parts:
            continue
        unit_lessons = db.query("SELECT count(*) n FROM lessons WHERE unit_id=?", (l["unit_id"],), one=True)["n"]
        if verbose:
            print("\n%s Grade %s · %s" % (l["sname"], l["grade"], l["ut"][:60]))
            print("  lesson %d '%s' (%d chars)  ->  %d lessons   [unit currently has %d lessons]"
                  % (l["id"], l["title"][:50], len(l["content_md"]), len(parts), unit_lessons))
            for i, (title, body) in enumerate(parts, 1):
                print("      %d. %-58s %5d chars" % (i, strip_number(title or "(introduction)")[:58], len(body)))
        total_new += len(parts) - 1
    print("\nLessons that would be split: %d | new lesson rows: %d"
          % (sum(1 for l in rows if plan_lesson(l, min_chars)), total_new))
    return total_new


def apply_split(lesson_id, min_chars, dry=False):
    """Split one lesson in place.

    The original lesson row becomes the first part so student progress and attempt
    history survive; the remaining parts are inserted right after it and every lesson
    in the unit is renumbered sequentially (numbers *and* titles).
    """
    l = db.query("SELECT * FROM lessons WHERE id=?", (lesson_id,), one=True)
    if not l:
        return 0
    parts = plan_lesson(l, min_chars)
    if not parts:
        return 0
    unit = db.query("SELECT number FROM units WHERE id=?", (l["unit_id"],), one=True)
    un = unit["number"]

    # 1. materialise the parts: first reuses the original row, the rest are new rows
    part_ids = []
    for i, (title, body) in enumerate(parts):
        clean = strip_number(title) if title else "Introduction"
        if i == 0:
            db.execute("UPDATE lessons SET title=?, content_md=?, content_html=? WHERE id=?",
                       (clean, body, render(body), l["id"]))
            db.execute("DELETE FROM questions WHERE scope='lesson' AND lesson_id=? AND status!='Approved'", (l["id"],))
            part_ids.append(l["id"])
        else:
            new_id = db.execute("""INSERT INTO lessons(unit_id,number,title,content_md,content_html,sort)
                                   VALUES(?,?,?,?,?,?)""",
                                (l["unit_id"], 10000 + i, clean, body, render(body), 10000 + i))
            part_ids.append(new_id)

    # 2. rebuild the unit order, placing the parts where the original lesson sat
    ordered = db.query("SELECT id,title FROM lessons WHERE unit_id=? ORDER BY number, id", (l["unit_id"],))
    new_order = []
    for row in ordered:
        if row["id"] == l["id"]:
            for pid in part_ids:
                nm = db.query("SELECT title FROM lessons WHERE id=?", (pid,), one=True)["title"]
                new_order.append((pid, nm))
        elif row["id"] not in part_ids:
            new_order.append((row["id"], row["title"]))

    # 3. renumber in two passes so no (unit, number) pair collides on the way
    for i, (lid, _t) in enumerate(new_order, 1):
        db.execute("UPDATE lessons SET number=?, sort=? WHERE id=?", (-i, 100000 + i, lid))
    for i, (lid, title) in enumerate(new_order, 1):
        final = "%d.%d %s" % (un, i, strip_number(title))
        db.execute("UPDATE lessons SET number=?, sort=?, title=? WHERE id=?", (i, i, final, lid))
    return len(part_ids) - 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-chars", type=int, default=6000)
    ap.add_argument("--lesson", type=int)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    db.init_db()
    if args.report or args.dry:
        report(args.min_chars, args.lesson, dry=True)
        return
    rows = db.query("SELECT id FROM lessons WHERE length(content_md)>=? ORDER BY id",
                    (args.min_chars,)) if not args.lesson else [{"id": args.lesson}]
    made = 0
    for r in rows:
        n = apply_split(r["id"], args.min_chars)
        made += n
        if n:
            print("  lesson %d -> +%d lessons" % (r["id"], n))
    print("Split complete. New lessons created: %d" % made)
    if not args.lesson:
        print("Now run:  python3 qbank.py            (10 questions + flashcards for the new lessons)")


if __name__ == "__main__":
    main()
