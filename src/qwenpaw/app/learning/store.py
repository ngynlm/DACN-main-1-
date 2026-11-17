"""Private SQLite persistence for student tutor accounts and study data."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from typing import Any, Iterator
import uuid

from ...constant import WORKING_DIR

_PASSWORD_ITERATIONS = 600_000
_SESSION_TTL_SECONDS = 30 * 24 * 60 * 60


def _password_digest(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _PASSWORD_ITERATIONS,
    )


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> int:
    return int(time.time())


class LearningStore:
    """Owns student credentials, sessions, and learning records."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or WORKING_DIR / "learning_tutor.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS learning_students (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    password_salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS learning_sessions (
                    token_hash TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL REFERENCES learning_students(id)
                        ON DELETE CASCADE,
                    expires_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS learning_sessions_student
                    ON learning_sessions(student_id);
                CREATE TABLE IF NOT EXISTS learning_materials (
                    id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL REFERENCES learning_students(id)
                        ON DELETE CASCADE,
                    subject TEXT NOT NULL,
                    grade INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS learning_materials_owner
                    ON learning_materials(student_id, subject, grade);
                CREATE TABLE IF NOT EXISTS learning_history (
                    id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL REFERENCES learning_students(id)
                        ON DELETE CASCADE,
                    kind TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    response TEXT NOT NULL,
                    sources_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS learning_history_owner
                    ON learning_history(student_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS learning_quizzes (
                    id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL REFERENCES learning_students(id)
                        ON DELETE CASCADE,
                    subject TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    grade INTEGER NOT NULL,
                    difficulty TEXT NOT NULL,
                    questions_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS learning_quiz_results (
                    id TEXT PRIMARY KEY,
                    quiz_id TEXT NOT NULL REFERENCES learning_quizzes(id)
                        ON DELETE CASCADE,
                    student_id TEXT NOT NULL REFERENCES learning_students(id)
                        ON DELETE CASCADE,
                    score INTEGER NOT NULL,
                    total INTEGER NOT NULL,
                    feedback_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS learning_results_owner
                    ON learning_quiz_results(student_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS learning_plans (
                    id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL REFERENCES learning_students(id)
                        ON DELETE CASCADE,
                    subject TEXT NOT NULL,
                    grade INTEGER NOT NULL,
                    goal TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS learning_plans_owner
                    ON learning_plans(student_id, created_at DESC);
                """,
            )
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def register(
        self,
        username: str,
        password: str,
    ) -> tuple[dict[str, Any], str]:
        username = username.strip()
        salt = secrets.token_bytes(16)
        password_hash = _password_digest(password, salt)
        student_id = uuid.uuid4().hex
        token = secrets.token_urlsafe(32)
        created_at = _now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO learning_students(
                    id, username, password_salt, password_hash, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (student_id, username, salt, password_hash, created_at),
            )
            self._insert_session(connection, student_id, token)
        return {
            "id": student_id,
            "username": username,
            "created_at": created_at,
        }, token

    def login(self, username: str, password: str) -> tuple[dict[str, Any], str] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, username, password_salt, password_hash, created_at
                FROM learning_students WHERE username = ?
                """,
                (username.strip(),),
            ).fetchone()
            if row is None:
                # Keep the work factor similar for unknown accounts.
                _password_digest(password, b"\0" * 16)
                return None
            actual_hash = _password_digest(password, bytes(row["password_salt"]))
            if not hmac.compare_digest(actual_hash, bytes(row["password_hash"])):
                return None
            token = secrets.token_urlsafe(32)
            self._insert_session(connection, str(row["id"]), token)
            return {
                "id": str(row["id"]),
                "username": str(row["username"]),
                "created_at": int(row["created_at"]),
            }, token

    @staticmethod
    def _insert_session(
        connection: sqlite3.Connection,
        student_id: str,
        token: str,
    ) -> None:
        connection.execute(
            "INSERT INTO learning_sessions(token_hash, student_id, expires_at) "
            "VALUES (?, ?, ?)",
            (
                _token_digest(token),
                student_id,
                _now() + _SESSION_TTL_SECONDS,
            ),
        )

    def get_student_for_token(self, token: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT s.id, s.username, s.created_at
                FROM learning_sessions AS t
                JOIN learning_students AS s ON s.id = t.student_id
                WHERE t.token_hash = ? AND t.expires_at > ?
                """,
                (_token_digest(token), _now()),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": str(row["id"]),
            "username": str(row["username"]),
            "created_at": int(row["created_at"]),
        }

    def get_or_create_for_username(self, username: str) -> dict[str, Any]:
        """Return the learning profile associated with a QwenPaw account."""
        username = username.strip()
        if not username:
            raise ValueError("username must not be empty")

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT id, username, created_at
                FROM learning_students WHERE username = ?
                """,
                (username,),
            ).fetchone()
            if row is None:
                student_id = uuid.uuid4().hex
                created_at = _now()
                connection.execute(
                    """
                    INSERT INTO learning_students(
                        id, username, password_salt, password_hash, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        student_id,
                        username,
                        secrets.token_bytes(16),
                        secrets.token_bytes(32),
                        created_at,
                    ),
                )
                row = connection.execute(
                    """
                    SELECT id, username, created_at
                    FROM learning_students WHERE id = ?
                    """,
                    (student_id,),
                ).fetchone()

        if row is None:
            raise RuntimeError("Could not load the learning profile.")

        return {
            "id": str(row["id"]),
            "username": str(row["username"]),
            "created_at": int(row["created_at"]),
        }

    def logout(self, token: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM learning_sessions WHERE token_hash = ?",
                (_token_digest(token),),
            )

    def create_material(
        self,
        student_id: str,
        subject: str,
        grade: int,
        title: str,
        content: str,
    ) -> dict[str, Any]:
        item = {
            "id": uuid.uuid4().hex,
            "subject": subject.strip(),
            "grade": grade,
            "title": title.strip(),
            "content": content.strip(),
            "created_at": _now(),
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO learning_materials(
                    id, student_id, subject, grade, title, content, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    student_id,
                    item["subject"],
                    grade,
                    item["title"],
                    item["content"],
                    item["created_at"],
                ),
            )
        return item

    def list_materials(self, student_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, subject, grade, title, content, created_at
                FROM learning_materials WHERE student_id = ?
                ORDER BY created_at DESC LIMIT 100
                """,
                (student_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_material(self, student_id: str, material_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM learning_materials WHERE student_id = ? AND id = ?",
                (student_id, material_id),
            )
        return cursor.rowcount > 0

    def search_materials(
        self,
        student_id: str,
        subject: str,
        grade: int,
        query: str,
        limit: int = 4,
    ) -> list[dict[str, str]]:
        terms = set(re.findall(r"[^\W_]+", query.casefold(), re.UNICODE))
        terms = {term for term in terms if len(term) > 1}
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT title, content FROM learning_materials
                WHERE student_id = ? AND subject = ? AND grade = ?
                ORDER BY created_at DESC LIMIT 100
                """,
                (student_id, subject.strip(), grade),
            ).fetchall()

        candidates: list[tuple[float, dict[str, str]]] = []
        for row in rows:
            content = str(row["content"])
            paragraphs = [
                paragraph.strip()
                for paragraph in re.split(r"\n{2,}", content)
                if paragraph.strip()
            ]
            if not paragraphs:
                paragraphs = [content]
            for paragraph in paragraphs:
                start = 0
                while start < len(paragraph):
                    excerpt = paragraph[start : start + 1600]
                    paragraph_terms = set(
                        re.findall(
                            r"[^\W_]+",
                            excerpt.casefold(),
                            re.UNICODE,
                        ),
                    )
                    overlap = len(terms & paragraph_terms)
                    score = overlap / max(len(terms), 1)
                    if query.casefold() in excerpt.casefold():
                        score += 1
                    if score > 0:
                        candidates.append(
                            (
                                score,
                                {
                                    "title": str(row["title"]),
                                    "excerpt": excerpt,
                                },
                            ),
                        )
                    start += 1400
        candidates.sort(key=lambda item: item[0], reverse=True)
        return [item for _, item in candidates[:limit]]

    def add_history(
        self,
        student_id: str,
        kind: str,
        subject: str,
        topic: str,
        prompt: str,
        response: str,
        sources: list[dict[str, str]],
    ) -> dict[str, Any]:
        item = {
            "id": uuid.uuid4().hex,
            "kind": kind,
            "subject": subject,
            "topic": topic,
            "prompt": prompt,
            "response": response,
            "sources": sources,
            "created_at": _now(),
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO learning_history(
                    id, student_id, kind, subject, topic, prompt, response,
                    sources_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    student_id,
                    kind,
                    subject,
                    topic,
                    prompt,
                    response,
                    json.dumps(sources, ensure_ascii=False),
                    item["created_at"],
                ),
            )
        return item

    def list_history(self, student_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, kind, subject, topic, prompt, response,
                       sources_json, created_at
                FROM learning_history WHERE student_id = ?
                ORDER BY created_at DESC LIMIT 100
                """,
                (student_id,),
            ).fetchall()
        return [
            {
                **{key: row[key] for key in (
                    "id",
                    "kind",
                    "subject",
                    "topic",
                    "prompt",
                    "response",
                    "created_at",
                )},
                "sources": json.loads(str(row["sources_json"])),
            }
            for row in rows
        ]

    def create_quiz(
        self,
        student_id: str,
        subject: str,
        topic: str,
        grade: int,
        difficulty: str,
        questions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        quiz_id = uuid.uuid4().hex
        created_at = _now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO learning_quizzes(
                    id, student_id, subject, topic, grade, difficulty,
                    questions_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    quiz_id,
                    student_id,
                    subject,
                    topic,
                    grade,
                    difficulty,
                    json.dumps(questions, ensure_ascii=False),
                    created_at,
                ),
            )
        return self.get_quiz(student_id, quiz_id) or {}

    def get_quiz(
        self,
        student_id: str,
        quiz_id: str,
        *,
        include_answers: bool = False,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, subject, topic, grade, difficulty, questions_json,
                       created_at
                FROM learning_quizzes WHERE student_id = ? AND id = ?
                """,
                (student_id, quiz_id),
            ).fetchone()
        if row is None:
            return None
        questions = json.loads(str(row["questions_json"]))
        if not include_answers:
            questions = [
                {
                    "prompt": question["prompt"],
                    "options": question["options"],
                }
                for question in questions
            ]
        return {
            "id": str(row["id"]),
            "subject": str(row["subject"]),
            "topic": str(row["topic"]),
            "grade": int(row["grade"]),
            "difficulty": str(row["difficulty"]),
            "questions": questions,
            "created_at": int(row["created_at"]),
        }

    def save_quiz_result(
        self,
        student_id: str,
        quiz_id: str,
        score: int,
        total: int,
        feedback: list[dict[str, Any]],
    ) -> dict[str, Any]:
        result = {
            "id": uuid.uuid4().hex,
            "quiz_id": quiz_id,
            "score": score,
            "total": total,
            "feedback": feedback,
            "created_at": _now(),
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO learning_quiz_results(
                    id, quiz_id, student_id, score, total, feedback_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result["id"],
                    quiz_id,
                    student_id,
                    score,
                    total,
                    json.dumps(feedback, ensure_ascii=False),
                    result["created_at"],
                ),
            )
        return result

    def progress(self, student_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT q.subject, q.topic,
                       SUM(r.score) AS correct,
                       SUM(r.total) AS total,
                       COUNT(r.id) AS attempts,
                       MAX(r.created_at) AS last_practiced
                FROM learning_quiz_results AS r
                JOIN learning_quizzes AS q ON q.id = r.quiz_id
                WHERE r.student_id = ?
                GROUP BY q.subject, q.topic
                ORDER BY last_practiced DESC
                """,
                (student_id,),
            ).fetchall()
        result = []
        for row in rows:
            total = int(row["total"])
            correct = int(row["correct"])
            result.append(
                {
                    "subject": str(row["subject"]),
                    "topic": str(row["topic"]),
                    "correct": correct,
                    "total": total,
                    "attempts": int(row["attempts"]),
                    "accuracy": correct / total if total else 0,
                    "last_practiced": int(row["last_practiced"]),
                },
            )
        return result

    def create_plan(
        self,
        student_id: str,
        subject: str,
        grade: int,
        goal: str,
        tasks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        item = {
            "id": uuid.uuid4().hex,
            "subject": subject,
            "grade": grade,
            "goal": goal,
            "tasks": tasks,
            "created_at": _now(),
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO learning_plans(
                    id, student_id, subject, grade, goal, plan_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    student_id,
                    subject,
                    grade,
                    goal,
                    json.dumps(tasks, ensure_ascii=False),
                    item["created_at"],
                ),
            )
        return item

    def list_plans(self, student_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, subject, grade, goal, plan_json, created_at
                FROM learning_plans WHERE student_id = ?
                ORDER BY created_at DESC LIMIT 20
                """,
                (student_id,),
            ).fetchall()
        return [
            {
                "id": str(row["id"]),
                "subject": str(row["subject"]),
                "grade": int(row["grade"]),
                "goal": str(row["goal"]),
                "tasks": json.loads(str(row["plan_json"])),
                "created_at": int(row["created_at"]),
            }
            for row in rows
        ]

    def set_plan_task_completed(
        self,
        student_id: str,
        plan_id: str,
        task_index: int,
        completed: bool,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT subject, grade, goal, plan_json, created_at
                FROM learning_plans WHERE student_id = ? AND id = ?
                """,
                (student_id, plan_id),
            ).fetchone()
            if row is None:
                return None
            tasks = json.loads(str(row["plan_json"]))
            if task_index < 0 or task_index >= len(tasks):
                return None
            tasks[task_index]["completed"] = completed
            tasks[task_index]["completed_at"] = _now() if completed else None
            connection.execute(
                "UPDATE learning_plans SET plan_json = ? WHERE id = ? AND student_id = ?",
                (
                    json.dumps(tasks, ensure_ascii=False),
                    plan_id,
                    student_id,
                ),
            )
        return {
            "id": plan_id,
            "subject": str(row["subject"]),
            "grade": int(row["grade"]),
            "goal": str(row["goal"]),
            "tasks": tasks,
            "created_at": int(row["created_at"]),
        }
