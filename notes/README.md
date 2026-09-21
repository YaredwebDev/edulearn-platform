# 📥 Put your notes here

**Chat attachments never reach me** (that's why `Biology_Grade10_Structured.html` didn't
arrive). This folder is the reliable route, and it works from a phone.

---

## ✅ Easiest way — upload here (works on a phone)

**Tap this link:**

> ### https://github.com/YaredwebDev/edulearn-platform/upload/arena/01a0b4b5-edulearn-platform

1. Sign in to GitHub if asked (free account).
2. Tap **choose your files** → pick your notes from your phone (Files, Downloads, Drive…).
   You can pick several at once.
3. Scroll to the bottom → tap **Commit changes**.
   - Make sure it says **"Commit directly to the `arena/01a0b4b5-edulearn-platform` branch"**.
4. Come back here and say **"uploaded"**.

That's it — I do the rest and show you the full lesson breakdown before anything changes.

### If the file picker is awkward on your phone

On the repo page, switch the branch dropdown to **`arena/01a0b4b5-edulearn-platform`**,
open the **`notes`** folder, then **Add file → Upload files**.

---

## Accepted formats

| Format | Notes |
|---|---|
| `.html` | what you already have (`Biology_Grade10_Structured.html`) — ideal |
| `.md` / `.txt` | plain text or Markdown |
| `.docx` | Word documents |
| `.zip` | **a whole folder in one file** — best if you have many files. I unpack it and sort out each subject/grade. |

**Grade and subject are read from the file name**, so keep both in it:

```
Biology_Grade9_Structured.html      Chemistry_Grade10_Structured.html
Biology_Grade10_Structured.html     Physics_Grade9_Structured.html
English_Grade9_Structured.html      Mathematics_Grade10_Structured.html
```

Inside a `.zip`, the name of each file inside is what counts.
Not sure of the naming? Just upload it — I'll tell you what I read from it.

---

## Alternative: just paste it into the chat

If your notes are plain text (not a file), **paste them straight into the chat message**.
Text always reaches me, even though attachments don't. For long notes, send it in a few
parts ("part 1 of 3"…) and I'll join them together.

## Alternative: give me a public link

Any **public** link works — a raw GitHub link, a public Google Doc set to
"anyone with the link", a hosted PDF. Paste the link and I'll fetch it.

---

## What I do with the notes

```
python3 notes_import.py --notes notes --preview   # shows every unit + lesson, writes nothing
python3 build_course.py --notes notes             # backup → import → 10 questions/lesson → report
```

* the full unit → lesson breakdown is printed for review **before** anything is written
* thin/duplicate/empty lessons are flagged, so nothing half-parsed gets published
* every lesson body is kept **verbatim**; summary and "quick revision" boxes kept as lessons
* 10 questions per lesson generated from each lesson's own text
* student progress carries across the content swap lesson-by-lesson

## Making them downloadable

Once your notes are in, I'll also make them **downloadable** from the platform, as you asked.
