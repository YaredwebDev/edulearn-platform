# EduLearn — where things stand

_Yaarad, this page is written to be read on your phone. No code inside._

---

## Opening the platform on your phone

The chat preview panel can't render on a phone, and file attachments never reach me.
So there are two ways for you to actually see and use the platform:

### 1. The one-click way (needs one action from you)

Turn on GitHub Pages once, and your platform gets a real web address:

1. Open **github.com/YaredwebDev/edulearn-platform/settings/pages**
2. Under **Branch**, choose **`arena/01a0b4b5-edulearn-platform`**
3. Set the folder to **`/docs`** → press **Save**
4. Wait about a minute, then open **https://yaredwebdev.github.io/edulearn-platform/**

That link works on any phone, forever, and updates whenever I push.

### 2. The link that needs no setup at all

**https://raw.githack.com/YaredwebDev/edulearn-platform/arena/01a0b4b5-edulearn-platform/docs/preview.html**

This one shows the whole course in a single page. I couldn't test it from my side
(the sandbox blocks that website), so if it shows you code instead of a page, use
option 1 — that one is guaranteed to work.

---

## What is built right now

| Part | Status |
|---|---|
| Your 9 notes files imported | ✅ Done |
| Lessons split by textbook topic | ✅ Done |
| 10 questions per lesson | ✅ 861 of 873 lessons |
| Flashcards per lesson | ✅ Done |
| **Ask your notes (AI tutor)** | ✅ **Just built** |
| **Download the notes** | ✅ **Just built** |
| Phone-friendly static site | ✅ 891 pages |
| Chatbot grounded in notes | ✅ Done, with citations |

## What a student does

1. Registers with phone number and password (no email needed).
2. Picks their grade, then a subject.
3. Opens the first lesson and reads it.
4. Answers 10 questions — 80% passes the lesson.
5. Moves to the next lesson.
6. After all subjects, sits the final exam (125 questions) for a certificate.

## The two new features

### Ask your notes

There's now an **Ask** button in the top menu. A student types a question and gets an
answer taken **only from the notes**, with the lesson it came from listed underneath.

- Ask *"what is the scientific method"* → answers from **1.3 The Scientific Method**
- Ask *"how do I bake injera"* → *"That is not covered in your notes."*

That second part matters: it **never makes things up**. If your notes don't cover
something, it says so instead of guessing. It works offline with no API key — and if you
later want smoother wording, setting a `CHAT_PROVIDER` environment variable plugs in
Gemini, Groq or OpenAI on top of the same retrieved material.

### Download the notes

Every subject page now has **“⬇ Download the notes”**, which hands the student the
original notes file for that subject and grade.

---

## Things you should know

**12 lessons have fewer than 10 questions.** The thinnest is *"5.6 Designing Simple
Machine"* — it is one 245-character instruction, so there is only one fact in it. I gave
it 3 questions instead of padding it with 10 copies. Tell me if you'd rather have 10.

**Grade 12 has no content at all.** Registration accepts Grade 12, but there are no
lessons, so a Grade 12 student sees an empty dashboard. Either send me Grade 12 notes or
I can hide Grade 12 from registration.

**Physics Grade 10 has no notes.** I left its existing 57 lessons in place.

**Your notes are safe.** Before every import the database is backed up
(`platform.db.prenotes-backup`), and each lesson body is stored exactly as you wrote it.

---

## What I would do next

1. You switch on GitHub Pages (one minute) so you can finally see it.
2. Send Grade 12 notes, or tell me to hide Grade 12.
3. Say the word and I'll add a per-subject PDF download with a proper cover page.
