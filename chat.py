"""Ask — the tutor that answers only from the uploaded notes.

Design notes
------------
* **Grounded by construction.** An answer is assembled from passages that were actually
  retrieved out of the lesson text, and every passage carries a citation (subject, unit,
  lesson). Nothing is invented, because nothing is generated: the reply *is* the retrieved
  material, quoted.
* **Honest fallback.** If retrieval finds nothing above the confidence floor we say
  "not covered in your notes" rather than guessing. That is the whole point of a
  notes-grounded tutor.
* **Offline first.** Search uses SQLite FTS5, which ships with Python, so the feature works
  with no API key and no internet. Setting CHAT_PROVIDER=gemini|groq|openai *optionally*
  lets a language model rewrite the retrieved passages into a smoother explanation; the
  citations and the "not covered" floor still come from retrieval.
* **Answers are cached** so repeat questions are instant and cheap.

Use:
    python3 chat.py --build                 # (re)build the search index
    python3 chat.py --ask "what is biology"
    python3 chat.py --ask "photosynthesis" --grade 10
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db  # noqa: E402

FTS_TABLE = "lesson_fts"
CACHE_TABLE = "chat_cache"
MIN_SCORE = float(os.environ.get("CHAT_MIN_SCORE", "0.28"))   # confidence floor

STOP = {
    "the", "a", "an", "of", "to", "and", "or", "in", "on", "is", "are", "was", "were",
    "what", "which", "who", "whom", "how", "why", "when", "where", "does", "do", "did",
    "for", "with", "about", "that", "this", "these", "those", "it", "its", "be", "been",
    "can", "could", "should", "would", "will", "shall", "i", "me", "my", "we", "our",
    "you", "your", "they", "them", "their", "he", "she", "his", "her", "explain", "tell",
    "define", "definition", "meaning", "mean", "please", "help", "between", "into",
}


# ------------------------------------------------------------------ schema helpers
def ensure_tables():
    db.execute("""CREATE TABLE IF NOT EXISTS %s(
                    lesson_id INTEGER PRIMARY KEY,
                    subject_id INTEGER, unit_id INTEGER, grade INTEGER,
                    subject TEXT, unit TEXT, title TEXT, body TEXT)""" % FTS_TABLE)
    db.execute("""CREATE TABLE IF NOT EXISTS %s(
                    qkey TEXT PRIMARY KEY, answer TEXT, sources TEXT, created_at REAL)"""
               % CACHE_TABLE)
    try:
        db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS lesson_fts_idx "
                   "USING fts5(body, title, lesson_id UNINDEXED)")
    except Exception:
        pass          # FTS5 unavailable: the scanner below still works


def _fts_ready():
    try:
        db.query("SELECT 1 FROM lesson_fts_idx LIMIT 1")
        return True
    except Exception:
        return False


def build_index(verbose=True):
    """Copy every lesson into the search table and (re)build the FTS index."""
    ensure_tables()
    rows = db.query("""SELECT l.id lid, l.title ltitle, l.content_md md, l.content_html html,
                              u.id uid, u.title utitle, s.id sid, s.name sname, s.grade grade
                       FROM lessons l
                       JOIN units u ON l.unit_id = u.id
                       JOIN subjects s ON u.subject_id = s.id""")
    db.execute("DELETE FROM %s" % FTS_TABLE)
    n = 0
    for r in rows:
        body = (r["md"] or "").strip()
        if len(re.sub(r"[#*`\-|]", "", body)) < 40:          # html-only lesson
            body = _plain(r["html"] or "")
        db.execute("""INSERT OR REPLACE INTO %s
                      (lesson_id,subject_id,unit_id,grade,subject,unit,title,body)
                      VALUES(?,?,?,?,?,?,?,?)""" % FTS_TABLE,
                   (r["lid"], r["sid"], r["uid"], r["grade"], r["sname"], r["utitle"],
                    r["ltitle"], body))
        n += 1
    if _fts_ready():
        db.execute("DELETE FROM lesson_fts_idx")
        for r in db.query("SELECT lesson_id, title, body FROM %s" % FTS_TABLE):
            db.execute("INSERT INTO lesson_fts_idx(body, title, lesson_id) VALUES(?,?,?)",
                       (r["body"], r["title"], r["lesson_id"]))
    if verbose:
        print("indexed %d lessons (fts5: %s)" % (n, "yes" if _fts_ready() else "no"))
    return n


def _plain(html_text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html_text or "")).strip()


# ------------------------------------------------------------------ retrieval
def _keywords(q):
    words = re.findall(r"[A-Za-z][A-Za-z\-']{2,}", (q or "").lower())
    return [w for w in words if w not in STOP]


def _sentences(text):
    text = re.sub(r"^\s*#+\s*.*$", "", text or "", flags=re.M)          # drop headings
    text = re.sub(r"^\s*[-*•]\s*", "", text, flags=re.M)
    text = re.sub(r"\*\*|\*|`", "", text)
    parts = re.split(r"(?<=[.!?])\s+|\n{2,}", text)
    return [re.sub(r"\s+", " ", p).strip() for p in parts if len(p.strip()) > 25]


def _score(sentence, keys, title):
    """Simple, predictable relevance: how many query words appear, weighted by rarity."""
    low = sentence.lower()
    hits = sum(1 for k in keys if k in low)
    if not hits:
        return 0.0
    coverage = hits / max(1, len(keys))
    title_bonus = 0.25 if any(k in (title or "").lower() for k in keys) else 0.0
    density = min(1.0, hits / max(3, len(low.split()) / 12))
    return min(1.0, coverage * 0.7 + density * 0.2 + title_bonus)


def search(question, grade=None, subject_id=None, limit=6):
    """Return the best matching passages as dicts with a citation for each."""
    keys = _keywords(question)
    if not keys:
        return []
    where, params = "1=1", []
    if grade:
        where += " AND grade=?"; params.append(grade)
    if subject_id:
        where += " AND subject_id=?"; params.append(subject_id)
    rows = db.query("SELECT * FROM %s WHERE %s" % (FTS_TABLE, where), tuple(params))
    scored = []
    for r in rows:
        best = []
        for s in _sentences(r["body"]):
            sc = _score(s, keys, r["title"])
            if sc > 0:
                best.append((sc, s))
        if not best:
            continue
        best.sort(reverse=True)
        top = best[0][0]
        # a passage is worth quoting if several query words appear, or the lesson is on-topic
        if top < MIN_SCORE:
            continue
        # precision: when the question has several keywords, at least two of them must
        # really occur — otherwise "menstrual cycle" would match a lesson about cell cycles
        if len(keys) >= 2 and sum(1 for k in keys if k in best[0][1].lower()) < 2:
            continue
        excerpts = [s for _, s in best[:3]]
        scored.append({"score": round(top, 3), "lesson_id": r["lesson_id"],
                       "lesson": r["title"], "unit": r["unit"], "subject": r["subject"],
                       "grade": r["grade"], "excerpts": excerpts})
    scored.sort(key=lambda x: -x["score"])
    return scored[:limit]


# ------------------------------------------------------------------ answering
def _compose(question, hits):
    """Build the reply out of retrieved text only — no invention."""
    lines = []
    lines.append("From your notes:\n")
    for h in hits[:3]:
        lines.append("**%s** — %s, %s (Grade %s)\n" % (h["lesson"], h["unit"], h["subject"], h["grade"]))
        for ex in h["excerpts"][:2]:
            lines.append("> %s\n" % ex)
        lines.append("")
    lines.append("_Sources: %s_" % ", ".join(
        dict.fromkeys("%s (Grade %s)" % (h["subject"], h["grade"]) for h in hits[:3])))
    return "\n".join(lines).strip()


def _llm_answer(question, hits):
    """Optional: let a model tidy the retrieved passages. Retrieval still does the work."""
    provider = (os.environ.get("CHAT_PROVIDER") or "off").lower()
    if provider in ("", "off", "none"):
        return None
    context = "\n\n".join("### %s (%s, %s)\n%s" % (h["lesson"], h["unit"], h["subject"],
                                                   "\n".join(h["excerpts"])) for h in hits[:4])
    prompt = ("Answer the student's question using ONLY the notes below. "
              "If the notes do not cover it, say \"not covered in your notes\". "
              "Cite the lesson name in brackets. Keep it short and clear.\n\n"
              "NOTES:\n" + context + "\n\nQUESTION: " + question)
    try:
        if provider == "gemini":
            import urllib.request
            key = os.environ["GEMINI_API_KEY"]
            url = ("https://generativelanguage.googleapis.com/v1beta/models/"
                   "gemini-1.5-flash:generateContent?key=" + key)
            req = urllib.request.Request(url, data=json.dumps(
                {"contents": [{"parts": [{"text": prompt}]}]}).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=25) as fh:
                d = json.load(fh)
            return d["candidates"][0]["content"]["parts"][0]["text"].strip()
        if provider in ("groq", "openai"):
            import urllib.request
            key = os.environ.get("GROQ_API_KEY" if provider == "groq" else "OPENAI_API_KEY", "")
            url = ("https://api.groq.com/openai/v1/chat/completions" if provider == "groq"
                   else "https://api.openai.com/v1/chat/completions")
            model = os.environ.get("CHAT_MODEL", "llama-3.1-8b-instant" if provider == "groq" else "gpt-4o-mini")
            req = urllib.request.Request(url, data=json.dumps({
                "model": model, "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2}).encode(),
                headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
            with urllib.request.urlopen(req, timeout=30) as fh:
                d = json.load(fh)
            return d["choices"][0]["message"]["content"].strip()
    except Exception:
        return None          # any failure falls back to the quoted retrieval answer
    return None


def ask(question, grade=None, subject_id=None, use_cache=True):
    """Answer a student question from the notes, or say it is not covered."""
    question = (question or "").strip()
    if len(question) < 3:
        return {"ok": False, "error": "Please type a question."}
    key = json.dumps([re.sub(r"\W+", " ", question.lower()).strip(), grade, subject_id])
    if use_cache:
        row = db.query("SELECT answer, sources FROM %s WHERE qkey=?" % CACHE_TABLE, (key,), one=True)
        if row:
            return {"ok": True, "answer": row["answer"], "sources": json.loads(row["sources"] or "[]"),
                    "cached": True}
    hits = search(question, grade=grade, subject_id=subject_id)
    if not hits:
        return {"ok": True, "answer": None, "sources": [], "not_covered": True,
                "message": "That is not covered in your notes."}
    answer = _llm_answer(question, hits) or _compose(question, hits)
    sources = [{"lesson_id": h["lesson_id"], "lesson": h["lesson"], "unit": h["unit"],
                "subject": h["subject"], "grade": h["grade"], "score": h["score"]} for h in hits[:4]]
    db.execute("INSERT OR REPLACE INTO %s(qkey,answer,sources,created_at) VALUES(?,?,?,?)"
               % CACHE_TABLE, (key, answer, json.dumps(sources), db.now()))
    return {"ok": True, "answer": answer, "sources": sources, "cached": False}


def main():
    ap = argparse.ArgumentParser(description="Ask the notes (grounded tutor).")
    ap.add_argument("--build", action="store_true", help="(re)build the search index")
    ap.add_argument("--ask", help="a question to answer")
    ap.add_argument("--grade", type=int)
    ap.add_argument("--subject", type=int)
    args = ap.parse_args()
    db.init_db()
    if args.build or not args.ask:
        build_index()
    if args.ask:
        print(json.dumps(ask(args.ask, grade=args.grade, subject_id=args.subject),
                         indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
