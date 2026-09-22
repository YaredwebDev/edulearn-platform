"""Fold non-lesson stubs into their neighbours.

Some imported "lessons" are not lessons at all:

* unit preambles — "UNIT 3 — Overview", "5.1 Introduction" (a few rhetorical questions)
* a bare instruction — "5.6 Designing Simple Machine" is one 245-character task line

A student opening one of those finds nothing to learn and no fair way to be assessed.
This tool merges their text into the neighbouring lesson (as an intro block for preambles,
appended for trailing instructions), removes the stub, renumbers the unit, and lets the
question bank be rebuilt afterwards.

    python3 merge_stubs.py --report
    python3 merge_stubs.py            # apply
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db  # noqa: E402

OVERVIEW = re.compile(r"—\s*overview\s*$|^\s*unit\s*\d+\b.*overview", re.I)
INTRO = re.compile(r"^\s*\d+(\.\d+)*\s*(introduction|intro)\s*$", re.I)
INSTRUCTION = re.compile(r"^(use|design|draw|discuss|list|describe|explain|identify|"
                         r"calculate|construct|prepare|carry out|show)\b", re.I)


def is_stub(lesson):
    """True when a lesson cannot carry a lesson's worth of teaching."""
    title = (lesson["title"] or "").strip()
    md = (lesson["content_md"] or "").strip()
    body = re.sub(r"^#+.*$", "", md, flags=re.M).strip()
    words = len(body.split())
    if OVERVIEW.search(title):
        return "unit preamble"
    if INTRO.match(title) and words < 60:
        return "intro preamble"
    # a single sentence of instruction with no facts in it
    if words and len(re.findall(r"[.!?](\s|$)", body)) <= 1 and "|" not in body \
            and len(body) < 320:
        if INSTRUCTION.match(body.lstrip("-*• ")):
            return "bare instruction"
    return None


def plan():
    out = []
    for r in db.query("""SELECT l.id, l.unit_id, l.number, l.title, l.content_md, u.title utitle,
                                s.name sname, s.grade
                         FROM lessons l JOIN units u ON l.unit_id=u.id
                         JOIN subjects s ON u.subject_id=s.id
                         ORDER BY l.unit_id, l.number"""):
        why = is_stub(r)
        if not why:
            continue
        siblings = db.query("SELECT id,number,title FROM lessons WHERE unit_id=? ORDER BY number",
                            (r["unit_id"],))
        pos = [i for i, x in enumerate(siblings) if x["id"] == r["id"]][0]
        target = siblings[pos + 1] if pos + 1 < len(siblings) else (siblings[pos - 1] if pos else None)
        if not target:
            continue
        out.append({"lesson": r, "why": why, "target": target})
    return out


def _merge(donor, target_id, prepend):
    """Append (or prepend) the donor's body to the target lesson."""
    d_md = (donor["content_md"] or "").strip()
    d_md = re.sub(r"^#+\s*.*\n?", "", d_md).strip()          # drop its own heading
    if not d_md:
        return False
    t = db.query("SELECT content_md, content_html FROM lessons WHERE id=?", (target_id,), one=True)
    t_md = (t["content_md"] or "").strip()
    joined = (d_md + "\n\n" + t_md) if prepend else (t_md + "\n\n" + d_md)
    try:
        import markdown as mdlib
        html = mdlib.Markdown(extensions=["tables", "fenced_code", "sane_lists"]).convert(joined)
    except Exception:
        html = "<p>" + joined.replace("\n\n", "</p><p>") + "</p>"
    db.execute("UPDATE lessons SET content_md=?, content_html=? WHERE id=?", (joined, html, target_id))
    db.execute("DELETE FROM questions WHERE lesson_id=?", (donor["id"],))
    db.execute("DELETE FROM flashcards WHERE lesson_id=?", (donor["id"],))
    db.execute("DELETE FROM lesson_progress WHERE lesson_id=?", (donor["id"],))
    db.execute("DELETE FROM lessons WHERE id=?", (donor["id"],))
    return True


def renumber(unit_id):
    rows = db.query("SELECT id,title FROM lessons WHERE unit_id=? ORDER BY number", (unit_id,))
    unit = db.query("SELECT number FROM units WHERE id=?", (unit_id,), one=True)
    un = unit["number"]
    for i, r in enumerate(rows, 1):
        db.execute("UPDATE lessons SET number=?, sort=? WHERE id=?", (-i, 100000 + i, r["id"]))
    for i, r in enumerate(rows, 1):
        title = r["title"] or ""
        new = re.sub(r"^\s*\d+\.\d+\s*", "%d.%d " % (un, i), title) if re.match(r"^\s*\d+\.\d+\s", title) else title
        db.execute("UPDATE lessons SET number=?, sort=?, title=? WHERE id=?", (i, i, new, r["id"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    db.init_db()
    items = plan()
    if not items:
        print("nothing to merge — every lesson is a real lesson")
        return
    units = set()
    for it in items:
        d, t = it["lesson"], it["target"]
        print("%-52s (%s)\n     -> into '%s'" % (d["title"][:52], it["why"], t["title"][:46]))
        units.add(d["unit_id"])
    print("\n%d stub lesson(s) would be merged; %d unit(s) renumbered" % (len(items), len(units)))
    if args.report:
        return
    done = 0
    for it in items:
        prepend = it["why"] in ("unit preamble", "intro preamble")
        if _merge(it["lesson"], it["target"]["id"], prepend):
            done += 1
    for uid in units:
        renumber(uid)
    print("merged %d stub lesson(s). Now rebuild questions: python3 qbank.py --n 10" % done)


if __name__ == "__main__":
    main()
