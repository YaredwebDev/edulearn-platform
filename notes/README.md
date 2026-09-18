# 📥 Drop your notes files here

Chat attachments aren't reaching the build sandbox, so use this folder instead.

## How (2 minutes, works on phone or laptop)

1. Open the upload page for this branch:
   **https://github.com/YaredwebDev/edulearn-platform/upload/arena/01a0b4b5-edulearn-platform**
   (or: repo → branch selector → `arena/01a0b4b5-edulearn-platform` → **Add file → Upload files**)

2. Drag in all 10 files:
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

3. Scroll down → **Commit changes** → choose *Commit directly to the
   `arena/01a0b4b5-edulearn-platform` branch*.

4. Tell me in the chat: **"uploaded"**.

I will then run:

```
python3 build_course.py --notes notes
```

which replaces the Grade 9/10 content lesson-by-lesson with your notes and builds
10 questions per lesson from them.

> File names are what identify grade + subject (`Chemistry_Grade9_Structured.html`),
> so please keep the subject and grade in each name.
