# 📱 Publishing EduLearn — two ways, pick one (or both)

Everything is built, tested and pushed. These are the only steps left, and they are yours
because they need your GitHub/Render login.

---

## Which one do you want?

| | **A. GitHub Pages** | **B. Render** |
|---|---|---|
| Gives students | Reading + quizzes + flashcards | **Everything** |
| Registration / login | ❌ no | ✅ yes |
| Ask-your-notes tutor | ❌ no | ✅ yes |
| Certificates | ❌ no | ✅ yes |
| Cost | Free | Free tier |
| Setup time | ~1 minute | ~5 minutes |
| Best for | Sharing the notes with everyone | A real working platform |

**My advice:** turn on Pages first (it's one minute and needs no account anywhere else).
Then do Render when you want the full app with logins and certificates.

---

## A. GitHub Pages — the notes, readable on any phone

1. On your phone or laptop, open:

   **github.com/YaredwebDev/edulearn-platform/settings/pages**

2. Under **Branch**, choose **`arena/01a0b4b5-edulearn-platform`**.
3. Set the folder to **`/docs`**.
4. Press **Save**.
5. Wait about a minute. Then open:

   **https://yaredwebdev.github.io/edulearn-platform/**

That's it. Students can read all **839 lessons** across 15 subjects, take the 10-question
quiz at the end of each lesson, and flip the flashcards. It works on any phone and needs
no login.

> Nothing else to do — every time I push, Pages updates itself.

---

## B. Render — the full platform (logins, tutor, certificates)

1. Create a free account at **render.com** (sign in with GitHub — easiest).
2. Go to **dashboard.render.com/blueprints**.
3. Click **New Blueprint Instance**, then pick the **`edulearn-platform`** repository.
4. Render reads `render.yaml` from the repo and fills everything in — just press **Apply**.
5. Wait ~3 minutes for the first build. Render gives you a link like
   **https://edulearn.onrender.com**.

That link is the real platform:

- students register with a name, grade, phone number and password
- lessons, flashcards and 10-question quizzes
- **Ask** — the tutor that answers only from your notes, with citations
- **⬇ Download the notes** on every subject page
- final exam (125 questions), certificate at 100/125, and a public certificate checker

### Two honest warnings about the free tier

- **It sleeps.** After 15 minutes of no visitors the app takes ~50 seconds to wake up.
  The first student of the day waits a moment. Paid tier removes this.
- **Data resets on redeploy.** The free tier wipes the disk, so student accounts and
  certificates can be lost when you push new code. The lesson content is safe (it lives in
  `platform.db`, which is part of the repo) — it's only student records that are at risk.
  For real use, I'd move the database to a proper hosted Postgres. Say the word.

### Optional: make the tutor smarter

The tutor already works with no API key — it quotes your notes and cites the lesson.
If you later want it to *rewrite* those quotes into smoother sentences, add one environment
variable in Render (**Environment** tab):

```
CHAT_PROVIDER = gemini
GEMINI_API_KEY = <your free key from aistudio.google.com>
```

`groq` and `openai` work the same way with `GROQ_API_KEY` / `OPENAI_API_KEY`.
Citations and the "not covered in your notes" rule stay exactly as they are either way.

---

## What is finished

| Part | Status |
|---|---|
| 9 notes files imported (Grades 9 & 10) | ✅ |
| Grade 11 content (5 subjects) | ✅ |
| 839 lessons, split by textbook topic | ✅ |
| 10 questions per lesson | ✅ **838 of 839** |
| Flashcards | ✅ 4,187 across 807 lessons |
| Ask-your-notes tutor | ✅ tested |
| Download-the-notes | ✅ tested |
| Final exam (125 questions) | ✅ tested |
| Certificate + public verification | ✅ tested |

## The three things I could not finish

1. **Grade 12 is empty.** Registration now says "12 (content coming soon)" and a Grade 12
   student sees a friendly explanation instead of a blank page. Send me Grade 12 notes and
   I'll build it the same way.
2. **One lesson has 9 questions instead of 10** — *10.7 Environmental impact of mineral
   exploitation*, which is 523 characters long. There isn't a tenth honest question in it.
3. **Physics Grade 10** still uses its original content — no notes were uploaded for it.
