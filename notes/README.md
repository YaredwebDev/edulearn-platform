# 📥 Drop your notes files here

Chat attachments don't reach the build sandbox, so this folder is the reliable route.
**Accepted formats:** `.html` · `.md` · `.txt` · `.docx` (Word) · `.zip` (a whole folder
in one file — the importer unpacks it and works out each subject/grade inside).

## How (2 minutes, phone or laptop)

1. Open the upload page for this branch:

   **https://github.com/YaredwebDev/edulearn-platform/upload/arena/01a0b4b5-edulearn-platform**

   (or: repo → branch selector → `arena/01a0b4b5-edulearn-platform` → **Add file → Upload files**)

2. Drag in your notes files, for example:

   - `Biology_Grade9_Structured.html`
   - `Biology_Grade10_Structured.html`
   - `Chemistry_Grade9_Structured.html`
   - `Chemistry_Grade10_Structured.html`
   - `English_Grade9_Structured.html`
   - `English_Grade10_Structured.html`
   - `Mathematics_Grade9_Structured.html`
   - `Mathematics_Grade10_Structured.html`
   - `Physics_Grade9_Structured.html`
   - `Physics_Grade10_Structured.html`

   > Grade + subject are read from the **file name**, so keep both in it
   > (`Chemistry_Grade9_Structured.html`). Inside a `.zip`, the name of each file
   > inside is what counts.

3. Scroll down → **Commit changes** → commit directly to the
   `arena/01a0b4b5-edulearn-platform` branch.

4. Say **"uploaded"** in the chat.

## What happens next (one command, run by the agent)

```
python3 notes_import.py --notes notes --preview   # shows every unit + lesson, writes nothing
python3 build_course.py --notes notes             # backup → import → 10 questions/lesson → report
```

* the full unit → lesson breakdown is printed for review **before** anything is written
* thin/duplicate/empty lessons are flagged, so nothing half-parsed gets published
* every lesson body is kept **verbatim**; summary and "quick revision" boxes are kept as lessons
* 10 questions per lesson are generated from each lesson's own text
* student progress carries across the content swap lesson-by-lesson
