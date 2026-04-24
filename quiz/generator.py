"""
quiz/generator.py
─────────────────
Uses Anthropic Claude to generate quiz questions from retrieved manual chunks.
"""

import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

import anthropic

# ── Config ───────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "sk-ant-REPLACE_WITH_YOUR_KEY_HERE")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
QUIZ_NUM_QUESTIONS = int(os.getenv("QUIZ_NUM_QUESTIONS", 5))
QUIZ_DIFFICULTY = os.getenv("QUIZ_DIFFICULTY", "mixed")
QUIZ_FORMAT = os.getenv("QUIZ_FORMAT", "mcq")

# ── Prompts ──────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert aviation training instructor creating quiz questions
for probationary Aircraft Maintenance Engineers (AMEs). Your questions must be:
- Based STRICTLY on the provided manual excerpts (no external knowledge)
- Technically precise and use correct aviation/maintenance terminology
- Appropriately challenging for entry-level engineers
- Safety-critical where relevant (emphasize procedures, warnings, limits)

Return ONLY valid JSON — no markdown, no preamble, no extra text."""

MCQ_PROMPT_TEMPLATE = """Based on the following aircraft manual excerpts, generate {n} multiple-choice quiz questions.

MANUAL EXCERPTS:
{context}

REQUIREMENTS:
- Difficulty: {difficulty}
- Each question must have exactly 4 options (A, B, C, D)
- Only one correct answer per question
- Include a brief explanation citing the manual source
- Focus on: procedures, limits, warnings, system operation, safety

Return this exact JSON structure:
{{
  "questions": [
    {{
      "id": 1,
      "question": "Question text here?",
      "options": {{
        "A": "Option A text",
        "B": "Option B text",
        "C": "Option C text",
        "D": "Option D text"
      }},
      "correct_answer": "B",
      "explanation": "According to [Manual Name] p.[X]: explanation here.",
      "topic": "Topic category (e.g. Hydraulics, Electrical, Structures)",
      "difficulty": "easy|medium|hard"
    }}
  ],
  "manual_sources": ["manual name 1", "manual name 2"],
  "topic_summary": "Brief summary of what this quiz covers"
}}"""

SHORT_ANSWER_PROMPT_TEMPLATE = """Based on the following aircraft manual excerpts, generate {n} short-answer quiz questions.

MANUAL EXCERPTS:
{context}

REQUIREMENTS:
- Difficulty: {difficulty}
- Questions should require 1-3 sentence answers
- Focus on procedures, safety limits, system descriptions
- Include model answers for evaluation

Return this exact JSON structure:
{{
  "questions": [
    {{
      "id": 1,
      "question": "Question text here?",
      "model_answer": "The complete model answer here.",
      "key_points": ["key point 1", "key point 2"],
      "explanation": "Why this is important for AMEs.",
      "topic": "Topic category",
      "difficulty": "easy|medium|hard"
    }}
  ],
  "manual_sources": ["manual name 1"],
  "topic_summary": "Brief summary of what this quiz covers"
}}"""


def format_context(chunks: list[dict]) -> str:
    """Format retrieved chunks into a readable context string."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(
            f"[Excerpt {i} — {chunk['manual']}, Page {chunk['page']}]\n"
            f"{chunk['text'].strip()}\n"
        )
    return "\n---\n".join(parts)


class QuizGenerator:
    def __init__(self):
        if ANTHROPIC_API_KEY.startswith("sk-ant-REPLACE"):
            raise ValueError(
                "⚠️  Anthropic API key not set. "
                "Edit .env and set ANTHROPIC_API_KEY=sk-ant-..."
            )
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def generate(
        self,
        chunks: list[dict],
        n_questions: int = QUIZ_NUM_QUESTIONS,
        difficulty: str = QUIZ_DIFFICULTY,
        format: str = QUIZ_FORMAT,
    ) -> dict:
        """
        Generate quiz questions from retrieved manual chunks.

        Returns:
            Parsed quiz dict with 'questions', 'manual_sources', 'topic_summary'
        """
        context = format_context(chunks)

        if format == "short_answer":
            prompt = SHORT_ANSWER_PROMPT_TEMPLATE.format(
                n=n_questions,
                difficulty=difficulty,
                context=context,
            )
        else:
            # Default: MCQ
            prompt = MCQ_PROMPT_TEMPLATE.format(
                n=n_questions,
                difficulty=difficulty,
                context=context,
            )

        response = self.client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()

        # Strip markdown code blocks if Claude wraps output
        raw = re.sub(r"^```(?:json)?\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

        quiz = json.loads(raw)
        quiz["format"] = format
        return quiz

    def evaluate_short_answer(self, question: dict, user_answer: str) -> dict:
        """
        Use Claude to evaluate a short-answer response against the model answer.

        Returns:
            Dict with: score (0-10), feedback, is_passing (bool)
        """
        eval_prompt = f"""You are evaluating a trainee aircraft engineer's answer.

QUESTION: {question['question']}
MODEL ANSWER: {question['model_answer']}
KEY POINTS (must cover): {', '.join(question.get('key_points', []))}

TRAINEE'S ANSWER: {user_answer}

Score the answer from 0-10 based on technical accuracy and coverage of key points.
Return ONLY this JSON:
{{
  "score": 7,
  "max_score": 10,
  "is_passing": true,
  "feedback": "Your answer correctly identified X but missed Y. The manual states...",
  "key_points_covered": ["point 1", "point 2"],
  "key_points_missed": ["point 3"]
}}"""

        response = self.client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": eval_prompt}],
        )

        raw = response.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        return json.loads(raw)
