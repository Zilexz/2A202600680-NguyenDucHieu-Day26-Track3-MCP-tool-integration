"""Create and seed the lab SQLite database (students / courses / enrollments)."""

import os
import sqlite3

SCHEMA_SQL = """
CREATE TABLE students (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name   TEXT NOT NULL,
    cohort TEXT NOT NULL,
    email  TEXT UNIQUE
);

CREATE TABLE courses (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    code    TEXT NOT NULL UNIQUE,
    title   TEXT NOT NULL,
    credits INTEGER NOT NULL DEFAULT 3
);

CREATE TABLE enrollments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id),
    course_id  INTEGER NOT NULL REFERENCES courses(id),
    term       TEXT NOT NULL,
    score      REAL
);
"""

SEED_SQL = """
INSERT INTO students (name, cohort, email) VALUES
    ('Nguyen Duc Hieu', 'A1', 'hieu@vinuni.edu.vn'),
    ('Tran Thi Mai',    'A1', 'mai@vinuni.edu.vn'),
    ('Le Van Nam',      'A2', 'nam@vinuni.edu.vn'),
    ('Pham Thu Ha',     'A2', 'ha@vinuni.edu.vn'),
    ('Do Quang Minh',   'A1', 'minh@vinuni.edu.vn');

INSERT INTO courses (code, title, credits) VALUES
    ('CS101', 'Introduction to Programming', 3),
    ('CS201', 'Data Structures',             4),
    ('AI301', 'Applied AI Agents',           3);

INSERT INTO enrollments (student_id, course_id, term, score) VALUES
    (1, 1, 'Fall2025',   92.5),
    (1, 2, 'Fall2025',   88.0),
    (2, 1, 'Fall2025',   79.0),
    (3, 3, 'Spring2026', 95.0),
    (4, 3, 'Spring2026', 67.5),
    (5, 2, 'Fall2025',   84.0);
"""

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "lab.db")


def create_database(db_path: str = DEFAULT_DB_PATH) -> str:
    """(Re)create the database at db_path with a fresh schema and seed data."""
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.executescript(SEED_SQL)
        conn.commit()
    finally:
        conn.close()

    return db_path


if __name__ == "__main__":
    path = create_database()
    print(f"Database created at {path}")
