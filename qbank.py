"""Build the lesson question bank: 10 assessment items for every lesson, plus flashcards.

Every item is produced *only* from the lesson notes, so nothing is invented:
  * "Term: definition" bullets, **bold** definitions and definitional prose sentences
  * complete statements quoted from the lesson (true/false)
  * the same statements with one number or term deliberately altered (false)
  * worked lines containing "=" turned into fill-in-the-blank calculations

Distractors are other definitions/terms/formulas taken from the same subject, so wrong
options are always plausible but never correct.

Authored or reviewed questions (status 'Approved') are never deleted: they count
towards the 10 and the generator tops the lesson up.

    python3 qbank.py                     # every lesson in the DB
    python3 qbank.py --grade 9,10        # grades 9 and 10 only
    python3 qbank.py --subject 6         # one subject id
    python3 qbank.py --lesson 783        # one lesson, prints the items
    python3 qbank.py --grade 9 --n 10 --report
"""
import argparse, json, os, random, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db  # noqa: E402

random.seed(11)

DEF_VERB = re.compile(r"\b(is|are|was|were|refers? to|means?|denotes?|defined as|known as|called|"
                      r"consists? of|composed of|made (?:up )?of|represents?|indicates?|describes?|"
                      r"states? that|occurs? (?:when|in)|takes? place|equals?|measures?|shows?|"
                      r"contains?|includes?|involves?|produced (?:by|from)|used (?:for|to)|"
                      r"formed (?:by|when|from)|results? (?:in|from))\b", re.I)
BAD_TERM = ("example", "note", "n.b", "nb", "tip", "trap", "answer", "solution", "figure", "fig",
            "table", "activity", "exercise", "question", "important", "remember", "summary",
            "key terms", "definition", "types", "steps", "rules", "check", "source", "unit",
            "lesson", "chapter", "review", "objective", "introduction", "conclusion", "overview",
            "quick revision", "practice", "self-check", "did you know", "warning", "caution")
INSTRUCTION = re.compile(r"^\s*(lab\s*activity|activity|exercise|task|inquiry|project|practical|experiment|"
                         r"do this|discuss|write|draw|calculate|work\s*(it\s*)?out|try\s|read\s|copy\s|"
                         r"complete\s+the|answer\s+the|study\s+the|use\s+the)", re.I)
SKIP_START = ("which", "what", "how", "why", "when", "who", "where", "list", "state", "explain",
              "describe", "give", "write", "calculate", "compute", "define", "name", "find",
              "solve", "suppose", "if ")
STOP_TERMS = {"it", "this", "that", "they", "these", "those", "there", "he", "she", "we", "you",
              "i", "one", "the", "a", "an"}
NUM_TOKEN = r"-?\d+(?:[.,]\d+)*(?:\s*(?:%|percent|kg|g|mg|km|m|cm|mm|l|ml|s|min|h|hours?|days?|"\
            r"years?|mol|mmol|j|kj|kj/mol|nm|pm|ev|hz|c|k|°c|°f|v|a|n|pa|atm))?"


# ================================================================= text helpers
def strip_md(s):
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s or "")
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"^#+\s*", "", s)
    return re.sub(r"\s+", " ", s).strip()


def clean_term(t):
    t = strip_md(t).strip(" \t.:;,-–—•*`\"'[]")
    t = re.sub(r"\s+", " ", t)
    if t.count("(") != t.count(")"):                           # unbalanced "(SI" -> cut it off
        t = t[:t.index("(")] if "(" in t else t.replace(")", "")
    if t.count("(") == 1 and t.endswith(")"):                  # keep "Units (SI)" style names
        t = t[:-1] + ")" if not t.endswith("()") else t
    return t.strip(" ,;:")


UNIT_ONLY = re.compile(r"^[\d\s.,/%°·×^\-]*(?:kg|g|mg|km|cm|mm|nm|pm|ml|mls|l|mol|mmol|j|kj|nm|hz|ev|v|a|n|pa|atm|c|k|s|min|h|°c|°f|g/cm3|g/ml|g/l)[\d\s.,/%°·×^\-]*$", re.I)


def term_ok(t):
    if not (2 <= len(t) <= 44):
        return False
    if t.lower() in STOP_TERMS or t.lower().startswith(BAD_TERM):
        return False
    if re.fullmatch(r"[\d\W]+", t) or UNIT_ONLY.match(t):
        return False
    if re.search(r"[:;=?!]|→|↔|°|×|·", t):
        return False
    if t.count("(") != t.count(")"):
        return False
    if t.count("/") > 1:
        return False
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 \-'&.()/+]*", t):
        return False
    if len(t.split()) > 6 or not re.search(r"[A-Za-z]{2}", t):
        return False
    return True


def clean_defn(d):
    d = re.sub(r"\s*\|\s*", " ", d or "")          # table cell separators
    d = strip_md(d).replace("*", "").strip(" \t:;,-–—•*")
    d = re.sub(r"^(?:is|are|was|were|means|refers to|defined as|known as|called)\s+", lambda m: m.group(0), d)
    return re.sub(r"\s+", " ", d).strip()


def defn_ok(d):
    if not (15 <= len(d) <= 260) or "|" in d:
        return False
    if d.lower().startswith(("which", "what", "how", "why", "when", "who", "where")):
        return False
    if re.search(r"\b(page|see figure|see table|figure \d|fig\.)\b", d, re.I):
        return False
    if d.count("/") > 2 or "↔" in d or "→" in d:
        return False
    if len(d.split()) < 4:                                     # "amount of matter" alone is too thin
        return False
    return True


def is_prose(d):
    """A sentence-like description rather than a formula/bullet fragment."""
    if re.search(r"[=→]|\b\d+\s*/\s*\d+\b", d):
        return False
    if len(re.findall(r"\d", d)) > 8:
        return False
    return bool(re.search(r"[a-z]{3}", d)) and (len(d.split()) >= 4)


def sentences(md):
    """Split markdown into (sentence, raw_line) keeping bullets as separate units."""
    out = []
    for line in re.split(r"\n", md or ""):
        raw = line.strip()
        if not raw or raw.startswith(("|", "---", "```", "#")):
            continue
        if raw.startswith("|"):
            continue
        body = re.sub(r"^[-*•]\s*", "", raw)
        body = re.sub(r"^(?:\d+|[a-z])[.)]\s+", "", body)      # "1. " / "a) " enumerations
        body = re.sub(r"\s*\*+\s*$", "", body)
        if not body or body.endswith(":"):
            continue
        if len(body) <= 300 and not body.endswith((".", "!", ":", "?", ";")):
            pass
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", body):
            s = strip_md(s).strip()
            if 22 <= len(s) <= 300:
                out.append(s)
    return out


def bullets(md):
    """Consecutive bullet blocks (>=3 items) as lists of cleaned item strings."""
    blocks, cur = [], []
    for line in re.split(r"\n", md or ""):
        m = re.match(r"^\s*[-*•]\s+(.*)$", line)
        if m:
            item = strip_md(m.group(1)).strip(" .;:")
            cur.append(item)
        else:
            if len(cur) >= 3:
                blocks.append(cur)
            cur = []
    if len(cur) >= 3:
        blocks.append(cur)
    return [[i for i in b if 3 <= len(i) <= 120] for b in blocks]


def numbers_in(text):
    out = []
    for m in re.finditer(NUM_TOKEN, text or ""):
        v = m.group(0).strip()
        if re.fullmatch(r"\d", v):                       # single digits are usually list numbers
            continue
        if re.fullmatch(r"\d+(?:\.\d+){2,}.*", v):      # "2.1.1" is a section number, not a value
            continue
        if v not in out:
            out.append(v)
    return out


UNIT_SUFFIX = re.compile(r"([A-Za-z%°][A-Za-z0-9/^·.\-]*)\s*$")


def split_unit(value):
    """('0.869', 'g/mL') style split so options stay unit-consistent."""
    m = re.search(r"\s*([A-Za-z%°][A-Za-z0-9/^·.\-]*)\s*$", value or "")
    if not m:
        return (value or "").strip(), ""
    unit = m.group(1)
    if unit.lower() in ("a", "an", "the"):
        return (value or "").strip(), ""
    return value[:m.start()].strip(), unit


def same_unit(options, correct):
    """Make every option carry the same unit as the correct answer."""
    num, unit = split_unit(correct)
    fixed = []
    for o in options:
        on, ou = split_unit(o)
        if unit:
            fixed.append(("%s %s" % (on, unit)).strip() if ou.lower() != unit.lower() else o)
        else:
            fixed.append(on if ou else o)
    return fixed


def fit(s, limit=170):
    """Shorten at a word boundary without leaving broken words."""
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) <= limit:
        return s
    cut = s[:limit].rsplit(" ", 1)[0].rstrip(" ,;:")
    return cut + "…"


# ============================================================ definition mining
SEP = r"[:=\-–—]"
BULLET_DEF = re.compile(r"^\s*[-*•]\s+\*\*(?P<t>[^*]{2,60}?)\*\*\s*(?P<sep>" + SEP + r"|is|are|means|refers to)\s*(?P<d>.{20,})$", re.I)
BULLET_DEF2 = re.compile(r"^\s*[-*•]\s+(?P<t>[A-Z][^:=–—\n]{2,44}?)\s*(?P<sep>" + SEP + r"|is|are)\s*(?P<d>.{25,})$")
BULLET_DEF3 = re.compile(r"^\s*[-*•]\s+\*\*(?P<t>[^*]{2,60}?)\*\*\s+(?P<d>.{25,})$")
PROSE_DEF = re.compile(r"(?P<t>[A-Z][\w'’\-]*(?:\s+[\w'’\-]+){0,4})\s+(?P<v>is|are|means|refers to|is defined as|is known as)\s+(?P<d>.{20,})$")
# "Scientific method: a systematic approach ..." on any line (not only bullets)
COLON_DEF = re.compile(r"^\s*(?:[-*•]\s*)?(?P<t>[A-Z][\w'’\-]*(?:\s+[\w'’\-]+){0,4})\s*:\s*(?P<d>[A-Za-z(].{24,})$")
DASH_DEF = re.compile(r"^\s*(?:[-*•]\s*)?(?P<t>[A-Z][\w'’\-]*(?:\s+[\w'’\-]+){0,4})\s+[–—]\s+(?P<d>[A-Za-z(].{24,})$")


def extract_pairs(md):
    """Return [(term, definition, raw)] mined from one lesson's markdown."""
    pairs, seen = [], set()

    def add(term, defn, raw):
        term, defn = clean_term(term), clean_defn(defn)
        if not (term_ok(term) and defn_ok(defn)):
            return
        key = (term.lower(), defn.lower()[:60])
        if key in seen:
            return
        seen.add(key)
        pairs.append((term, defn, strip_md(raw)))

    for line in re.split(r"\n", md or ""):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        candidates = [line] + ([strip_md(line)] if "**" in line else [])
        matched = False
        for cand in candidates:
            for rx in (BULLET_DEF, BULLET_DEF2, BULLET_DEF3, COLON_DEF, DASH_DEF):
                m = rx.match(cand)
                if not m:
                    continue
                d = m.group("d")
                if (m.groupdict() or {}).get("sep") in ("is", "are"):
                    d = m.groupdict()["sep"] + " " + d
                add(m.group("t"), d, line)
                matched = True
                break
            if matched:
                break
        if not matched:
            body = strip_md(re.sub(r"^[-*•]\s*", "", line))
            if "?" in body or body.endswith(":"):
                continue
            m = PROSE_DEF.search(body)
            if m and not body.lower().startswith(SKIP_START):
                add(m.group("t"), m.group("d"), body)
    return pairs


# =================================================================== the corpus
class Corpus:
    """All mined term/definition pairs of a subject, used to build distractors."""

    def __init__(self, subject_id):
        self.subject_id = subject_id
        self.by_lesson = {}
        self.unit_of = {}
        for r in db.query("""SELECT l.id lid, l.content_md md, l.title title, u.id uid, u.title utitle
                             FROM lessons l JOIN units u ON l.unit_id=u.id WHERE u.subject_id=?""",
                          (subject_id,)):
            text = r["md"] or ""
            if len(strip_md(text)) < 80 and r.get("html"):
                text = r["html"]
            self.by_lesson[r["lid"]] = [(t, d, raw, r["title"]) for t, d, raw in extract_pairs(text)]
            self.unit_of[r["lid"]] = (r["uid"], r["utitle"])
        self.prose = [(t, d, lid) for lid, ps in self.by_lesson.items() for t, d, _, _ in ps if is_prose(d)]
        self.terms = sorted({t for ps in self.by_lesson.values() for t, _, _, _ in ps})
        self.lookup = {}                      # lowercased term -> (term, definition, lesson_id)
        for lid, ps in self.by_lesson.items():
            for t, d, _, _ in ps:
                key = t.lower()
                if key not in self.lookup or (is_prose(d) and not is_prose(self.lookup[key][1])):
                    self.lookup[key] = (t, d, lid)

    def define(self, term, exclude_lesson=None):
        """Definition of a term found anywhere in the subject (used for key-terms lessons)."""
        hit = self.lookup.get(term.lower())
        if not hit:
            return None
        t, d, lid = hit
        if exclude_lesson and lid == exclude_lesson:
            return None
        return d

    def defs_for(self, lesson_id, need=3, exclude_term=None):
        """Definitions for choice options: prefer the lesson, then the unit, then subject."""
        uid = self.unit_of.get(lesson_id, (None, None))[0]
        local = [(t, d) for t, d, _, _ in self.by_lesson.get(lesson_id, []) if is_prose(d)]
        unit = [(t, d, lid) for t, d, lid in self.prose if self.unit_of.get(lid, (None,))[0] == uid
                and lid != lesson_id]
        others = [(t, d) for t, d, lid in self.prose if self.unit_of.get(lid, (None,))[0] != uid]
        picked, seen = [], set()
        for pool in (local, [(t, d) for t, d, _ in unit], others):
            for t, d in pool:
                if exclude_term and t.lower() == exclude_term.lower():
                    continue
                key = d.lower()[:40]
                if key in seen or not is_prose(d):
                    continue
                seen.add(key)
                picked.append(d)
                if len(picked) >= need:
                    return picked
        return picked if len(picked) >= need else []

    def terms_for(self, lesson_id, need=3, exclude=None):
        uid = self.unit_of.get(lesson_id, (None,))[0]
        local = [t for t, _, _, _ in self.by_lesson.get(lesson_id, [])]
        same_unit = [t for lid, ps in self.by_lesson.items() if self.unit_of.get(lid, (None,))[0] == uid
                     for t, _, _, _ in ps]
        picked, seen = [], set()
        for pool in (local, same_unit, self.terms):
            for t in pool:
                if t.lower() in seen or (exclude and t.lower() == exclude.lower()):
                    continue
                if not term_ok(t):
                    continue
                seen.add(t.lower())
                picked.append(t)
                if len(picked) >= need:
                    return picked
        return picked if len(picked) >= need else []


# ==================================================================== generation
def _tokens(s):
    s = re.sub(r"\*\*|\*|`|>", "", s or "")
    s = re.sub(r"^\s*[-*•]\s*", "", s, flags=re.M)
    return re.findall(r"[a-z0-9]+", s.lower())


def occurs_in(body_tokens, frag_tokens):
    """Word-sequence containment (markdown-, case- and punctuation-insensitive)."""
    if not frag_tokens or len(frag_tokens) > len(body_tokens):
        return False
    first = frag_tokens[0]
    n = len(frag_tokens)
    for i, tok in enumerate(body_tokens):
        if tok == first and body_tokens[i:i + n] == frag_tokens:
            return True
    return False


class LessonQuestions:
    def __init__(self, lesson, corpus):
        self.lesson = lesson
        self.lid = lesson["id"]
        self.md = lesson["content_md"] or ""
        self.corpus = corpus
        self.body_tokens = _tokens((lesson["content_md"] or "") + "\n" + (lesson.get("content_html") or ""))
        self.pairs = extract_pairs(self.md)
        self.sents = sentences(self.md)
        self.blocks = bullets(self.md)
        self.used = set()
        self.items = []

    # -- plumbing -----------------------------------------------------------
    def key(self, prompt):
        return re.sub(r"\W+", " ", strip_md(prompt).lower()).strip()[:110]

    def push(self, qtype, prompt, choices, idx, why, concept, difficulty):
        want = 2 if qtype == "tf" else 4
        if len(choices) != want or not (0 <= idx < want):
            return False
        norm = [re.sub(r"\s+", " ", str(c)).strip().lower() for c in choices]
        if len(set(norm)) != want or any(not str(c).strip() for c in choices):
            return False
        if len(norm[idx]) < 1:
            return False
        k = self.key(prompt)
        if k in self.used:
            return False
        prompt_c = re.sub(r"\*+", "", strip_md(str(prompt))).replace(" :", ":")
        prompt_c = re.sub(r"\s{2,}", " ", prompt_c).strip()
        choices_c = [re.sub(r"\s{2,}", " ", re.sub(r"\*+", "", strip_md(str(c)))).strip() for c in choices]
        why_c = re.sub(r"\s{2,}", " ", re.sub(r"\*+", "", strip_md(str(why)))).strip()
        if any(("→" in c or "↔" in c or "|" in c or "**" in c) for c in choices_c):
            return False
        if "|" in prompt_c or "**" in prompt_c:
            return False
        self.used.add(k)
        self.items.append({"qtype": qtype, "prompt": prompt_c, "choices": choices_c,
                           "answer_index": idx, "explanation": why_c, "concept": strip_md(concept)[:80],
                           "difficulty": difficulty})
        return True

    @staticmethod
    def order(correct, wrongs):
        choices = [correct] + list(wrongs)
        random.shuffle(choices)
        return choices, choices.index(correct)

    # -- validation ---------------------------------------------------------
    def in_lesson(self, text):
        """Strictly true when the text occurs in this lesson (no invented wording)."""
        return occurs_in(self.body_tokens, _tokens(text))

    def can_assert_false(self, altered, original):
        """A statement may only be marked False if the altered wording is NOT in the
        lesson while the original wording IS."""
        return self.in_lesson(original) and not self.in_lesson(altered)

    # -- strategies ---------------------------------------------------------
    def strategy_definitions(self, want):
        made = 0
        for term, defn, raw in self.pairs:
            if made >= want:
                break
            if not is_prose(defn):
                continue
            wrongs = [fit(d, 150) for d in self.corpus.defs_for(self.lid, 3, exclude_term=term)]
            if len(wrongs) < 3:
                continue
            correct = fit(defn, 150)
            if correct.lower() in [w.lower() for w in wrongs]:
                continue
            choices, idx = self.order(correct, wrongs)
            if self.push("mcq", "Which of the following best describes %s?" % term, choices, idx,
                         "%s — %s" % (term, defn), term, "Medium"):
                made += 1
        return made

    def strategy_reverse(self, want):
        made = 0
        for term, defn, raw in self.pairs:
            if made >= want:
                break
            if not is_prose(defn) or len(defn) > 220:
                continue
            wrongs = self.corpus.terms_for(self.lid, 3, exclude=term)
            if len(wrongs) < 3:
                continue
            choices, idx = self.order(term, wrongs)
            if self.push("mcq", "Which term matches this description?\n“%s”" % fit(defn, 190),
                         choices, idx, "That statement describes %s." % term, term, "Medium"):
                made += 1
        return made

    def strategy_cloze(self, want):
        made = 0
        # (a) blank the term inside its own definition
        for term, defn, raw in self.pairs:
            if made >= want:
                break
            if not re.search(re.escape(term), defn, re.I):
                continue
            blanked = re.sub(re.escape(term), "______", defn, count=1, flags=re.I)
            wrongs = self.corpus.terms_for(self.lid, 3, exclude=term)
            if len(wrongs) < 3:
                continue
            choices, idx = self.order(term, wrongs)
            if self.push("mcq", "Complete the statement from the lesson:\n“%s”" % fit(blanked, 190),
                         choices, idx, "The missing word is %s — “%s”" % (term, defn), term, "Easy"):
                made += 1
        # (b) blank a term inside any complete sentence of the lesson
        local_terms = [t for t, _, _ in self.pairs]
        for s in self.sents:
            if made >= want:
                break
            if "?" in s or len(s) > 210:
                continue
            hit = next((t for t in local_terms if re.search(r"(?<![A-Za-z])" + re.escape(t) + r"(?![A-Za-z])", s, re.I)), None)
            if not hit:
                continue
            wrongs = self.corpus.terms_for(self.lid, 3, exclude=hit)
            if len(wrongs) < 3:
                continue
            blanked = re.sub(r"(?<![A-Za-z])" + re.escape(hit) + r"(?![A-Za-z])", "______", s, count=1, flags=re.I)
            choices, idx = self.order(hit, wrongs)
            if self.push("mcq", "Complete the statement from the lesson:\n“%s”" % fit(blanked, 190),
                         choices, idx, "The lesson states: %s" % s, hit, "Easy"):
                made += 1
        return made

    def strategy_worked(self, want):
        """Lines containing a calculation -> fill in the missing value."""
        made = 0
        for line in re.split(r"\n", self.md):
            if made >= want:
                break
            line = strip_md(line).strip()
            if line.count("=") < 2 or len(line) > 220:
                continue
            if re.search(r"\b(e\.g\.|eg\.|such as|for example|i\.e\.)\b", line, re.I):
                continue
            if "↔" in line or "⇌" in line:
                continue
            nums = numbers_in(line.split("=")[-1])
            if not nums:
                continue
            answer = nums[0]
            other_nums = [n for n in numbers_in(self.md) if n != answer]
            wrongs = []
            for n in other_nums:
                if n not in wrongs:
                    wrongs.append(n)
                if len(wrongs) == 3:
                    break
            if len(wrongs) < 3:
                try:
                    base = float(re.sub(r"[^\d.]", "", answer) or 0)
                except ValueError:
                    continue
                for f, suf in ((2, ""), (0.5, ""), (10, "")):
                    cand = ("%g" % (base * f))
                    if cand and cand != answer and cand not in wrongs:
                        wrongs.append(cand)
                    if len(wrongs) == 3:
                        break
            if len(wrongs) < 3:
                continue
            num, unit = split_unit(answer)
            if not unit and line.count("=") < 3:      # a real computation must show its working or a unit
                continue
            tail = re.sub(r"(?<![\w.])" + re.escape(answer) + r"(?![\w])", "______", line, count=1)
            if "______" not in tail:
                continue
            wrongs = same_unit(wrongs, answer)
            choices, idx = self.order(answer, wrongs)
            if self.push("mcq", "Use the relationship given in this lesson and work out the missing value:\n“%s”"
                         % fit(tail, 190), choices, idx,
                         "The lesson shows: %s" % line, self.lesson["title"], "Hard"):
                made += 1
        return made

    def strategy_numbers(self, want):
        made = 0
        pool = numbers_in(self.md)
        for s in self.sents:
            if made >= want:
                break
            nums = numbers_in(s)
            if not nums or len(s) > 200 or "?" in s:
                continue
            answer = nums[0]
            wrongs = [n for n in pool if n != answer][:3]
            if len(wrongs) < 3:
                try:
                    base = float(re.sub(r"[^\d.]", "", answer) or 0)
                except ValueError:
                    continue
                for f in (2, 3, 0.5, 10):
                    cand = "%g" % (base * f)
                    if cand != answer and cand not in wrongs:
                        wrongs.append(cand)
                    if len(wrongs) == 3:
                        break
            if len(wrongs) < 3:
                continue
            blanked = re.sub(r"(?<![\w.])" + re.escape(answer) + r"(?![\w])", "______", s, count=1)
            if "______" not in blanked:
                continue
            wrongs = same_unit(wrongs, answer)
            choices, idx = self.order(answer, wrongs)
            if self.push("mcq", "Fill in the blank using this lesson:\n“%s”" % fit(blanked, 190),
                         choices, idx, "The lesson states: %s" % s, self.lesson["title"], "Hard"):
                made += 1
        return made

    def strategy_tf(self, want_true, want_false):
        t = f = 0
        for s in self.sents:
            if t >= want_true and f >= want_false:
                break
            low = s.lower()
            if "?" in s or low.startswith(SKIP_START) or "______" in s:
                continue
            if not re.match(r"^[A-Z0-9\"'(]", s) or len(s) > 220:
                continue
            if low.startswith(("note", "tip", "remember", "did you know")) or INSTRUCTION.match(s):
                continue
            if len(s) > 180:
                continue
            stmt = s.rstrip(".") + "."
            if t < want_true and self.push("tf", "True or False: %s" % stmt, ["True", "False"], 0,
                                           "Correct — the lesson states: %s" % s,
                                           self.lesson["title"], "Easy"):
                t += 1
                continue
            if f < want_false:
                nums = numbers_in(s)
                if nums and re.search(r"\d", nums[0]):
                    target = nums[0]
                    try:
                        base = float(re.sub(r"[^\d.]", "", target) or 0)
                    except ValueError:
                        continue
                    fake = "%g" % (base * random.choice([2, 3, 5, 0.5, 10]))
                    if fake != target and re.search(r"(?<![\w.])" + re.escape(target) + r"(?![\w])", s):
                        altered = re.sub(r"(?<![\w.])" + re.escape(target) + r"(?![\w])", fake, s, count=1)
                        if len(altered) > 180 or not self.can_assert_false(altered, s):
                            continue
                        if self.push("tf", "True or False: %s" % (altered.rstrip(".") + "."),
                                     ["True", "False"], 1,
                                     "False — the lesson states “%s”, not %s." % (s, fake),
                                     self.lesson["title"], "Medium"):
                            f += 1
                            continue
                local_terms = [x for x, _, _ in self.pairs if len(x) > 3]
                hit = next((x for x in local_terms if re.search(r"(?<![A-Za-z])" + re.escape(x) + r"(?![A-Za-z])", s, re.I)), None)
                if hit:
                    wrongs = self.corpus.terms_for(self.lid, 1, exclude=hit)
                    if wrongs:
                        altered = re.sub(r"(?<![A-Za-z])" + re.escape(hit) + r"(?![A-Za-z])",
                                         wrongs[0], s, count=1, flags=re.I)
                        if len(altered) > 180 or not self.can_assert_false(altered, s):
                            continue
                        if self.push("tf", "True or False: %s" % (altered.rstrip(".") + "."),
                                     ["True", "False"], 1,
                                     "False — the lesson says “%s”, not “%s”." % (s, wrongs[0]),
                                     self.lesson["title"], "Medium"):
                            f += 1
        return t, f

    def strategy_bullet_tf(self, want_true, want_false):
        """Statements taken from list items (summary boxes, key facts, revision lists)."""
        t = f = 0
        pool = [i for b in self.blocks for i in b] + [s for s in self.sents]
        for item in pool:
            if t >= want_true and f >= want_false:
                break
            item = item.strip()
            if len(item) < 22 or "?" in item or item.endswith(":"):
                continue
            if item.lower().startswith(SKIP_START) or len(item) > 180 or INSTRUCTION.match(item):
                continue
            stmt = item.rstrip(".") + "."
            if t < want_true and self.push("tf", "True or False: %s" % stmt, ["True", "False"], 0,
                                           "Correct — this lesson states: %s" % item,
                                           self.lesson["title"], "Easy"):
                t += 1
                continue
            if f < want_false:
                nums = numbers_in(item)
                if nums and re.search(r"\d", nums[0]):
                    target = nums[0]
                    try:
                        base = float(re.sub(r"[^\d.]", "", target) or 0)
                    except ValueError:
                        continue
                    fake = "%g" % (base * random.choice([2, 3, 5, 0.5]))
                    altered = re.sub(r"(?<![\w.])" + re.escape(target) + r"(?![\w])", fake, item, count=1)
                    if altered != item and len(altered) <= 180 and self.can_assert_false(altered, item) and \
                       self.push("tf", "True or False: %s" % (altered.rstrip(".") + "."),
                                                     ["True", "False"], 1,
                                                     "False — the lesson states “%s”, not %s." % (item, fake),
                                                     self.lesson["title"], "Medium"):
                        f += 1
                        continue
                local_terms = [x for x, _, _ in self.pairs if len(x) > 3]
                hit = next((x for x in local_terms if re.search(r"(?<![A-Za-z])" + re.escape(x) + r"(?![A-Za-z])", item, re.I)), None)
                if hit:
                    wrongs = self.corpus.terms_for(self.lid, 1, exclude=hit)
                    if wrongs:
                        altered = re.sub(r"(?<![A-Za-z])" + re.escape(hit) + r"(?![A-Za-z])", wrongs[0], item, count=1, flags=re.I)
                        if len(altered) > 180 or not self.can_assert_false(altered, item):
                            continue
                        if self.push("tf", "True or False: %s" % (altered.rstrip(".") + "."),
                                     ["True", "False"], 1,
                                     "False — the lesson says “%s”, not “%s”." % (item, wrongs[0]),
                                     self.lesson["title"], "Medium"):
                            f += 1
        return t, f

    def keyterm_list(self):
        """Term-only lessons: "Key Terms" lists written as comma/bullet separated words."""
        terms, lines = [], [l.strip() for l in re.split(r"\n", self.md or "") if l.strip()]
        for line in lines:
            line = re.sub(r"^[-*•]\s*", "", line)
            line = re.sub(r"^#+\s*", "", line)
            if line.endswith(":") or len(line) < 8:
                continue
            for part in re.split(r"[,;•]|\s{3,}", line):
                t = clean_term(part)
                # a key-term entry is a noun phrase - not a clause and not a broken fragment
                if not term_ok(t) or len(t.split()) > 4:
                    continue
                if re.search(r"\b(is|are|was|were|has|have|provides?|gives?|means|includes?|refers?)\b", t, re.I):
                    continue
                if re.match(r"^[a-z]", t) or t.endswith(("nour", "pro", "con")) and len(t) < 8:
                    continue
                terms.append(t)
        out, seen = [], set()
        for t in terms:
            if t.lower() in seen:
                continue
            seen.add(t.lower())
            out.append(t)
        if len(out) < 8:
            return []
        looks_like_list = (len(self.sents) <= 4) or ("key term" in self.lesson["title"].lower())
        if "key term" not in self.lesson["title"].lower() and len(self.sents) > 4:
            return []
        avg_len = sum(len(t) for t in out) / len(out)
        return out if looks_like_list and avg_len <= 30 else []

    def strategy_keyterms(self, want):
        terms = self.keyterm_list()
        if len(terms) < 5:
            return 0
        made = 0
        # (a) definition lookup: "which term matches this description?"
        for t in list(terms):
            if made >= want:
                break
            d = self.corpus.define(t, exclude_lesson=self.lid) or self.corpus.define(t)
            if not d or not defn_ok(d):
                continue
            wrongs = [x for x in terms if x.lower() != t.lower()]
            if len(wrongs) < 3:
                continue
            wrongs = random.sample(wrongs, 3)
            choices, idx = self.order(t, wrongs)
            if self.push("mcq", "Which term matches this description?\n“%s”" % fit(d, 190), choices, idx,
                         "%s — %s" % (t, d), t, "Medium"):
                made += 1
        # (b) which term belongs to this unit's key terms (recognition)
        for t in list(terms):
            if made >= want:
                break
            others = self.corpus.terms_for(self.lid, 12)
            outsiders = [x for x in others if x.lower() not in {y.lower() for y in terms}]
            if len(outsiders) < 3:
                continue
            choices, idx = self.order(t, random.sample(outsiders, 3))
            if self.push("mcq", "Which of the following is one of the key terms introduced in this lesson?",
                         choices, idx, "“%s” is listed in the key terms of this lesson." % t,
                         self.lesson["title"], "Easy"):
                made += 1
        return made

    def strategy_keyterm_tf(self, want):
        terms = self.keyterm_list()
        made = 0
        for t in terms:
            if made >= want:
                break
            if not self.in_lesson(t):
                continue
            if self.push("tf", "True or False: “%s” is one of the key terms of this lesson." % t,
                         ["True", "False"], 0,
                         "Correct — “%s” appears in this lesson's key terms." % t,
                         self.lesson["title"], "Easy"):
                made += 1
        others = [x for x in self.corpus.terms_for(self.lid, 30)
                  if x.lower() not in {y.lower() for y in terms} and not self.in_lesson(x)]
        for t in others:
            if made >= want:
                break
            if self.push("tf", "True or False: “%s” is one of the key terms of this lesson." % t,
                         ["True", "False"], 1,
                         "False — “%s” is not in this lesson's key-term list." % t,
                         self.lesson["title"], "Medium"):
                made += 1
        return made

    def strategy_altered_mcq(self, want):
        """A statement from the lesson as the only correct option; the other options are
        the same statement with one value or term changed, so they are certainly false."""
        made = 0
        local_terms = [t for t, _, _ in self.pairs if len(t) > 3]
        for st in self.sents:
            if made >= want:
                break
            if "?" in st or len(st) > 190 or "______" in st:
                continue
            variants = []
            for target in numbers_in(st)[:3]:
                num, unit = split_unit(target)
                try:
                    base = float(re.sub(r"[^\d.]", "", num) or 0)
                except ValueError:
                    continue
                if base == 0:
                    continue
                fake = "%g" % (base * random.choice([2, 3, 4, 5, 0.5]))
                if fake == num:
                    continue
                alt = st.replace(target, ("%s %s" % (fake, unit)).strip() if unit else fake)
                if alt != st:
                    variants.append(alt)
            if len(variants) < 3 and local_terms:
                hit = next((t for t in local_terms if re.search(r"(?<![A-Za-z])" + re.escape(t) + r"(?![A-Za-z])", st, re.I)), None)
                if hit:
                    for other in self.corpus.terms_for(self.lid, 4, exclude=hit):
                        alt = re.sub(r"(?<![A-Za-z])" + re.escape(hit) + r"(?![A-Za-z])", other, st, count=1, flags=re.I)
                        if alt != st:
                            variants.append(alt)
                        if len(variants) >= 3:
                            break
            if len(variants) < 3:
                continue
            wrongs = []
            for v in variants:
                v = fit(v, 160)
                if v.lower() != fit(st, 160).lower() and v not in wrongs:
                    wrongs.append(v)
                if len(wrongs) == 3:
                    break
            if len(wrongs) < 3:
                continue
            if not self.in_lesson(st):
                continue
            wrongs = [w for w in wrongs if not self.in_lesson(w)]
            if len(wrongs) < 3:
                continue
            choices, idx = self.order(fit(st, 160), wrongs)
            if self.push("mcq", "According to this lesson, which statement is correct?", choices, idx,
                         "The lesson states: %s. The other options change a value or term from the lesson." % st,
                         self.lesson["title"], "Medium"):
                made += 1
        return made

    def strategy_list(self, want):
        made = 0
        for block in self.blocks:
            if made >= want:
                break
            items = block
            if len(items) < 4:
                continue
            picked = random.sample(items, 3)
            block_low = " ".join(items).lower()
            outsiders = [t for t in self.corpus.terms_for(self.lid, 25)
                         if t.lower() not in block_low and not any(t.lower() in p.lower() for p in picked)]
            if not outsiders:
                continue
            outsider = outsiders[0]
            correct = fit(outsider, 110)
            wrongs = [fit(p, 110) for p in picked]
            choices, idx = self.order(correct, wrongs)
            if self.push("mcq", "All of the following are listed in this lesson EXCEPT:", choices, idx,
                         "“%s” is not part of that list in the lesson." % correct,
                         self.lesson["title"], "Hard"):
                made += 1
        return made

    # -- assembly -----------------------------------------------------------
    def build(self, need):
        if need <= 0:
            return []
        # ~3 true/false items per lesson, the rest spread over the other strategies
        want_tf = 3 if need >= 6 else max(1, need // 3)
        self.strategy_tf(max(1, want_tf - 1), max(1, want_tf - 2))
        plan = [("strategy_definitions", 3), ("strategy_cloze", 2), ("strategy_reverse", 1),
                ("strategy_numbers", 2), ("strategy_worked", 2), ("strategy_altered_mcq", 2),
                ("strategy_bullet_tf", 2), ("strategy_list", 1), ("strategy_keyterms", 3),
                ("strategy_keyterm_tf", 3), ("strategy_definitions", 5),
                ("strategy_cloze", 4), ("strategy_altered_mcq", 4), ("strategy_reverse", 3),
                ("strategy_numbers", 4), ("strategy_worked", 3)]
        for name, cap in plan:
            if len(self.items) >= need:
                break
            fn = getattr(self, name)
            if name == "strategy_bullet_tf":
                fn(2, 2)
            else:
                fn(cap)
        # top up from every remaining source until the lesson has its full set
        for _ in range(4):
            if len(self.items) >= need:
                break
            before = len(self.items)
            self.strategy_bullet_tf(3, 3)
            self.strategy_keyterms(4)
            self.strategy_keyterm_tf(4)
            self.strategy_altered_mcq(3)
            self.strategy_cloze(4)
            self.strategy_numbers(4)
            self.strategy_reverse(4)
            self.strategy_definitions(4)
            self.strategy_worked(3)
            self.strategy_list(2)
            if len(self.items) == before:
                break
        return self.items[:need]


# ==================================================================== DB layer
def ensure_flashcards(lesson_id, md, limit=12):
    have = db.query("SELECT count(*) n FROM flashcards WHERE lesson_id=?", (lesson_id,), one=True)["n"]
    if have:
        return 0
    made, seen = 0, set()
    for term, defn, raw in extract_pairs(md):
        if made >= limit or term.lower() in seen:
            continue
        seen.add(term.lower())
        db.execute("INSERT INTO flashcards(lesson_id,front,back,sort) VALUES(?,?,?,?)",
                   (lesson_id, term, fit(defn, 230), made))
        made += 1
    return made


def scrub_flashcards():
    """Repair flashcard text left with stray markdown markers (e.g. a lone '*')."""
    fixed = 0
    for r in db.query("SELECT id, front, back FROM flashcards WHERE front LIKE '%*%' OR back LIKE '%*%'"):
        f, b = strip_md(r["front"]).replace("*", "").strip(), strip_md(r["back"]).replace("*", "").strip()
        if (f, b) != (r["front"], r["back"]):
            db.execute("UPDATE flashcards SET front=?, back=? WHERE id=?", (f, b, r["id"]))
            fixed += 1
    return fixed


def build_lesson(lesson_id, n=10, corpus=None, verbose=False):
    lesson = db.query("SELECT id,unit_id,title,content_md,content_html FROM lessons WHERE id=?",
                      (lesson_id,), one=True)
    if not lesson:
        return {"lesson": lesson_id, "added": 0, "kept": 0, "total": 0, "flashcards": 0}
    unit = db.query("SELECT subject_id FROM units WHERE id=?", (lesson["unit_id"],), one=True)
    subject_id = unit["subject_id"] if unit else None
    md = lesson["content_md"] or ""
    if len(strip_md(md)) < 80:                     # html-only lesson
        try:
            import notes_import
            md = notes_import.html_to_md(lesson["content_html"] or "")
        except Exception:
            md = strip_md(lesson["content_html"] or "")
        lesson["content_md"] = md

    kept = db.query("SELECT count(*) n FROM questions WHERE scope='lesson' AND lesson_id=? AND status='Approved'",
                    (lesson_id,), one=True)["n"]
    db.execute("DELETE FROM questions WHERE scope='lesson' AND lesson_id=? AND status!='Approved'", (lesson_id,))
    need = max(0, n - kept)
    corpus = corpus or Corpus(subject_id)
    items = LessonQuestions(lesson, corpus).build(need) if need else []
    for i, q in enumerate(items):
        db.execute("""INSERT INTO questions(scope,lesson_id,subject_id,qtype,prompt,choices,answer,
                      answer_index,explanation,difficulty,concept,status,sort,created_at)
                      VALUES('lesson',?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                   (lesson_id, subject_id, q["qtype"], q["prompt"], json.dumps(q["choices"], ensure_ascii=False),
                    q["choices"][q["answer_index"]], q["answer_index"], q["explanation"], q["difficulty"],
                    q["concept"], "AI Generated", kept + i, db.now()))
    fc = ensure_flashcards(lesson_id, md)
    if verbose:
        for q in items:
            print("\n  [%s / %s] %s" % (q["qtype"], q["difficulty"], q["prompt"]))
            for j, c in enumerate(q["choices"]):
                print("      %s %s%s" % ("▶" if j == q["answer_index"] else " ", "ABCD"[j], fit(c, 120)))
            print("      why: %s" % fit(q["explanation"], 150))
    return {"lesson": lesson_id, "added": len(items), "kept": kept, "total": kept + len(items),
            "flashcards": fc}


def build_scope(where="", params=(), n=10, limit=None, quiet=False):
    sql = "SELECT id FROM lessons" + (" WHERE " + where if where else "") + " ORDER BY id"
    if limit:
        sql += " LIMIT %d" % limit
    rows = db.query(sql, params)
    corp, stats = {}, {"lessons": 0, "full": 0, "short": 0, "questions": 0, "flashcards": 0, "worst": []}
    for i, r in enumerate(rows, 1):
        u = db.query("SELECT subject_id FROM units WHERE id=(SELECT unit_id FROM lessons WHERE id=?)",
                     (r["id"],), one=True)
        sid = u["subject_id"] if u else None
        if sid not in corp:
            corp[sid] = Corpus(sid)
        res = build_lesson(r["id"], n=n, corpus=corp[sid])
        stats["lessons"] += 1
        stats["questions"] += res["added"]
        stats["flashcards"] += res["flashcards"]
        if res["total"] >= n:
            stats["full"] += 1
        else:
            stats["short"] += 1
            stats["worst"].append((res["total"], r["id"]))
        if not quiet and i % 100 == 0:
            print("   ... %d/%d lessons" % (i, len(rows)))
    stats["worst"].sort()
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grade", default="")
    ap.add_argument("--subject", type=int)
    ap.add_argument("--lesson", type=int)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--report", action="store_true", help="print per-lesson counts")
    ap.add_argument("--scrub", action="store_true", help="repair flashcard text and exit")
    args = ap.parse_args()
    db.init_db()
    if args.scrub:
        print("flashcards repaired:", scrub_flashcards())
        return
    if args.lesson:
        print("Lesson", args.lesson)
        print(build_lesson(args.lesson, n=args.n, verbose=True))
        return
    where, params = "", ()
    if args.subject:
        where, params = "unit_id IN (SELECT id FROM units WHERE subject_id=?)", (args.subject,)
    elif args.grade:
        grades = [int(x) for x in re.findall(r"\d+", args.grade)]
        where = ("unit_id IN (SELECT u.id FROM units u JOIN subjects s ON u.subject_id=s.id WHERE s.grade IN (%s))"
                 % ",".join("?" * len(grades)))
        params = tuple(grades)
    st = build_scope(where, params, n=args.n, limit=args.limit)
    print("Lessons: %d  |  with %d questions: %d  |  fewer: %d  |  new questions: %d  |  flashcards: %d"
          % (st["lessons"], args.n, st["full"], st["short"], st["questions"], st["flashcards"]))
    if st["short"]:
        print("Lessons below %d (id:count): %s" % (args.n, ", ".join("%d:%d" % (i, c) for c, i in st["worst"][:20])))
    if args.report:
        for r in db.query("""SELECT l.id, l.title, count(q.id) n FROM lessons l
                             LEFT JOIN questions q ON q.lesson_id=l.id AND q.scope='lesson'
                             GROUP BY l.id ORDER BY n, l.id"""):
            flag = "" if r["n"] >= args.n else "   <-- short"
            print("%5d  %-62s %3d%s" % (r["id"], r["title"][:62], r["n"], flag))


if __name__ == "__main__":
    main()
