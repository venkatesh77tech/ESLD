-- ═══════════════════════════════════════════════════
--  ESLD EDUCATIONAL PLATFORM  –  DATABASE SCHEMA
-- ═══════════════════════════════════════════════════

CREATE DATABASE IF NOT EXISTS esld CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE esld;

-- ─── SCHOOLS ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS schools (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  name       VARCHAR(255) NOT NULL UNIQUE,
  code       VARCHAR(20)  NOT NULL UNIQUE,
  address    VARCHAR(500),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── CLASSES ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS classes (
  id        INT AUTO_INCREMENT PRIMARY KEY,
  school_id INT         NOT NULL,
  standard  VARCHAR(30) NOT NULL,   -- e.g. "Grade 1", "Class 5"
  section   VARCHAR(5)  NOT NULL,   -- A, B, C …
  FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
  UNIQUE KEY uk_class (school_id, standard, section)
);

-- ─── STUDENTS ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS students (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  student_id  VARCHAR(20)  NOT NULL UNIQUE,
  school_id   INT          NOT NULL,
  class_id    INT          NOT NULL,
  school      VARCHAR(255) DEFAULT NULL,   -- free-text school name from the dropdown (see note below)
  standard    VARCHAR(30)  DEFAULT NULL,   -- e.g. "3" (matches teachers.standard for filtering)
  section     VARCHAR(5)   DEFAULT NULL,   -- e.g. "A"
  name        VARCHAR(255) NOT NULL,
  email       VARCHAR(255) NOT NULL UNIQUE,
  password    VARCHAR(255) NOT NULL,
  disability  ENUM('dyslexia','dysgraphia','dyscalculia','adhd','other') DEFAULT 'dyslexia',
  total_coins INT DEFAULT 0,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (school_id) REFERENCES schools(id),
  FOREIGN KEY (class_id)  REFERENCES classes(id)
);
-- NOTE: school_id/class_id stay as the normalized FK columns from the original design.
-- school/standard/section are added because student-login.html and teacher-login.html
-- both collect a free-text school name + grade + section from a dropdown, not a numeric
-- ID — so filtering "which students does this teacher see" has to match on these text
-- columns, not the FKs (which the registration forms never actually populate correctly).
-- If you already created this table, run instead:
--   ALTER TABLE students ADD COLUMN school VARCHAR(255), ADD COLUMN standard VARCHAR(30), ADD COLUMN section VARCHAR(5);

-- ─── TEACHERS ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS teachers (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  teacher_id VARCHAR(20)  NOT NULL UNIQUE,
  school_id  INT          NOT NULL,
  class_id   INT          NOT NULL,
  school     VARCHAR(255) DEFAULT NULL,   -- free-text, must match students.school for filtering
  standard   VARCHAR(30)  DEFAULT NULL,   -- class/grade this teacher teaches; blank = whole school
  section    VARCHAR(5)   DEFAULT NULL,   -- blank = all sections
  role       VARCHAR(20)  DEFAULT 'teacher', -- 'teacher' | 'head' | 'admin'
  name       VARCHAR(255) NOT NULL,
  email      VARCHAR(255) NOT NULL UNIQUE,
  password   VARCHAR(255) NOT NULL,
  subject    VARCHAR(100) DEFAULT 'General',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (school_id) REFERENCES schools(id),
  FOREIGN KEY (class_id)  REFERENCES classes(id)
);
-- If you already created this table, run instead:
--   ALTER TABLE teachers ADD COLUMN school VARCHAR(255), ADD COLUMN standard VARCHAR(30),
--                         ADD COLUMN section VARCHAR(5), ADD COLUMN role VARCHAR(20) DEFAULT 'teacher';

-- ─── PARENTS ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS parents (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  parent_id  VARCHAR(20)  NOT NULL UNIQUE,
  name       VARCHAR(255) NOT NULL,
  email      VARCHAR(255) NOT NULL UNIQUE,
  password   VARCHAR(255) NOT NULL,
  student_id VARCHAR(20)  NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (student_id) REFERENCES students(student_id)
);

-- ─── ASSIGNMENTS ────────────────────────────────────
CREATE TABLE IF NOT EXISTS assignments (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  teacher_id  VARCHAR(20)  NOT NULL,
  school_id   INT          NOT NULL,
  class_id    INT          NOT NULL,
  title       VARCHAR(255) NOT NULL,
  description TEXT,
  due_date    DATE,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id),
  FOREIGN KEY (school_id)  REFERENCES schools(id),
  FOREIGN KEY (class_id)   REFERENCES classes(id)
);

-- ─── ASSIGNMENT SUBMISSIONS ──────────────────────────
CREATE TABLE IF NOT EXISTS assignment_submissions (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  assignment_id INT          NOT NULL,
  student_id    VARCHAR(20)  NOT NULL,
  status        ENUM('submitted','graded') DEFAULT 'submitted',
  grade         INT          DEFAULT NULL,
  feedback      TEXT         DEFAULT NULL,
  submitted_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
  FOREIGN KEY (student_id)    REFERENCES students(student_id),
  UNIQUE KEY uk_sub (assignment_id, student_id)
);

-- ─── GAME PROGRESS ──────────────────────────────────
CREATE TABLE IF NOT EXISTS game_progress (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  student_id   VARCHAR(20) NOT NULL,
  game         VARCHAR(100) NOT NULL,
  module       ENUM('dyslexia','dysgraphia','adhd') DEFAULT 'dyslexia',
  mode         VARCHAR(20),
  level        INT DEFAULT 1,
  accuracy     FLOAT DEFAULT 0,
  coins        INT DEFAULT 0,
  session_time INT DEFAULT 0,
  questions    INT DEFAULT 0,
  correct      INT DEFAULT 0,
  wrong        INT DEFAULT 0,
  date_played  DATE,
  created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (student_id) REFERENCES students(student_id)
);

-- If you already created this table before, run this once instead of dropping data:
-- ALTER TABLE game_progress ADD COLUMN module ENUM('dyslexia','dysgraphia','adhd') DEFAULT 'dyslexia' AFTER game;

-- ─── PASSWORD RESETS ────────────────────────────────
CREATE TABLE IF NOT EXISTS password_resets (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  email      VARCHAR(255) NOT NULL,
  token      VARCHAR(64)  NOT NULL UNIQUE,
  expires_at DATETIME     NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── MESSAGES ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  sender_id     VARCHAR(20) NOT NULL,
  sender_type   ENUM('student','teacher','parent') NOT NULL,
  receiver_id   VARCHAR(20) NOT NULL,
  receiver_type ENUM('student','teacher','parent') NOT NULL,
  message       TEXT NOT NULL,
  is_read       TINYINT DEFAULT 0,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ════════════════════════════════════════════════════
--  SEED DATA
-- ════════════════════════════════════════════════════

INSERT IGNORE INTO schools (name, code, address) VALUES
  ('Springfield Elementary',   'SPE001', '123 Main St, Springfield'),
  ('Greenwood Academy',        'GWA002', '45 Park Ave, Greenwood'),
  ('Sunrise Learning Center',  'SLC003', '78 Sunrise Blvd, Eastville'),
  ('Riverside Public School',  'RPS004', '12 River Rd, Riverside');

-- Classes for school 1 (Springfield)
INSERT IGNORE INTO classes (school_id, standard, section) VALUES
  (1,'Grade 1','A'),(1,'Grade 1','B'),(1,'Grade 2','A'),(1,'Grade 2','B'),
  (1,'Grade 3','A'),(1,'Grade 3','B'),(1,'Grade 4','A'),(1,'Grade 4','B'),
  (1,'Grade 5','A'),(1,'Grade 5','B');

-- Classes for school 2 (Greenwood)
INSERT IGNORE INTO classes (school_id, standard, section) VALUES
  (2,'Grade 1','A'),(2,'Grade 2','A'),(2,'Grade 3','A'),
  (2,'Grade 4','A'),(2,'Grade 5','A'),(2,'Grade 6','A');

-- Classes for school 3 (Sunrise)
INSERT IGNORE INTO classes (school_id, standard, section) VALUES
  (3,'Grade 1','A'),(3,'Grade 2','A'),(3,'Grade 3','A'),
  (3,'Grade 4','A'),(3,'Grade 5','A');

-- Classes for school 4 (Riverside)
INSERT IGNORE INTO classes (school_id, standard, section) VALUES
  (4,'Grade 1','A'),(4,'Grade 2','A'),(4,'Grade 3','A'),
  (4,'Grade 4','A');

-- Demo teacher password = "teacher123"  (bcrypt hash generated separately)
-- Run this Python snippet to get hashes:
--   import bcrypt
--   print(bcrypt.hashpw(b"teacher123", bcrypt.gensalt()).decode())
-- Then update the INSERT below with the real hash.

-- NOTE: Teachers must be added via /teacher-register API or manually after
-- generating bcrypt hashes. The API endpoints handle all hashing securely.