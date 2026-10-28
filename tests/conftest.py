import sqlite3

import pytest
from fastapi.testclient import TestClient

# Just the tables and columns the explorer reads, mirroring the Oak release schema.
SCHEMA = """
CREATE TABLE key_stage (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE year_group (id INTEGER PRIMARY KEY, name TEXT, key_stage_id INTEGER);
CREATE TABLE subject (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE scheme (id INTEGER PRIMARY KEY, name TEXT, key_stage_id INTEGER, subject_id INTEGER);
CREATE TABLE tier (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE exam_board (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE programme (id INTEGER PRIMARY KEY, name TEXT, year_group_id INTEGER,
                        scheme_id INTEGER, tier_id INTEGER, exam_board_id INTEGER);
CREATE TABLE unit (id INTEGER PRIMARY KEY, name TEXT, description TEXT,
                   why_this_why_now TEXT, scheme_id INTEGER);
CREATE TABLE unit_variant (id INTEGER PRIMARY KEY, name TEXT, unit_id INTEGER);
CREATE TABLE unit_variant_choice (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE unit_variant_choice_option (unit_variant_choice_id INTEGER, unit_variant_id INTEGER);
CREATE TABLE unit_variant_inclusion (id INTEGER PRIMARY KEY, sequence_position INTEGER,
    programme_id INTEGER, unit_variant_id INTEGER, unit_variant_choice_id INTEGER);
CREATE TABLE lesson (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE lesson_inclusion (id INTEGER PRIMARY KEY, sequence_position INTEGER,
                               lesson_id INTEGER, unit_variant_id INTEGER);
CREATE TABLE pupil_lesson_outcome (id INTEGER PRIMARY KEY, name TEXT, lesson_id INTEGER);
CREATE TABLE key_learning_point (id INTEGER PRIMARY KEY, name TEXT, lesson_id INTEGER);
CREATE TABLE keyword (id INTEGER PRIMARY KEY, name TEXT, description TEXT);
CREATE TABLE lesson_keyword (lesson_id INTEGER, keyword_id INTEGER);
CREATE TABLE misconception (id INTEGER PRIMARY KEY, statement TEXT, correction TEXT);
CREATE TABLE lesson_misconception (lesson_id INTEGER, misconception_id INTEGER);
CREATE TABLE prior_knowledge_requirement (id INTEGER PRIMARY KEY, name TEXT, unit_id INTEGER);
CREATE TABLE thread (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE unit_thread (unit_id INTEGER, thread_id INTEGER);
"""

DATA = """
INSERT INTO key_stage VALUES (2, 'Key Stage 2'), (3, 'Key Stage 3'), (4, 'Key Stage 4');
INSERT INTO year_group VALUES (5, 'Year Group 5', 2), (7, 'Year Group 7', 3), (10, 'Year Group 10', 4);
INSERT INTO subject VALUES (1, 'Mathematics'), (2, 'Biology');
INSERT INTO scheme VALUES (1, 'Maths KS3', 3, 1), (2, 'Biology KS4', 4, 2), (3, 'Maths KS2', 2, 1);
INSERT INTO tier VALUES (1, 'Higher');
INSERT INTO exam_board VALUES (1, 'AQA');
INSERT INTO programme VALUES
  (1, 'Mathematics Year Group 7', 7, 1, NULL, NULL),
  (2, 'Biology Year Group 10 Higher AQA', 10, 2, 1, 1);

INSERT INTO unit VALUES
  (1, 'Place value', 'Revisit place value.', 'We start here because it underpins everything.', 1),
  (2, 'Cells', 'All about   cells .', 'Cells first.', 2),
  (3, 'Ratio', NULL, 'Later.', 1),
  (4, 'Primary fractions', NULL, 'KS2.', 3);
INSERT INTO unit_variant VALUES (1, 'Place value', 1), (2, 'Cells', 2), (3, 'Ratio A', 3),
                                (4, 'Ratio B', 3), (5, 'Primary fractions', 4);
INSERT INTO unit_variant_choice VALUES (1, 'Pick a ratio unit');
INSERT INTO unit_variant_choice_option VALUES (1, 3), (1, 4);
INSERT INTO unit_variant_inclusion VALUES
  (1, 1, 1, 1, NULL), (2, 2, 1, NULL, 1), (3, 1, 2, 2, NULL);

INSERT INTO lesson VALUES (1, 'Ordering decimals'), (2, 'Rounding'), (3, 'Animal cells'),
                          (4, 'Halves and quarters');
INSERT INTO lesson_inclusion VALUES (1, 1, 1, 1), (2, 2, 2, 1), (3, 1, 3, 2), (4, 1, 4, 5);
INSERT INTO pupil_lesson_outcome VALUES (1, 'I can order decimals.', 1);
INSERT INTO key_learning_point VALUES (1, 'Compare digits from the left.', 1);
INSERT INTO keyword VALUES (1, 'decimal', 'a number with a decimal point'), (2, 'nucleus', 'controls the cell');
INSERT INTO lesson_keyword VALUES (1, 1), (3, 2);
INSERT INTO misconception VALUES
  (1, 'Pupils may think that the more decimal places, the bigger the number', 'Compare place value columns.'),
  (2, 'Pupils struggle to line up the digits', 'Use a place value chart.');
INSERT INTO lesson_misconception VALUES (1, 1), (2, 2);
INSERT INTO prior_knowledge_requirement VALUES (1, 'Read whole numbers', 1);
INSERT INTO thread VALUES (1, 'Number');
INSERT INTO unit_thread VALUES (1, 1);
"""


@pytest.fixture
def client(tmp_path, monkeypatch):
    path = tmp_path / "oak.sqlite"
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA + DATA)
    monkeypatch.setenv("OAK_DB", str(path))
    from oak_explorer.app import app

    return TestClient(app)
