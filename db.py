"""SQLite data layer for the Grade 9-12 digital learning platform."""
import os, sqlite3, threading, json, time

DB_PATH = os.environ.get("EDULEARN_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "platform.db")
_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  full_name TEXT NOT NULL,
  grade INTEGER NOT NULL,
  phone TEXT,
  age INTEGER,
  school TEXT,
  role TEXT NOT NULL DEFAULT 'student',   -- 'student' | 'admin'
  pwd_hash TEXT NOT NULL,
  salt TEXT NOT NULL,
  created_at REAL
);
CREATE TABLE IF NOT EXISTS subjects(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  grade INTEGER NOT NULL,
  code TEXT NOT NULL,          -- 'chem','bio','phys','agri','engl','math'
  name TEXT NOT NULL,
  description TEXT,
  sort INTEGER DEFAULT 0,
  UNIQUE(grade, code)
);
CREATE TABLE IF NOT EXISTS units(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  subject_id INTEGER NOT NULL REFERENCES subjects(id),
  number INTEGER NOT NULL,
  title TEXT NOT NULL,
  sort INTEGER DEFAULT 0,
  UNIQUE(subject_id, number)
);
CREATE TABLE IF NOT EXISTS lessons(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  unit_id INTEGER NOT NULL REFERENCES units(id),
  number INTEGER NOT NULL,
  title TEXT NOT NULL,
  content_md TEXT,           -- original markdown body
  content_html TEXT,         -- rendered teaching content
  sort INTEGER DEFAULT 0,
  UNIQUE(unit_id, number)
);
CREATE TABLE IF NOT EXISTS questions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scope TEXT NOT NULL,        -- 'lesson' | 'final'
  lesson_id INTEGER,          -- when scope='lesson'
  subject_id INTEGER,         -- when scope='final' (and lesson subject)
  qtype TEXT NOT NULL DEFAULT 'mcq',   -- mcq|tf|cloze|match
  prompt TEXT NOT NULL,
  choices TEXT,               -- JSON array of choices (for mcq); for tf ['True','False']
  answer TEXT NOT NULL,       -- correct: for mcq index-or-text; store answer string + position
  answer_index INTEGER,       -- index of correct choice for mcq/tf
  explanation TEXT,           -- why correct
  difficulty TEXT DEFAULT 'Medium',  -- Easy|Medium|Hard
  concept TEXT,
  status TEXT DEFAULT 'AI Generated',  -- 'AI Generated' | 'Needs Review' | 'Approved' | 'Rejected'
  sort INTEGER DEFAULT 0,
  created_at REAL
);
CREATE TABLE IF NOT EXISTS flashcards(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  lesson_id INTEGER NOT NULL REFERENCES lessons(id),
  front TEXT NOT NULL,
  back TEXT NOT NULL,
  sort INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS lesson_progress(
  user_id INTEGER NOT NULL,
  lesson_id INTEGER NOT NULL,
  status TEXT DEFAULT 'Not Started',  -- Not Started|In Progress|Quiz Failed|Review Required|Completed
  best_score INTEGER DEFAULT 0,
  best_total INTEGER DEFAULT 0,
  attempts INTEGER DEFAULT 0,
  last_at REAL,
  completed_at REAL,
  PRIMARY KEY(user_id, lesson_id)
);
CREATE TABLE IF NOT EXISTS attempts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  scope TEXT NOT NULL,            -- 'lesson' | 'final'
  lesson_id INTEGER,              -- lesson when scope=lesson
  subject_id INTEGER,
  total INTEGER NOT NULL,
  correct INTEGER NOT NULL,
  percent REAL NOT NULL,
  passed INTEGER NOT NULL,
  answers TEXT,                   -- JSON {question_id: chosen_index}
  started_at REAL,
  submitted_at REAL
);
CREATE TABLE IF NOT EXISTS unit_progress(
  user_id INTEGER NOT NULL,
  unit_id INTEGER NOT NULL,
  lessons_total INTEGER DEFAULT 0,
  lessons_done INTEGER DEFAULT 0,
  completed INTEGER DEFAULT 0,
  completed_at REAL,
  PRIMARY KEY(user_id, unit_id)
);
CREATE TABLE IF NOT EXISTS subject_progress(
  user_id INTEGER NOT NULL,
  subject_id INTEGER NOT NULL,
  units_total INTEGER DEFAULT 0,
  units_done INTEGER DEFAULT 0,
  lessons_total INTEGER DEFAULT 0,
  lessons_done INTEGER DEFAULT 0,
  status TEXT DEFAULT 'Not Started',  -- Not Started|In Progress|Units Complete|Exam Passed
  final_unlocked INTEGER DEFAULT 0,
  final_passed INTEGER DEFAULT 0,
  best_exam INTEGER DEFAULT 0,
  best_exam_total INTEGER DEFAULT 0,
  PRIMARY KEY(user_id, subject_id)
);
CREATE TABLE IF NOT EXISTS certificates(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  cert_id TEXT UNIQUE NOT NULL,
  user_id INTEGER NOT NULL,
  subject_id INTEGER NOT NULL,
  grade INTEGER NOT NULL,
  full_name TEXT NOT NULL,       -- snapshot of name at issuance
  exam_score INTEGER NOT NULL,
  exam_total INTEGER NOT NULL,
  issued_at REAL
);
CREATE TABLE IF NOT EXISTS notifications(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  audience TEXT NOT NULL,          -- all|grade|subject|one
  audience_value TEXT,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  created_by INTEGER,
  created_at REAL
);
CREATE TABLE IF NOT EXISTS user_notifications(
  user_id INTEGER NOT NULL,
  notification_id INTEGER NOT NULL,
  read INTEGER DEFAULT 0,
  PRIMARY KEY(user_id, notification_id)
);
CREATE TABLE IF NOT EXISTS exam_sessions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  subject_id INTEGER NOT NULL,
  question_ids TEXT NOT NULL,      -- JSON array of the delivered question ids
  returned INTEGER DEFAULT 0,      -- 1 once the result has been recorded
  created_at REAL,
  submitted_at REAL
);
CREATE TABLE IF NOT EXISTS admin_sessions(
  token TEXT PRIMARY KEY,
  created_at REAL
);
CREATE INDEX IF NOT EXISTS ix_lessons_unit ON lessons(unit_id);
CREATE INDEX IF NOT EXISTS ix_questions_lesson ON questions(lesson_id);
CREATE INDEX IF NOT EXISTS ix_questions_final ON questions(subject_id) WHERE scope='final';
CREATE INDEX IF NOT EXISTS ix_flashcards_lesson ON flashcards(lesson_id);
CREATE INDEX IF NOT EXISTS ix_lp ON lesson_progress(user_id);
CREATE INDEX IF NOT EXISTS ix_attempts_user ON attempts(user_id);
CREATE INDEX IF NOT EXISTS ix_exam_sessions ON exam_sessions(user_id, subject_id);
"""

def _conn():
    if not hasattr(_local, 'conn') or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA foreign_keys=ON")
        _local.conn.execute("PRAGMA journal_mode=WAL")
    return _local.conn

def init_db():
    c = _conn()
    c.executescript(SCHEMA)
    c.commit()

def query(sql, params=(), one=False):
    c = _conn()
    cur = c.execute(sql, params)
    rows = cur.fetchall()
    if one:
        return dict(rows[0]) if rows else None
    return [dict(r) for r in rows]

def execute(sql, params=()):
    c = _conn()
    cur = c.execute(sql, params)
    c.commit()
    return cur.lastrowid

def execute_many(sql, seq):
    c = _conn()
    c.executemany(sql, seq)
    c.commit()

def now():
    return time.time()
