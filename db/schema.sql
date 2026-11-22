-- =============================================================
-- SmartExam Database Schema
-- Engine: MySQL 8.0+
-- =============================================================

CREATE DATABASE IF NOT EXISTS smartexam
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE smartexam;

-- -------------------------------------------------------------
-- 1. users
--    Stores both students and admins (differentiated by role).
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id            INT          AUTO_INCREMENT PRIMARY KEY,
    full_name     VARCHAR(120) NOT NULL,
    email         VARCHAR(180) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role          ENUM('student','admin') NOT NULL DEFAULT 'student',
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- -------------------------------------------------------------
-- 2. exams
--    Each exam belongs to an admin who created it.
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS exams (
    id               INT          AUTO_INCREMENT PRIMARY KEY,
    title            VARCHAR(200) NOT NULL,
    description      TEXT,
    duration_minutes INT          NOT NULL DEFAULT 30,
    total_marks      INT          NOT NULL DEFAULT 0,
    created_by       INT          NOT NULL,
    created_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- -------------------------------------------------------------
-- 3. questions
--    MCQ questions linked to an exam.
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS questions (
    id             INT           AUTO_INCREMENT PRIMARY KEY,
    exam_id        INT           NOT NULL,
    question_text  TEXT          NOT NULL,
    option_a       VARCHAR(500)  NOT NULL,
    option_b       VARCHAR(500)  NOT NULL,
    option_c       VARCHAR(500)  NOT NULL,
    option_d       VARCHAR(500)  NOT NULL,
    correct_option ENUM('A','B','C','D') NOT NULL,
    marks          INT           NOT NULL DEFAULT 1,
    question_order INT           NOT NULL DEFAULT 0,
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- -------------------------------------------------------------
-- 4. exam_results
--    One row per student per exam sitting.
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS exam_results (
    id            INT      AUTO_INCREMENT PRIMARY KEY,
    student_id    INT      NOT NULL,
    exam_id       INT      NOT NULL,
    score         INT      NOT NULL DEFAULT 0,   -- raw marks before penalty
    penalty_marks INT      NOT NULL DEFAULT 0,   -- total marks deducted
    final_score   INT      NOT NULL DEFAULT 0,   -- score - penalty_marks (>=0)
    started_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    submitted_at  DATETIME,
    status        ENUM('in_progress','submitted','terminated','retake_allowed') NOT NULL DEFAULT 'in_progress',
    answers_json  TEXT,                           -- JSON snapshot of student answers
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (exam_id)    REFERENCES exams(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- -------------------------------------------------------------
-- 5. violation_logs
--    Every confirmed violation event is recorded here.
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS violation_logs (
    id             INT          AUTO_INCREMENT PRIMARY KEY,
    student_id     INT          NOT NULL,
    exam_id        INT          NOT NULL,
    result_id      INT          NOT NULL,
    violation_type VARCHAR(50)  NOT NULL,  -- FACE_MISSING | MULTIPLE_FACES | GAZE_LEFT | GAZE_RIGHT | HEAD_TURNED
    warning_number INT          NOT NULL DEFAULT 1,
    penalty_marks  INT          NOT NULL DEFAULT 0, -- marks deducted THIS event (0 if only a warning)
    detected_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (exam_id)    REFERENCES exams(id) ON DELETE CASCADE,
    FOREIGN KEY (result_id)  REFERENCES exam_results(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- -------------------------------------------------------------
-- 6. exam_config
--    Per-exam AI monitoring thresholds (falls back to defaults
--    in config.py when no row exists for that exam).
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS exam_config (
    id                          INT  AUTO_INCREMENT PRIMARY KEY,
    exam_id                     INT  NOT NULL UNIQUE,
    look_away_threshold_sec     INT  NOT NULL DEFAULT 3,
    max_warnings_before_penalty INT  NOT NULL DEFAULT 3,
    penalty_marks_per_violation INT  NOT NULL DEFAULT 1,
    max_penalty_marks           INT  NOT NULL DEFAULT 5,
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- =============================================================
-- SEED DATA
-- =============================================================

-- Admin account  (password: Admin@123)
INSERT INTO users (full_name, email, password_hash, role) VALUES
('Admin User', 'admin@smartexam.com',
 '$2b$12$xS2gUwjjeQ8KGqEcliSkKORJIRqJOAnBxolAStsos40XWepz.vvd.', 'admin');

-- Sample student  (password: Student@123)
INSERT INTO users (full_name, email, password_hash, role) VALUES
('Alice Johnson', 'alice@example.com',
 '$2b$12$fWV1gq9BZcOi6KK7HSAz0OWg7zFluHHVjAPurrPeywGobdJ3vgXE2', 'student');

-- Exam 1: Python Basics
INSERT INTO exams (title, description, duration_minutes, total_marks, created_by) VALUES
('Python Basics', 'Test your knowledge of Python fundamentals.', 30, 10, 1);

-- Exam 2: Web Development Fundamentals
INSERT INTO exams (title, description, duration_minutes, total_marks, created_by) VALUES
('Web Development Fundamentals', 'HTML, CSS and JavaScript basics.', 20, 10, 1);

-- Exam 1 questions
INSERT INTO questions (exam_id, question_text, option_a, option_b, option_c, option_d, correct_option, marks, question_order) VALUES
(1, 'What is the output of print(type([]))?', "<class 'list'>", "<class 'dict'>", "<class 'tuple'>", "<class 'set'>", 'A', 1, 1),
(1, 'Which keyword is used to define a function in Python?', 'function', 'def', 'fun', 'define', 'B', 1, 2),
(1, 'What does len("hello") return?', '4', '5', '6', 'Error', 'B', 1, 3),
(1, 'Which of these is a mutable data type in Python?', 'tuple', 'string', 'list', 'int', 'C', 1, 4),
(1, 'What is the result of 3 ** 2 in Python?', '6', '8', '9', '5', 'C', 1, 5),
(1, 'How do you start a comment in Python?', '//', '#', '/*', '--', 'B', 1, 6),
(1, 'Which method adds an element to the end of a list?', 'add()', 'insert()', 'append()', 'push()', 'C', 1, 7),
(1, 'What is the default return value of a Python function?', '0', 'None', 'False', 'Error', 'B', 1, 8),
(1, 'Which operator is used for floor division?', '/', '%', '//', '**', 'C', 1, 9),
(1, 'What does the range(5) function generate?', '[1,2,3,4,5]', '[0,1,2,3,4]', '[0,1,2,3,4,5]', '[1,2,3,4]', 'B', 1, 10);

-- Exam 2 questions
INSERT INTO questions (exam_id, question_text, option_a, option_b, option_c, option_d, correct_option, marks, question_order) VALUES
(2, 'Which tag is used to create a hyperlink in HTML?', '<link>', '<href>', '<a>', '<url>', 'C', 1, 1),
(2, 'What does CSS stand for?', 'Computer Style Sheets', 'Cascading Style Sheets', 'Creative Style Sheets', 'Colorful Style Sheets', 'B', 1, 2),
(2, 'Which HTML tag is used for the largest heading?', '<h6>', '<heading>', '<h1>', '<head>', 'C', 1, 3),
(2, 'In CSS, how do you select an element with id="main"?', '.main', '*main', '#main', 'main', 'C', 1, 4),
(2, 'Which JavaScript method is used to write to the console?', 'console.print()', 'console.log()', 'print()', 'log()', 'B', 1, 5),
(2, 'What does the display:flex CSS property do?', 'Hides the element', 'Enables flexbox layout', 'Makes text bold', 'Adds a border', 'B', 1, 6),
(2, 'Which HTML attribute specifies the URL of an image?', 'href', 'link', 'src', 'url', 'C', 1, 7),
(2, 'What is the correct JavaScript syntax to change the content of the element with id="demo"?', 'document.getElement("demo").innerHTML="Hello";', 'document.getElementById("demo").innerHTML="Hello";', '#demo.innerHTML="Hello";', 'getElementById("demo").innerHTML="Hello";', 'B', 1, 8),
(2, 'Which CSS property controls the text size?', 'text-size', 'font-size', 'text-style', 'font-style', 'B', 1, 9),
(2, 'Which HTML element is used to define navigation links?', '<navigate>', '<nav>', '<navigation>', '<link>', 'B', 1, 10);

-- Default exam configs
INSERT INTO exam_config (exam_id, look_away_threshold_sec, max_warnings_before_penalty, penalty_marks_per_violation, max_penalty_marks) VALUES
(1, 3, 3, 1, 5),
(2, 3, 3, 1, 5);
