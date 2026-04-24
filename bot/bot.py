"""
bot/bot.py
──────────
Telegram bot logic for the Aircraft Engineer Quiz Bot.
- Engineers DM the bot to take quizzes
- Results are posted to the group leaderboard automatically
- /leaderboard works in both DM and group
"""

import os
import logging
from pathlib import Path
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv

load_dotenv()

from rag.retriever import ManualRetriever
from quiz.generator import QuizGenerator
from quiz.session import QuizSession, update_scoreboard, get_leaderboard
from quiz.bank import get_quiz, get_random_quiz, list_topics as bank_list_topics

log = logging.getLogger("quiz-bot")

# ── Config ────────────────────────────────────────────────────────────────────
GROUP_CHAT_ID_RAW = os.getenv("TELEGRAM_ALLOWED_CHAT_ID", "")
GROUP_CHAT_ID = int(GROUP_CHAT_ID_RAW) if GROUP_CHAT_ID_RAW.lstrip("-").isdigit() else None

retriever = ManualRetriever()
generator = QuizGenerator()

# Per-user pending topic selection state
PENDING_TOPIC: dict[str, bool] = {}

# Always resolve relative to this file's location (project root)
PROJECT_ROOT = Path(__file__).parent.parent
TOPICS_FILE = PROJECT_ROOT / "data" / "topics.json"


def _load_topics() -> list[str]:
    """Load admin-defined topics from the UI."""
    try:
        import json
        if TOPICS_FILE.exists():
            return json.loads(TOPICS_FILE.read_text())
        return []
    except Exception:
        return []


def esc(text: str) -> str:
    """Escape all MarkdownV2 reserved characters."""
    reserved = r'\_*[]()~`>#+-=|{}.!'
    return "".join(f"\\{c}" if c in reserved else c for c in str(text))


# ── Formatters ────────────────────────────────────────────────────────────────

def fmt_mcq_question(q: dict, index: int, total: int) -> tuple[str, ReplyKeyboardMarkup]:
    opts = q.get("options", {})
    options_text = "\n".join(f"*{k}:* {esc(v)}" for k, v in opts.items())
    text = (
        f"📋 *Question {index + 1} of {total}*\n"
        f"_Topic: {esc(q.get('topic', 'General'))}_\n\n"
        f"{esc(q['question'])}\n\n"
        f"{options_text}"
    )
    keyboard = ReplyKeyboardMarkup(
        [["A", "B"], ["C", "D"]],
        one_time_keyboard=True,
        resize_keyboard=True,
    )
    return text, keyboard


def fmt_short_question(q: dict, index: int, total: int) -> str:
    return (
        f"📋 *Question {index + 1} of {total}*\n"
        f"_Topic: {esc(q.get('topic', 'General'))}_\n\n"
        f"{esc(q['question'])}\n\n"
        f"_Type your answer below_"
    )


def fmt_mcq_feedback(result: dict) -> str:
    icon = "✅" if result["is_correct"] else "❌"
    if result["is_correct"]:
        status = "Correct\\!"
    else:
        status = f"Incorrect\\. Correct answer: *{esc(result['correct_answer'])}*"
    explanation = esc(result.get("explanation", ""))
    return f"{icon} {status}\n\n📖 _{explanation}_"


def fmt_short_feedback(result: dict) -> str:
    ev = result.get("evaluation", {})
    score = ev.get("score", 0)
    max_score = ev.get("max_score", 10)
    passed = ev.get("is_passing", False)
    icon = "✅" if passed else "❌"
    feedback = esc(ev.get("feedback", ""))
    model_answer = esc(result.get("model_answer", ""))
    missed = ev.get("key_points_missed", [])
    missed_str = "\n".join(f"  • {esc(p)}" for p in missed) if missed else ""
    text = (
        f"{icon} *Score: {score}/{max_score}* "
        f"{'\\(Pass\\)' if passed else '\\(Not yet passing\\)'}\n\n"
        f"💬 {feedback}\n\n"
        f"📌 *Model Answer:* {model_answer}"
    )
    if missed_str:
        text += f"\n\n⚠️ *Key points missed:*\n{missed_str}"
    return text


def fmt_score_bar(pct: int) -> str:
    filled = round(pct / 10)
    return "█" * filled + "░" * (10 - filled)


def fmt_summary_dm(summary: dict) -> str:
    """Full summary sent to the engineer in DM."""
    pct = summary["percentage"]
    bar = fmt_score_bar(pct)
    passed_str = "✅ *PASS*" if summary["passed"] else "❌ *Did not pass \\(70% required\\)*"
    topic_lines = ""
    for topic, counts in summary.get("topic_breakdown", {}).items():
        topic_lines += f"\n  • {esc(topic)}: {counts['correct']}/{counts['total']}"
    sources = esc(", ".join(summary.get("manual_sources", [])) or "N/A")
    name = esc(summary['user_name'])
    time_taken = esc(summary['time_taken'])
    return (
        f"🏁 *Quiz Complete — {name}*\n\n"
        f"*Score:* {summary['score']}/{summary['total']} \\({pct}%\\)\n"
        f"`{bar}`\n\n"
        f"{passed_str}\n\n"
        f"⏱️ Time: {time_taken}\n"
        f"*Topic breakdown:*{topic_lines}\n\n"
        f"📚 Sources: _{sources}_\n\n"
        f"_Your result has been posted to the group\\._"
    )


def fmt_group_result(summary: dict) -> str:
    """Short result card posted to the group after a quiz."""
    pct = summary["percentage"]
    bar = fmt_score_bar(pct)
    passed_str = "✅ PASS" if summary["passed"] else "❌ Did not pass"
    name = esc(summary['user_name'])
    sources = esc(", ".join(summary.get("manual_sources", [])) or "N/A")
    return (
        f"📊 *Quiz Result — {name}*\n\n"
        f"*Score:* {summary['score']}/{summary['total']} \\({pct}%\\)\n"
        f"`{bar}`\n\n"
        f"{passed_str}\n"
        f"📚 _{sources}_"
    )


def fmt_leaderboard(board: list[dict]) -> str:
    if not board:
        return "📊 No scores yet\\. Engineers — DM the bot and type /quiz to get started\\!"
    lines = ["🏆 *Leaderboard — Top Scores*\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, entry in enumerate(board):
        medal = medals[i] if i < 3 else f"{i + 1}\\."
        status = "✅" if entry["passed"] else "❌"
        name = esc(entry['user_name'])
        time_taken = esc(entry['time_taken'])
        lines.append(
            f"{medal} *{name}* — "
            f"{entry['percentage']}% {status} "
            f"\\({entry['score']}/{entry['total']}\\) \\| {time_taken}"
        )
    return "\n".join(lines)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def post_to_group(bot: Bot, summary: dict):
    """Post quiz result + updated leaderboard to the group chat."""
    if not GROUP_CHAT_ID:
        return
    try:
        # Post individual result
        await bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=fmt_group_result(summary),
            parse_mode="MarkdownV2",
        )
        # Post updated leaderboard
        board = get_leaderboard()
        await bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=fmt_leaderboard(board),
            parse_mode="MarkdownV2",
        )
    except Exception as e:
        log.error("Failed to post to group: %s", e)


# ── Command Handlers ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topics = _load_topics()
    if topics:
        topic_lines = "\n".join(f"  • {esc(t)}" for t in topics)
        topics_section = f"\n\n📚 *Available topics:*\n{topic_lines}"
    else:
        topics_section = ""

    await update.message.reply_text(
        f"👋 Welcome to the *Aircraft Engineering Quiz Bot*\\!\n\n"
        f"I quiz probationary engineers on aircraft maintenance manuals\\."
        f"{topics_section}\n\n"
        f"Type /quiz to begin — you'll pick a topic and get started\\.\n"
        f"Type /leaderboard to see top scores\\.",
        parse_mode="MarkdownV2",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✈️ *Aircraft Engineering Quiz Bot*\n\n"
        "• /quiz — start a quiz \\(DM me\\)\n"
        "• /leaderboard — top scores\n"
        "• /quit — cancel current quiz\n"
        "• /help — this message\n\n"
        "_DM me to take a quiz\\. Your result will be posted to the AeroQuiz group\\._",
        parse_mode="MarkdownV2",
    )


async def cmd_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    # If typed in the group, redirect to DM
    if update.effective_chat.type in ["group", "supergroup"]:
        bot_username = (await context.bot.get_me()).username
        await update.message.reply_text(
            f"👋 DM me directly to take a quiz\\!\n\n"
            f"👉 [@{esc(bot_username)}](https://t.me/{bot_username})",
            parse_mode="MarkdownV2",
        )
        return

    # If topic passed directly e.g. /quiz hydraulics
    if context.args:
        topic = " ".join(context.args)
        await start_quiz_with_topic(update, user_id, topic)
        return

    # Load topics that have questions in the bank
    PENDING_TOPIC[user_id] = True
    topics = bank_list_topics()  # only shows topics with actual questions

    rows = [["🎲 Random Topic"]]
    pair = []
    for topic in topics:
        pair.append(f"📝 {topic}")
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)

    keyboard = ReplyKeyboardMarkup(rows, one_time_keyboard=True, resize_keyboard=True)

    if topics:
        topic_lines = "\n".join(f"• {esc(t)}" for t in topics)
        msg = f"📚 *Choose a topic:*\n\n{topic_lines}\n\n_Tap a button or type any topic freely\\._"
    else:
        msg = "📚 *No topics available yet\\.*\n\nAsk your trainer to generate questions in the web UI first\\."

    await update.message.reply_text(msg, parse_mode="MarkdownV2", reply_markup=keyboard)


async def start_quiz_with_topic(update: Update, user_id: str, topic: str):
    user_name = update.effective_user.full_name or "Engineer"

    # Strip emoji prefixes from keyboard buttons
    clean_topic = topic.replace("📄 ", "").replace("🎲 ", "").replace("📝 ", "").strip()
    is_random = clean_topic.lower() in ["random topic", "random", ""]

    await update.message.reply_text(
        "🔍 Loading your quiz\\.\\.\\.",
        parse_mode="MarkdownV2",
        reply_markup=ReplyKeyboardRemove(),
    )

    try:
        QuizSession.clear(user_id)

        # Pull from question bank (no API call)
        quiz = get_random_quiz() if is_random else get_quiz(clean_topic)

        if not quiz:
            await update.message.reply_text(
                f"❌ No questions found for *{esc(clean_topic)}*\\.\n\n"
                f"Ask your trainer to generate questions for this topic in the web UI\\.",
                parse_mode="MarkdownV2",
            )
            return

        session = QuizSession(user_id=user_id, user_name=user_name, quiz=quiz)
        session._save()

        topic_summary = esc(quiz.get("topic_summary", clean_topic))
        sources = esc(", ".join(quiz.get("manual_sources", [])))

        await update.message.reply_text(
            f"✈️ *Quiz Ready\\!*\n\n"
            f"📖 Topic: _{topic_summary}_\n"
            f"📚 Source: _{sources}_\n"
            f"❓ Questions: {session.total_questions}\n\n"
            f"Let's go\\!",
            parse_mode="MarkdownV2",
        )
        await send_question(update, session)

    except Exception as e:
        log.exception("Error starting quiz")
        await update.message.reply_text(f"❌ Error: {esc(str(e))}", parse_mode="MarkdownV2")


async def cmd_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    board = get_leaderboard()
    await update.message.reply_text(fmt_leaderboard(board), parse_mode="MarkdownV2")


async def cmd_quit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    PENDING_TOPIC.pop(user_id, None)
    QuizSession.clear(user_id)
    await update.message.reply_text(
        "Quiz cancelled\\. Type /quiz to start again\\.",
        parse_mode="MarkdownV2",
        reply_markup=ReplyKeyboardRemove(),
    )


# ── Answer Handler ────────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = (update.message.text or "").strip()

    # Ignore messages in group (bot only processes DMs for quizzes)
    if update.effective_chat.type in ["group", "supergroup"]:
        return

    # Handle topic selection
    if PENDING_TOPIC.get(user_id):
        PENDING_TOPIC.pop(user_id, None)
        await start_quiz_with_topic(update, user_id, text)
        return

    session = QuizSession.load(user_id)
    if not session or session.completed:
        await update.message.reply_text(
            "Type /quiz to start a quiz, or /help for commands\\.",
            parse_mode="MarkdownV2",
        )
        return

    if session.is_mcq:
        answer = text.upper()
        if answer not in ["A", "B", "C", "D"]:
            await update.message.reply_text(
                "Please tap *A*, *B*, *C*, or *D*\\.",
                parse_mode="MarkdownV2",
            )
            return
        result = session.submit_mcq_answer(answer)
        await update.message.reply_text(
            fmt_mcq_feedback(result),
            parse_mode="MarkdownV2",
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await update.message.reply_text("⏳ Evaluating your answer\\.\\.\\.", parse_mode="MarkdownV2")
        q = session.current_question
        evaluation = generator.evaluate_short_answer(q, text)
        result = session.submit_short_answer(text, evaluation)
        await update.message.reply_text(fmt_short_feedback(result), parse_mode="MarkdownV2")

    # Quiz complete
    if session.completed:
        summary = session.summary()
        update_scoreboard(summary)
        QuizSession.clear(user_id)

        # Send full summary to engineer in DM
        await update.message.reply_text(
            fmt_summary_dm(summary),
            parse_mode="MarkdownV2",
            reply_markup=ReplyKeyboardRemove(),
        )

        # Post result + leaderboard to group
        await post_to_group(context.bot, summary)
    else:
        await send_question(update, session)


# ── Question Sender ───────────────────────────────────────────────────────────

async def send_question(update: Update, session: QuizSession):
    q = session.current_question
    if not q:
        return
    if session.is_mcq:
        text, keyboard = fmt_mcq_question(q, session.current_index, session.total_questions)
        await update.message.reply_text(text, parse_mode="MarkdownV2", reply_markup=keyboard)
    else:
        text = fmt_short_question(q, session.current_index, session.total_questions)
        await update.message.reply_text(text, parse_mode="MarkdownV2", reply_markup=ReplyKeyboardRemove())


# ── App Builder ───────────────────────────────────────────────────────────────

def build_app() -> Application:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token or token.startswith("REPLACE"):
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("quiz", cmd_quiz))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CommandHandler("scores", cmd_leaderboard))
    app.add_handler(CommandHandler("quit", cmd_quit))
    app.add_handler(CommandHandler("stop", cmd_quit))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app
