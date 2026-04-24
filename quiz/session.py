"""
quiz/session.py
───────────────
Manages active quiz sessions per Teams user.
Tracks state: current question, score, answers, completion.
"""

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

DATA_DIR = Path("./data/sessions")
DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class QuizSession:
    user_id: str
    user_name: str
    quiz: dict                        # full quiz dict from generator
    current_index: int = 0
    score: int = 0
    answers: list = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    completed: bool = False

    # ── Navigation ────────────────────────────────────────────────────────────

    @property
    def current_question(self) -> Optional[dict]:
        questions = self.quiz.get("questions", [])
        if self.current_index < len(questions):
            return questions[self.current_index]
        return None

    @property
    def total_questions(self) -> int:
        return len(self.quiz.get("questions", []))

    @property
    def is_mcq(self) -> bool:
        return self.quiz.get("format", "mcq") != "short_answer"

    @property
    def progress_str(self) -> str:
        return f"Question {self.current_index + 1} of {self.total_questions}"

    # ── Answer handling ───────────────────────────────────────────────────────

    def submit_mcq_answer(self, answer: str) -> dict:
        """
        Submit an MCQ answer. Returns result dict.
        answer: single letter "A", "B", "C", or "D"
        """
        q = self.current_question
        if not q:
            return {"error": "No active question"}

        answer = answer.strip().upper()
        correct = q["correct_answer"].upper()
        is_correct = answer == correct

        if is_correct:
            self.score += 1

        result = {
            "question_id": q["id"],
            "submitted": answer,
            "correct_answer": correct,
            "is_correct": is_correct,
            "explanation": q.get("explanation", ""),
            "topic": q.get("topic", ""),
        }

        self.answers.append(result)
        self.current_index += 1

        if self.current_index >= self.total_questions:
            self.completed = True

        self._save()
        return result

    def submit_short_answer(self, answer: str, evaluation: dict) -> dict:
        """Submit a short answer with its Claude evaluation."""
        q = self.current_question
        if not q:
            return {"error": "No active question"}

        is_passing = evaluation.get("is_passing", False)
        if is_passing:
            self.score += 1

        result = {
            "question_id": q["id"],
            "submitted": answer,
            "evaluation": evaluation,
            "model_answer": q.get("model_answer", ""),
            "topic": q.get("topic", ""),
        }

        self.answers.append(result)
        self.current_index += 1

        if self.current_index >= self.total_questions:
            self.completed = True

        self._save()
        return result

    # ── Summary ───────────────────────────────────────────────────────────────

    def summary(self) -> dict:
        pct = round((self.score / self.total_questions) * 100) if self.total_questions else 0
        passed = pct >= 70  # 70% pass mark

        topic_counts = {}
        for a in self.answers:
            topic = a.get("topic", "General")
            topic_counts[topic] = topic_counts.get(topic, {"correct": 0, "total": 0})
            topic_counts[topic]["total"] += 1
            if a.get("is_correct") or (a.get("evaluation", {}).get("is_passing")):
                topic_counts[topic]["correct"] += 1

        elapsed = round(time.time() - self.started_at)
        mins, secs = divmod(elapsed, 60)

        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "score": self.score,
            "total": self.total_questions,
            "percentage": pct,
            "passed": passed,
            "time_taken": f"{mins}m {secs}s",
            "topic_breakdown": topic_counts,
            "manual_sources": self.quiz.get("manual_sources", []),
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save(self):
        path = DATA_DIR / f"{self.user_id}.json"
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, user_id: str) -> Optional["QuizSession"]:
        path = DATA_DIR / f"{user_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return cls(**data)

    @classmethod
    def clear(cls, user_id: str):
        path = DATA_DIR / f"{user_id}.json"
        if path.exists():
            path.unlink()


# ── Scoreboard ────────────────────────────────────────────────────────────────

SCOREBOARD_PATH = Path("./data/scoreboard.json")


def update_scoreboard(summary: dict):
    """Append a completed quiz result to the scoreboard."""
    board = []
    if SCOREBOARD_PATH.exists():
        board = json.loads(SCOREBOARD_PATH.read_text())

    board.append({
        "user_id": summary["user_id"],
        "user_name": summary["user_name"],
        "score": summary["score"],
        "total": summary["total"],
        "percentage": summary["percentage"],
        "passed": summary["passed"],
        "time_taken": summary["time_taken"],
        "timestamp": time.time(),
        "sources": summary.get("manual_sources", []),
    })

    SCOREBOARD_PATH.write_text(json.dumps(board, indent=2))


def get_leaderboard(limit: int = 10) -> list[dict]:
    """Return top scores sorted by percentage."""
    if not SCOREBOARD_PATH.exists():
        return []
    board = json.loads(SCOREBOARD_PATH.read_text())
    return sorted(board, key=lambda x: x["percentage"], reverse=True)[:limit]
