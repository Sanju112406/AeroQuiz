"""
quiz/bank.py
────────────
Question bank — stores trainer-generated questions per topic.
The Telegram bot pulls from here instead of calling the Anthropic API.
"""

import json
from pathlib import Path

BANK_FILE = Path(__file__).parent.parent / "data" / "question_bank.json"


def _load() -> dict:
    try:
        if BANK_FILE.exists():
            return json.loads(BANK_FILE.read_text())
        return {}
    except Exception:
        return {}


def _save(bank: dict):
    BANK_FILE.parent.mkdir(parents=True, exist_ok=True)
    BANK_FILE.write_text(json.dumps(bank, indent=2))


def save_quiz(topic: str, quiz: dict):
    """Save a generated quiz under a topic key."""
    bank = _load()
    key = topic.strip().lower()
    bank[key] = {
        "topic": topic,
        "quiz": quiz,
    }
    _save(bank)


def get_quiz(topic: str) -> dict | None:
    """Get a saved quiz for a topic. Returns None if not found."""
    bank = _load()
    key = topic.strip().lower()
    entry = bank.get(key)
    return entry["quiz"] if entry else None


def list_topics() -> list[str]:
    """Return all topics that have saved questions."""
    bank = _load()
    return [v["topic"] for v in bank.values()]


def delete_topic(topic: str):
    """Remove a topic and its questions from the bank."""
    bank = _load()
    key = topic.strip().lower()
    bank.pop(key, None)
    _save(bank)


def get_random_quiz() -> dict | None:
    """Return a random quiz from the bank."""
    import random
    bank = _load()
    if not bank:
        return None
    entry = random.choice(list(bank.values()))
    return entry["quiz"]
