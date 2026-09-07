"""Heuristic question + flashcard generator.

Produces DRAFT assessment items strictly from each lesson's own content so that no
fact is invented. Every generated item is stored with status 'AI Generated' so it can
be reviewed/edited/approved in the admin panel. Questions never exceed the lesson text.

Run:  python3 generator.py            # whole DB
      python3 generator.py --lesson N # single lesson
"""
import os, re, argparse, random
import db

random.seed(7)
LINK = re.compile(r"\b(is|are|was|were|refers?\s+to|means?|known\s+as|called|defined\s+as|"
                  r"consists?\s+of|has|have|composed\s+of|made\s+of|uses?|occurs?\s+in|"
                  r"takes\s+place\s+in|produced\s+by|are\s+used\s+for|stands\s+for)\b", re.I)


def clean_term(t):
    return re.sub(r"[\[\](){}<>*_`\"']", "", t).strip()


BAD_START = ("must-know", "must remember", "note", "tip", "trap", "exam", "key takeaway",
             "brainstorm", "language tip", "important", "see ", "check ", "do ", "answer",
             "source", "adapted", "figure", "fig ", "table", "nb", "remember", "writing tip",
             "reading skill", "activity", "example")

def _good_term(t):
    if len(t) < 2 or len(t) > 42:
        return False
    if re.match(r"^[\d.,\-+=\s]+$", t):
        return False
    if ":" in t or ";" in t or "=" in t:
        return False
    low = t.lower()
    if low.startswith(BAD_START):
        return False
    # allow word-ish phrases (letters, spaces, apostrophes, hyphen)
    if not re.fullmatch(r"[\w \-'’]+", t):
        return False
    return True


def split_sentences(text):
    # crude sentence splitter that ignores newline-only breaks
    text = re.sub(r"\s+", " ", text)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", text)
    return [p.strip() for p in parts if len(p.strip()) > 25]


def extract_terms(md_text):
    """Return ordered list of distinct bolded terms found in the markdown."""
    terms = []
    seen = set()
    for m in re.finditer(r"\*\*([^*\n]{2,60})\*\*", md_text):
        t = clean_term(m.group(1))
        if not _good_term(t):
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        terms.append(t)
    return terms


def term_definition(term, para):
    """Find a usable one-line definition/fact sentence in paragraph mentioning term."""
    term_rx = re.escape(term)
    for s in split_sentences(para):
        if not re.search(term_rx, s, re.I):
            continue
        if LINK.search(s):
            return s
    # fallback: the sentence containing the term
    for s in split_sentences(para):
        if re.search(term_rx, s, re.I):
            return s
    return None


def _para_of_term(term, text):
    """Find the paragraph containing the term's definition-ish sentence."""
    paras = re.split(r"\n\s*\n", text)
    best = None
    for p in paras:
        if re.search(re.escape(term), p, re.I):
            if best is None or len(p) < len(best):
                best = p
    return best or text


def best_definition(term, text):
    """Return a clean short definitional sentence for term, or None.

    Prefers a sentence that STARTS with the term; else the shortest sentence that
    contains the term and a definition link verb. Keeps only compact sentences so
    generated items are readable.
    """
    rx = re.escape(term)
    starts, contains, any_contains = [], [], []
    for s in split_sentences(text):
        core = re.sub(r"^[-•*]\s*", "", s).strip()
        if not re.search(rx, core, re.I):
            continue
        L = len(core)
        if L > 240:
            continue
        if L > 10 and re.match(rx + r"[\s:]", core, re.I | re.IGNORECASE):
            starts.append(core)
        if L > 10 and LINK.search(core):
            contains.append(core)
        any_contains.append(core)
    if starts:
        return min(starts, key=len)
    if contains:
        return min(contains, key=len)
    if any_contains:
        return min(any_contains, key=len)
    return None


def strip_md(s):
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    return s.strip()


def shorten(s, limit=220):
    s = strip_md(s).replace("  ", " ")
    return s if len(s) <= limit else s[:limit].rsplit(" ", 1)[0] + "…"


def build_lesson(lesson_id):
    """Generate questions+flashcards for one lesson. Returns counts."""
    lesson = db.query("SELECT id,unit_id,title,content_md FROM lessons WHERE id=?", (lesson_id,), one=True)
    if not lesson:
        return (0, 0)
    text = lesson["content_md"] or ""
    terms = extract_terms(text)
    # build definition map using clean short sentences only
    term_def = {}
    for t in terms:
        d = best_definition(t, text)
        if d:
            term_def[t] = d
    # flashcards: term->definition
    db.execute("DELETE FROM flashcards WHERE lesson_id=?", (lesson_id,))
    fcount = 0
    for t in terms[:12]:
        if t not in term_def:
            continue
        db.execute("INSERT INTO flashcards(lesson_id,front,back,sort) VALUES(?,?,?,?)",
                   (lesson_id, t, term_def[t], fcount))
        fcount += 1

    db.execute("DELETE FROM questions WHERE scope='lesson' AND lesson_id=?", (lesson_id,))
    unit = db.query("SELECT subject_id FROM units WHERE id=?", (lesson["unit_id"],), one=True)
    subject_id = unit["subject_id"]

    qs = []
    items = list(term_def.items())
    if len(items) < 4:
        # too few clean definition pairs -> not enough to make MCQs safely
        return (0, fcount)
    random.shuffle(items)
    # 1) Definition MCQs (term -> correct definition among other terms' defs)
    mcq_n = 0
    for i in range(min(9, len(items))):
        term, defn = items[i]
        others = [o for o in items if o[0] != term and len(o[1]) > 8]
        if len(others) < 3:
            continue
        dist = [x[1] for x in random.sample(others, 3)]
        choices = [defn] + dist
        random.shuffle(choices)
        answer = defn
        ai = choices.index(defn)
        qs.append({
            "scope": "lesson", "lesson_id": lesson_id, "subject_id": subject_id,
            "qtype": "mcq",
            "prompt": f"Which of the following correctly describes '{term}'?",
            "choices": choices, "answer": answer, "answer_index": ai,
            "explanation": f"'{term}' is correctly described as: {defn}",
            "difficulty": "Medium", "concept": term,
            "status": "AI Generated", "sort": mcq_n})
        mcq_n += 1

    # 2) Cloze / complete-the-sentence items from definitional sentences
    clo_n = 0
    for term, defn in items[mcq_n:]:
        # only if definition contains the term literally and is replaceable
        if term.lower() not in defn.lower():
            continue
        if clo_n >= 5:
            break
        others_t = [o for o in items if o[0] != term]
        if len(others_t) < 3:
            continue
        cloze = re.sub(re.escape(term), "______", defn, flags=re.I, count=1)
        options = [o[0] for o in random.sample(others_t, 3)] + [term]
        random.shuffle(options)
        qs.append({
            "scope": "lesson", "lesson_id": lesson_id, "subject_id": subject_id,
            "qtype": "mcq",
            "prompt": f"Complete the sentence: \"{cloze}\"",
            "choices": options, "answer": term, "answer_index": options.index(term),
            "explanation": f"The missing term is '{term}'. The full statement: {defn}",
            "difficulty": "Easy", "concept": term,
            "status": "AI Generated", "sort": 50 + clo_n})
        clo_n += 1

    # 3) True/False from clear factual sentences that are self-contained
    tf = 0
    sentences = split_sentences(text)
    for s in sentences:
        if tf >= 2:
            break
        # pick standalone statements that clearly assert a fact and aren't questions
        if "?" in s or "if " in s.lower() and "?" in s:
            continue
        if s.lower().startswith(("which", "what", "how", "why", "when", "who", "where",
                                 "note:", "nb:", "hint", "tip", "e.g", "i.e", "see")):
            continue
        if len(s) > 40 and not s.startswith(("•", "-")):
            stat = shorten(s, 160).rstrip(".") + "."
            if re.match(r"^[A-Z]", stat):
                qs.append({
                    "scope": "lesson", "lesson_id": lesson_id, "subject_id": subject_id,
                    "qtype": "tf",
                    "prompt": f"True or False: {stat}",
                    "choices": ["True", "False"], "answer": "True", "answer_index": 0,
                    "explanation": f"The lesson states: {stat}",
                    "difficulty": "Easy", "concept": lesson["title"],
                    "status": "AI Generated", "sort": 90 + tf})
                tf += 1

    for q in qs:
        db.execute("""INSERT INTO questions
            (scope,lesson_id,subject_id,qtype,prompt,choices,answer,answer_index,
             explanation,difficulty,concept,status,sort,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (q["scope"], q["lesson_id"], q["subject_id"], q["qtype"], q["prompt"],
             __import__("json").dumps(q["choices"], ensure_ascii=False), q["answer"],
             q["answer_index"], q["explanation"], q["difficulty"], q["concept"],
             q["status"], q["sort"], db.now()))
    return (len(qs), fcount)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lesson", type=int, default=None)
    ap.add_argument("--subject", type=int, default=None)
    args = ap.parse_args()
    db.init_db()
    if args.lesson:
        print("lesson:", args.lesson, build_lesson(args.lesson))
        return
    lessons = db.query("SELECT id FROM lessons" + (" WHERE unit_id IN (SELECT id FROM units WHERE subject_id=?)" if args.subject else ""),
                       (args.subject,) if args.subject else ())
    total_q = total_f = 0
    for i, row in enumerate(lessons, 1):
        q, f = build_lesson(row["id"])
        total_q += q; total_f += f
        if i % 150 == 0:
            print(f"  {i}/{len(lessons)} ...")
    print(f"Done: {len(lessons)} lessons, {total_q} questions, {total_f} flashcards")


if __name__ == "__main__":
    main()
