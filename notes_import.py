"""Import structured HTML study notes into the platform as Grade -> Subject -> Unit -> Lesson.

The notes files are "structured" HTML exports (one file per grade+subject), e.g.
    Chemistry_Grade9_Structured.html
    Physics_Grade10_Structured.html
    Biology_Grade9_Structured.html

The parser is structure-tolerant. It recognises, in order of preference:
  * real headings <h1>..<h6>  ("Unit 3 — ...", "3.2 ...", "Lesson 4: ...")
  * pseudo headings in standalone <p><strong>Unit 3 ...</strong></p> / <div class="...heading">
  * a completely flat document, in which case lessons are grouped into units by the
    leading number of their lesson numbering ("3.2 Periodic table" -> Unit 3).

Nothing in the notes is rewritten: every lesson body is stored verbatim as HTML
(content_html) and as markdown (content_md) so quizzes, flashcards, the unit PDF
export and the SPA renderer all keep working.

Usage
-----
    python3 notes_import.py --notes /home/user/uploads              # import + replace
    python3 notes_import.py --notes DIR --only 9 --dry              # preview only
    python3 notes_import.py --notes DIR --keep                      # merge instead of replace
"""
import argparse, html as htmllib, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db  # noqa: E402

# ---------------------------------------------------------------- subject naming
_SUBJECTS = {
    "biology": ("bio", "Biology"),
    "bio": ("bio", "Biology"),
    "chemistry": ("chem", "Chemistry"),
    "chem": ("chem", "Chemistry"),
    "physics": ("phys", "Physics"),
    "phys": ("phys", "Physics"),
    "english": ("english", "English"),
    "eng": ("english", "English"),
    "mathematics": ("math", "Mathematics"),
    "maths": ("math", "Mathematics"),
    "math": ("math", "Mathematics"),
    "agriculture": ("agric", "Agriculture"),
    "agricultural": ("agric", "Agriculture"),
    "agric": ("agric", "Agriculture"),
    "it": ("it", "ICT"),
    "civics": ("civics", "Civics"),
    "geography": ("geo", "Geography"),
    "history": ("hist", "History"),
}

UNIT_RX = re.compile(r"^\s*(?:unit|chapter|module|part)\s*[:\-\u2013\u2014.]?\s*(\d+)\s*(?![\d.])(.*)$", re.I)
# "1.2 Title" / "1.2. " -> a lesson; a third component ("1.1.1") is a sub-heading, not a lesson
LESSON_RX = re.compile(r"^\s*(?:lesson\s*)?(\d+)\s*\.\s*(\d+)\s*\.?\s*(?![\d.])\s*[:\-\u2013\u2014]?\s*(.*)$")
LESSON_RX3 = re.compile(r"^\s*(?:lesson\s*)?(\d+)\s*[)]\s*(\d+)\s*[:\-\u2013\u2014]?\s*(.*)$")
LESSON_RX2 = re.compile(r"^\s*lesson\s*(\d+)\s*[:\-\u2013\u2014.]?\s*(.*)$", re.I)
GRADE_RX = re.compile(r"(?:grade|gr)\s*[_\-\s]*(\d{1,2})", re.I)
WIDE = lambda key: re.compile(r"(?<![a-z])" + key + r"(?![a-z])")   # underscore-tolerant word match
# supplementary sections that belong to the unit but are not numbered lessons
SUPP_RX = re.compile(r"^[\s\W]*?(?:unit\s*\d+\s*)?(summary|quick\s*revision|revision|review|key\s*(?:facts|points|terms)|"
                     r"glossary|exam\s*focus|practice\s*(?:questions)?|exercises?|overview|checklist)\b", re.I)

TAG_RX = re.compile(r"<[^>]+>")
BLOCK_RX = re.compile(r"</?(?:p|div|li|ul|ol|table|tr|td|th|h[1-6]|section|article|blockquote|br)\b[^>]*>", re.I)
HEAD_RX = re.compile(r"<h([1-6])\b[^>]*>(.*?)</h\1>", re.I | re.S)
PSEUDO_RX = re.compile(
    r"<(p|div|span|strong|b)\b[^>]*>\s*(?:(?:<strong>|<b>|<span[^>]*>)\s*)?((?:unit|chapter|module|lesson)\s*\d+|\d+\.\d+)[^<]{0,160}</(?:p|div|span|strong|b)>",
    re.I,
)


def clean_text(fragment):
    """Strip tags + decode entities from a fragment of HTML."""
    txt = re.sub(r"<(script|style)\b.*?</\1>", " ", fragment, flags=re.I | re.S)
    txt = re.sub(r"<br\s*/?>", " ", txt, flags=re.I)
    txt = TAG_RX.sub(" ", txt)
    txt = htmllib.unescape(txt)
    return re.sub(r"\s+", " ", txt).strip()


def _subject_in(text):
    """Best (code, name) mention in a filename/title; longest keyword wins."""
    low = text.lower()
    hits = []
    for key, (c, n) in _SUBJECTS.items():
        if WIDE(key).search(low):
            hits.append((len(key), c, n))
    if not hits:
        return None, None
    hits.sort(reverse=True)
    return hits[0][1], hits[0][2]


def guess_subject(path):
    """Return (grade, code, name) from a file name, or (0,'','')."""
    base = os.path.basename(path)
    g = GRADE_RX.search(base)
    grade = int(g.group(1)) if g else 0
    code, name = _subject_in(base)
    if grade == 0 or not code:
        # fall back to the document's own title / first heading only (never the body text)
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                head = fh.read(3000)
        except OSError:
            head = ""
        title_area = clean_text(head[:400]) or clean_text(head)
        if grade == 0:
            g2 = re.search(r"grade\s*(\d{1,2})", title_area, re.I)
            grade = int(g2.group(1)) if g2 else 0
        if not code:
            c2, n2 = _subject_in(title_area)
            code, name = (c2 or code), (n2 or name)
    return grade, (code or ""), (name or "")


# ------------------------------------------------------------------- HTML -> MD
def html_to_md(fragment):
    """Very small, loss-free-enough HTML -> markdown converter (used for study/quiz text)."""
    s = re.sub(r"<(script|style)\b.*?</\1>", "", fragment, flags=re.I | re.S)
    s = re.sub(r"<\s*br\s*/?\s*>", "\n", s, flags=re.I)
    for lvl in range(1, 7):
        s = re.sub(r"<h%d\b[^>]*>(.*?)</h%d>" % (lvl, lvl), lambda m: "\n\n" + "#" * lvl + " " + m.group(1).strip() + "\n\n", s, flags=re.I | re.S)
    s = re.sub(r"</?(?:strong|b)\b[^>]*>", "**", s, flags=re.I)
    s = re.sub(r"</?(?:em|i)\b[^>]*>", "*", s, flags=re.I)
    s = re.sub(r"</?code\b[^>]*>", "`", s, flags=re.I)
    s = re.sub(r"<li\b[^>]*>", "\n- ", s, flags=re.I)
    s = re.sub(r"</li\s*>", "", s, flags=re.I)
    s = re.sub(r"</?(?:ul|ol)\b[^>]*>", "\n", s, flags=re.I)
    s = re.sub(r"<t[dh]\b[^>]*>", " | ", s, flags=re.I)
    s = re.sub(r"</tr\s*>", "\n", s, flags=re.I)
    s = re.sub(r"<(?:p|div|blockquote|section|article)\b[^>]*>", "\n\n", s, flags=re.I)
    s = re.sub(r"</(?:p|div|blockquote|section|article|table)\s*>", "\n\n", s, flags=re.I)
    s = TAG_RX.sub("", s)
    s = htmllib.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


# ------------------------------------------------------------------- the parser
def _headings(raw):
    """Return [(start, end, level, text)] for every real or pseudo heading, in order."""
    out = []
    for m in HEAD_RX.finditer(raw):
        txt = clean_text(m.group(2))
        if txt:
            out.append((m.start(), m.end(), int(m.group(1)), txt))
    if len(out) < 3:                     # pseudo headings (<p><strong>Unit 2 ...</strong></p>)
        for m in PSEUDO_RX.finditer(raw):
            txt = clean_text(m.group(2))
            if txt:
                out.append((m.start(), m.end(), 3 if txt[:6].lower().startswith(("unit", "chapt", "modul")) else 4, txt))
    out.sort(key=lambda x: x[0])
    # drop headings that live inside another heading span (nested markup)
    keep = []
    for h in out:
        if keep and h[0] < keep[-1][1]:
            continue
        keep.append(h)
    return keep


def parse_html(text, fallback_title=""):
    """Parse a structured notes document.

    Returns a list of units: [{'number':1,'title':'Unit 1 - ...','intro':md,
                               'lessons':[{'number':1,'title':'1.1 ...','body_html':..,'body_md':..}]}]
    Sub-headings, summary boxes and revision sections that live inside a lesson are kept
    inside that lesson; nothing from the notes is dropped.
    """
    raw = re.sub(r"<(script|style)\b.*?</\1>", " ", text, flags=re.I | re.S)
    heads = _headings(raw)

    # ---- decide which heading level carries units and which carries lessons, so that
    #      sub-headings inside a lesson (e.g. "1.1.1 Definition") stay inside that lesson.
    unit_levels = [lv for _, _, lv, txt in heads if UNIT_RX.match(txt) and not SUPP_RX.match(txt)]
    unit_level = min(unit_levels) if unit_levels else None
    lesson_lvls = []
    for _, _, lv, txt in heads:
        if LESSON_RX.match(txt) or LESSON_RX3.match(txt) or LESSON_RX2.match(txt):
            if unit_level is None or lv > unit_level:
                lesson_lvls.append(lv)
    lesson_level = max(set(lesson_lvls), key=lesson_lvls.count) if lesson_lvls else (
        (unit_level + 1) if unit_level else None)
    supp_levels = [lv for _, _, lv, txt in heads if SUPP_RX.match(txt)]
    supp_level = min(supp_levels) if supp_levels else None

    def kind_of(level, txt):
        if UNIT_RX.match(txt) and not SUPP_RX.match(txt):
            return "unit", None, None
        is_supp = bool(SUPP_RX.match(txt)) and (supp_level is None or level == supp_level)
        if is_supp and (lesson_level is None or level >= lesson_level or unit_level is None or level > unit_level):
            return "lesson", None, None
        if lesson_level is not None and level != lesson_level:
            return "other", None, None
        for rx in (LESSON_RX, LESSON_RX3):
            m = rx.match(txt)
            if m:
                return "lesson", int(m.group(1)), int(m.group(2))
        m2 = LESSON_RX2.match(txt)
        if m2:
            return "lesson", None, int(m2.group(1))
        return "other", None, None

    # ---- classify every heading into an event list
    events = []            # (kind, unit_no, lesson_no, title, head_html, body_html)
    last_ln = {}
    for i, (start, end, level, txt) in enumerate(heads):
        stop = heads[i + 1][0] if i + 1 < len(heads) else len(raw)
        body = raw[end:stop]
        if not clean_text(body) and not re.search(r"<img|<table", body, re.I):
            body = ""
        kind, uno, lno = kind_of(level, txt)
        if kind == "lesson" and uno is not None and lno is not None:
            if lno <= last_ln.get(uno, 0):        # numbering went backwards -> sub-heading
                kind, uno, lno = "other", None, None
            else:
                last_ln[uno] = lno
        events.append((kind, uno, lno, txt, raw[start:end], body))

    k_units = sum(1 for e in events if e[0] == "unit")
    k_lessons = sum(1 for e in events if e[0] == "lesson")

    def new_lesson(number, title, head_html="", body=""):
        return {"number": number, "title": title,
                "body_html": (head_html + body).strip(), "body_md": html_to_md(head_html + body)}

    # ---- case 1: numbered lessons ("x.y") grouped into units by their prefix
    if k_lessons and not k_units:
        units, order = {}, []
        cur_lesson = None
        for kind, uno, lno, title, head_html, body in events:
            if kind != "lesson":
                if cur_lesson is not None:                     # sub-heading inside the lesson
                    cur_lesson["body_html"] += (head_html + body)
                    cur_lesson["body_md"] = html_to_md(cur_lesson["body_html"])
                continue
            un = uno if uno is not None else 1
            if un not in units:
                units[un] = {"number": un, "title": "Unit %d" % un, "intro": "", "lessons": []}
                order.append(un)
            cur_lesson = new_lesson(lno or (len(units[un]["lessons"]) + 1), title, head_html, body)
            units[un]["lessons"].append(cur_lesson)
        out = [units[u] for u in order]
        first_h = heads[0][3] if heads else fallback_title
        if len(out) == 1 and first_h and re.search(r"[A-Za-z]{3}", first_h) and not UNIT_RX.match(first_h):
            out[0]["title"] = first_h
        return _renumber(out)

    # ---- case 2: explicit unit headings (with or without lessons under them)
    out, cur, cur_lesson = [], None, None
    for kind, uno, lno, title, head_html, body in events:
        if kind == "unit":
            cur = {"number": uno, "title": title, "intro": "", "lessons": []}
            out.append(cur)
            cur_lesson = None
            if clean_text(body):
                cur["intro"] = html_to_md(body)
        elif kind == "lesson":
            if cur is None:
                cur = {"number": 1, "title": "Unit 1", "intro": "", "lessons": []}
                out.append(cur)
            cur_lesson = new_lesson(lno or 0, title, head_html, body)
            cur["lessons"].append(cur_lesson)
        else:                                  # sub-heading: belongs to the open lesson / unit
            if cur_lesson is not None:
                cur_lesson["body_html"] += (head_html + body)
                cur_lesson["body_md"] = html_to_md(cur_lesson["body_html"])
            elif cur is not None:
                if clean_text(body):
                    cur["intro"] = (cur["intro"] + "\n\n" + html_to_md(head_html + body)).strip()
                elif (title and len(title) > 3
                      and re.fullmatch(r"\s*(?:unit|chapter|module|part)\s*\d+\s*", cur["title"], re.I)):
                    cur["title"] = title       # bare "Unit 3" -> descriptive heading that follows
            elif title and not re.search(r"grade\s*\d", title, re.I):
                out.append({"number": 1, "title": title, "intro": html_to_md(body), "lessons": []})
                cur = out[-1]

    out = [u for u in out if u["lessons"] or u["intro"]]

    # ---- unit-level intro that never became a lesson: keep it as an "Overview" lesson
    for u in out:
        intro = (u.get("intro") or "").strip()
        if intro and len(strip_tags(intro)) > 200:
            u["lessons"].insert(0, {"number": 0, "title": "%s — Overview" % u["title"].split("—")[0].strip(),
                                    "body_html": "", "body_md": intro})
        u["intro"] = "" if len(strip_tags(intro)) > 200 else intro

    # ---- a document with one unit heading but lessons hidden in nested headings
    if out and not any(u["lessons"] for u in out):
        for u in out:
            parts = re.split(r"\n(?=###+ )", u.get("intro") or "")
            u["lessons"] = [{"number": j + 1, "title": re.sub(r"^#+\s*", "", p.split("\n")[0])[:120],
                             "body_html": "", "body_md": p.strip()} for j, p in enumerate(parts) if p.strip()]
            u["intro"] = ""
    return _renumber(out)


def parse_markdown(text, fallback_title=""):
    """Markdown / plain-text notes -> same structure as the HTML parser."""
    try:
        import markdown as mdlib
        html = mdlib.markdown(text or "", extensions=["tables", "fenced_code", "sane_lists"])
    except Exception:
        html = "\n".join(
            "<h%d>%s</h%d>" % (len(m.group(1)), m.group(2), len(m.group(1)))
            if (m := re.match(r"^(#{1,6})\s+(.*)$", line)) else line
            for line in (text or "").split("\n"))
    return parse_html(html, fallback_title)


def _is_helper_file(name):
    """README-style files are documentation, not study notes."""
    stem = os.path.splitext(os.path.basename(name))[0].strip().lower()
    return stem in ("readme", "index", "license", "changelog") or stem.startswith("readme")


# A 'unit' that is really a boxed extra rather than a chapter of the textbook.
_BOX_RX = re.compile(r"(quick\s*revision|must[-\s]*know|formula\s*sheet|exam[-\s]*trap|"
                     r"glossary|how\s*to\s*use|key\s*facts|cheat\s*sheet)", re.I)
_TOC_RX = re.compile(r"^\s*(?:[\U0001F300-\U0001FAFF\u2600-\u27BF]+\s*)?table\s*of\s*contents", re.I)


def tidy_units(units):
    """Tidy a parsed document into clean textbook units.

    * drops a 'Table of Contents' pseudo-unit (navigation, not learning content)
    * folds single-lesson revision/formula/glossary 'units' into the previous unit
      as ordinary lessons, so every unit is a real chapter
    """
    out = []
    for u in units:
        title = (u["title"] or "").strip()
        body = " ".join(strip_tags(l.get("body_html") or l.get("body_md") or "")
                        for l in u["lessons"])
        if _TOC_RX.match(title) or (title.lower().startswith(("📑",)) and "content" in title.lower()):
            continue                                   # navigation only
        if out and _BOX_RX.search(title) and len(u["lessons"]) <= 2 and not u.get("intro"):
            prev = out[-1]                             # it belongs to the unit before it
            for l in u["lessons"]:
                if not l["title"] or l["title"].strip().lower().startswith("📑"):
                    l["title"] = title
                prev["lessons"].append(l)
            continue
        out.append(u)
    return out


def audit(units):
    """Quality checks on a parsed document: returns a list of human-readable issues."""
    issues = []
    seen_titles = {}
    for u in units:
        if not u["lessons"]:
            issues.append("Unit %d has no lessons: %s" % (u["number"], u["title"][:60]))
        for l in u["lessons"]:
            body = strip_tags(l["body_html"] or l["body_md"] or "")
            if len(body) < 40:
                issues.append("thin lesson (u%d l%d, %d chars): %s"
                              % (u["number"], l["number"], len(body), l["title"][:60]))
            key = l["title"].strip().lower()
            if key in seen_titles:
                issues.append("duplicate lesson title: %s (units %d and %d)"
                              % (l["title"][:60], seen_titles[key], u["number"]))
            seen_titles[key] = u["number"]
    return issues


def print_tree(units, max_body=0):
    total = 0
    for u in units:
        title = re.sub(r"^\s*unit\s*\d+\s*[—\-–:]\s*", "", u["title"], flags=re.I).strip() or u["title"]
        print("  Unit %d — %s   (%d lessons)" % (u["number"], title[:70], len(u["lessons"])))
        for l in u["lessons"]:
            total += 1
            body = strip_tags(l["body_html"] or l["body_md"] or "")
            print("      %2d. %-64s %5d chars" % (l["number"], l["title"][:64], len(body)))
    print("  TOTAL: %d units / %d lessons" % (len(units), total))


def strip_tags(html_text):
    return re.sub(r"\s+", " ", TAG_RX.sub(" ", html_text or "")).strip()


def _renumber(units):
    """Make unit/lesson numbering dense and ordered; drop empties."""
    units = tidy_units(units)
    units = [u for u in units if u["lessons"] or u["intro"]]
    for i, u in enumerate(units, 1):
        u["number"] = i
        u["title"] = (u["title"] or "Unit %d" % i).strip()
        seen = 0
        for j, l in enumerate(u["lessons"], 1):
            seen += 1
            l["number"] = j
            l["title"] = (l["title"] or "Lesson %d" % j).strip()
    return units


# ------------------------------------------------------------------- DB writing
def subject_row(grade, code, name):
    row = db.query("SELECT * FROM subjects WHERE grade=? AND code=?", (grade, code), one=True)
    if row:
        return row["id"]
    sid = db.execute("INSERT INTO subjects(grade,code,name,description,sort) VALUES(?,?,?,?,0)",
                     (grade, code, name, "Grade %d %s" % (grade, name)))
    return sid


# --------------------------------------------------------------- file readers
def _docx_to_html(path):
    """Word document -> HTML (needs python-docx; skipped gracefully when absent)."""
    try:
        import docx  # python-docx
    except Exception:
        raise RuntimeError("python-docx is not installed (pip install python-docx)")
    d = docx.Document(path)
    out = []
    for para in d.paragraphs:
        txt = (para.text or "").strip()
        if not txt:
            continue
        style = (para.style.name or "").lower()
        m = re.match(r"heading\s*(\d+)", style)
        if m:
            lvl = min(6, max(1, int(m.group(1))))
            out.append("<h%d>%s</h%d>" % (lvl, htmllib.escape(txt), lvl))
        elif style.startswith("list"):
            out.append("<li>%s</li>" % htmllib.escape(txt))
        else:
            out.append("<p>%s</p>" % htmllib.escape(txt))
    for table in d.tables:
        rows = ["<tr>" + "".join("<td>%s</td>" % htmllib.escape(c.text.strip()) for c in r.cells) + "</tr>"
                for r in table.rows]
        out.append("<table>%s</table>" % "".join(rows))
    return "\n".join(out)


def _pdf_to_text(path):
    """PDF -> text (needs pypdf; skipped gracefully when absent)."""
    try:
        from pypdf import PdfReader
    except Exception:
        raise RuntimeError("pypdf is not installed (pip install pypdf)")
    reader = PdfReader(path)
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n\n".join(pages)


def read_documents(path):
    """Return [(name, text, kind)] for a notes file (or every file inside a zip).

    kind is 'html' or 'md' so the parser can treat the text the right way.
    """
    low = path.lower()
    if low.endswith(".zip"):
        import zipfile, tempfile
        docs = []
        with zipfile.ZipFile(path) as z:
            tmp = tempfile.mkdtemp(prefix="notes_zip_")
            for info in z.infolist():
                if info.is_dir() or info.filename.startswith("__MACOSX"):
                    continue
                inner = info.filename
                if inner.lower().endswith((".html", ".htm", ".md", ".txt", ".docx", ".pdf")):
                    z.extract(info, tmp)
                    for name, text, kind in read_documents(os.path.join(tmp, inner)):
                        docs.append((os.path.basename(inner), text, kind))
        return docs
    if low.endswith((".html", ".htm")):
        with open(path, encoding="utf-8", errors="ignore") as fh:
            return [(os.path.basename(path), fh.read(), "html")]
    if low.endswith(".docx"):
        return [(os.path.basename(path), _docx_to_html(path), "html")]
    if low.endswith(".pdf"):
        return [(os.path.basename(path), _pdf_to_text(path), "md")]
    with open(path, encoding="utf-8", errors="ignore") as fh:
        return [(os.path.basename(path), fh.read(), "md")]


def import_document(path, replace=True, dry=False, verbose=True):
    """Import one structured notes file. Returns a summary dict."""
    base = os.path.basename(path)
    try:
        docs = read_documents(path)
    except Exception as e:
        return {"file": base, "ok": False, "error": str(e)}
    # a zip may hold several files - import each with its own name
    if len(docs) > 1:
        results = []
        for name_in, text_in, kind in docs:
            sub = os.path.join(os.path.dirname(path), name_in)
            results.append(_import_text(sub, text_in, kind, replace=replace, dry=dry, verbose=verbose))
        merged = {"file": base, "ok": all(r.get("ok") for r in results),
                  "units": sum(r.get("units", 0) for r in results),
                  "lessons": sum(r.get("lessons", 0) for r in results),
                  "parts": len(results)}
        if verbose:
            print("  %-46s -> %d file(s) inside: %d units / %d lessons"
                  % (base, len(results), merged["units"], merged["lessons"]))
        return merged
    name_in, text, kind = docs[0]
    return _import_text(path, text, kind, replace=replace, dry=dry, verbose=verbose)


def _import_text(path, text, kind="html", replace=True, dry=False, verbose=True):
    grade, code, name = guess_subject(path)
    base = os.path.basename(path)
    if not (grade and code):
        return {"file": base, "ok": False, "error": "could not detect grade/subject from name"}
    units = parse_html(text, fallback_title=name) if kind == "html" else parse_markdown(text)
    n_lessons = sum(len(u["lessons"]) for u in units)
    info = {"file": base, "grade": grade, "subject": name, "units": len(units),
            "lessons": n_lessons, "ok": True, "replaced": 0}
    if verbose:
        print("  %-46s grade %-2s %-12s -> %2d units / %3d lessons" % (base, grade, name, len(units), n_lessons))
    if dry or not units:
        return info

    sid = subject_row(grade, code, name)

    # ---- keep a map of old lessons (unit_no, lesson_no) -> id so student progress survives
    old = {}
    for r in db.query("""SELECT l.id,l.number ln,u.number un FROM lessons l JOIN units u ON l.unit_id=u.id
                         WHERE u.subject_id=?""", (sid,)):
        old[(r["un"], r["ln"])] = r["id"]

    if replace:
        db.execute("DELETE FROM questions WHERE lesson_id IN (SELECT l.id FROM lessons l JOIN units u ON l.unit_id=u.id WHERE u.subject_id=?)", (sid,))
        db.execute("DELETE FROM flashcards WHERE lesson_id IN (SELECT l.id FROM lessons l JOIN units u ON l.unit_id=u.id WHERE u.subject_id=?)", (sid,))
        db.execute("""DELETE FROM lesson_progress WHERE lesson_id IN
                      (SELECT l.id FROM lessons l JOIN units u ON l.unit_id=u.id WHERE u.subject_id=?)""", (sid,))
        db.execute("""DELETE FROM lessons WHERE unit_id IN (SELECT id FROM units WHERE subject_id=?)""", (sid,))
        db.execute("DELETE FROM units WHERE subject_id=?", (sid,))
        info["replaced"] = len(old)

    for u in units:
        uid = db.execute("INSERT INTO units(subject_id,number,title,sort) VALUES(?,?,?,?)",
                         (sid, u["number"], u["title"], u["number"]))
        for l in u["lessons"]:
            body_html = l["body_html"] or ""
            body_md = l["body_md"] or ""
            lid = db.execute("""INSERT INTO lessons(unit_id,number,title,content_md,content_html,sort)
                                VALUES(?,?,?,?,?,?)""",
                             (uid, l["number"], l["title"], body_md, body_html, l["number"]))
            key = (u["number"], l["number"])
            if key in old:              # carry the student's progress across the content swap
                db.execute("UPDATE lesson_progress SET lesson_id=? WHERE lesson_id=?", (lid, old[key]))
                db.execute("UPDATE attempts SET lesson_id=? WHERE lesson_id=?", (lid, old[key]))
    return info


def import_folder(folder, only=None, replace=True, dry=False):
    files = sorted(f for f in os.listdir(folder)
                   if f.lower().endswith((".html", ".htm", ".md", ".txt", ".zip", ".docx", ".pdf"))
                   and not _is_helper_file(f))
    if not files:
        print("No .html files found in", folder)
        return []
    summaries = []
    for f in files:
        path = os.path.join(folder, f)
        g, _, _ = guess_subject(path)
        if only and g not in only:
            continue
        summaries.append(import_document(path, replace=replace, dry=dry))
    return summaries


def main():
    ap = argparse.ArgumentParser(description="Import structured HTML notes into EduLearn.")
    ap.add_argument("--notes", required=True, help="folder containing the *_Structured.html files")
    ap.add_argument("--only", default="", help="comma separated grades to import, e.g. 9,10")
    ap.add_argument("--keep", action="store_true", help="merge instead of replacing existing subject content")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--preview", action="store_true",
                    help="show the full unit/lesson breakdown and quality checks, write nothing")
    args = ap.parse_args()
    db.init_db()
    only = [int(x) for x in re.findall(r"\d+", args.only)] or None

    if args.preview:                      # breakdown preview, nothing is written
        files = sorted(f for f in os.listdir(args.notes)
                       if f.lower().endswith((".html", ".htm", ".md", ".txt", ".zip", ".docx", ".pdf"))
                       and not _is_helper_file(f))
        for f in files:
            path = os.path.join(args.notes, f)
            g, _c, n = guess_subject(path)
            if only and g not in only:
                continue
            print("\n" + "=" * 88)
            print("%s   [grade %s · %s]" % (f, g or "?", n or "?"))
            print("=" * 88)
            try:
                for name_in, text, kind in read_documents(path):
                    units = parse_html(text, fallback_title=n) if kind == "html" else parse_markdown(text, n)
                    units = _renumber(units)   # show exactly what would be imported
                    if len(files) > 1 or True:
                        pass
                    print_tree(units)
                    for issue in audit(units):
                        print("   ⚠ ", issue)
            except Exception as e:
                print("   !! could not read:", e)
        return

    print("Importing notes from", args.notes, "(replace)" if not args.keep else "(merge)")
    res = import_folder(args.notes, only=only, replace=not args.keep, dry=args.dry)
    bad = [r for r in res if not r.get("ok")]
    print("Files: %d  |  units: %d  |  lessons: %d" % (
        len(res), sum(r.get("units", 0) for r in res), sum(r.get("lessons", 0) for r in res)))
    for b in bad:
        print("  !! skipped", b["file"], "-", b["error"])
    if args.dry:
        print("(dry run - nothing written)")


if __name__ == "__main__":
    main()
