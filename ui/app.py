"""
ui/app.py
─────────
Local web UI for AeroQuiz trainer tool.
  Tab 1 — Ingest Manuals   : upload PDFs → ChromaDB
  Tab 2 — Create Quiz      : trainer generates & previews all questions
  Tab 3 — Take Quiz        : interactive step-by-step quiz
  Tab 4 — Leaderboard
"""

import os
import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import gradio as gr
import chromadb

from rag.ingest import ingest_pdf, get_embedding_function
from rag.retriever import ManualRetriever
from quiz.bank import save_quiz, list_topics as bank_list_topics, delete_topic as bank_delete_topic
from quiz.generator import QuizGenerator
from quiz.session import get_leaderboard

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/chromadb")
MANUALS_DIR = Path("./manuals")
MANUALS_DIR.mkdir(exist_ok=True)
TOPICS_FILE = Path(__file__).parent.parent / "data" / "topics.json"

_session = {}
_generated_quiz = {}   # stores trainer-generated quiz for preview


# ── TOPICS ────────────────────────────────────────────────────────────────────

def load_topics() -> list[str]:
    try:
        import json
        if TOPICS_FILE.exists():
            return json.loads(TOPICS_FILE.read_text())
        return []
    except Exception:
        return []


def save_topics(topics: list[str]):
    import json
    TOPICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOPICS_FILE.write_text(json.dumps(sorted(set(t.strip() for t in topics if t.strip())), indent=2))


def add_topic(new_topic: str) -> tuple[str, str]:
    if not new_topic.strip():
        return "⚠️ Topic name cannot be empty.", render_topics()
    topics = load_topics()
    if new_topic.strip() in topics:
        return f"⚠️ '{new_topic.strip()}' already exists.", render_topics()
    topics.append(new_topic.strip())
    save_topics(topics)
    return f"✅ Added topic: **{new_topic.strip()}**", render_topics()


def delete_topic(topic: str) -> tuple[str, str]:
    topics = load_topics()
    if topic not in topics:
        return f"⚠️ Topic not found.", render_topics()
    topics.remove(topic)
    save_topics(topics)
    return f"🗑️ Removed: **{topic}**", render_topics()


def render_topics() -> str:
    topics = load_topics()
    if not topics:
        return "📭 No topics defined yet. Add some above."
    lines = ["**Available Quiz Topics:**\n"]
    for t in sorted(topics):
        lines.append(f"• {t}")
    return "\n".join(lines)


def get_collection():
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    return client.get_or_create_collection(
        name="aircraft_manuals",
        embedding_function=get_embedding_function(),
        metadata={"hnsw:space": "cosine"},
    )


# ── INGEST ────────────────────────────────────────────────────────────────────

def upload_and_ingest(files):
    if not files:
        return "⚠️ No files selected.", list_manuals()
    collection = get_collection()
    results = []
    for file in files:
        src = Path(file) if isinstance(file, str) else Path(file.name)
        dest = MANUALS_DIR / src.name
        shutil.copy(src, dest)
        chunks = ingest_pdf(dest, collection)
        results.append(f"✅ **{dest.name}** — {chunks} chunks indexed")
    results.append(f"\n📊 Total in store: **{collection.count()}** chunks")
    return "\n".join(results), list_manuals()


def list_manuals():
    try:
        collection = get_collection()
        results = collection.get(include=["metadatas"])
        manuals = {}
        for meta in results["metadatas"]:
            name = meta.get("manual", "Unknown")
            manuals[name] = manuals.get(name, 0) + 1
        if not manuals:
            return "📂 No manuals ingested yet."
        lines = ["**Ingested Manuals:**\n"]
        for name, count in sorted(manuals.items()):
            lines.append(f"• {name} — {count} chunks")
        lines.append(f"\n📊 Total: {sum(manuals.values())} chunks")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ {e}"


def reset_collection():
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    try:
        client.delete_collection("aircraft_manuals")
        return "🗑️ Vector store cleared.", list_manuals()
    except Exception as e:
        return f"❌ {e}", list_manuals()


# ── SHARED HELPERS ────────────────────────────────────────────────────────────

def _build_retriever_and_generator():
    retriever = ManualRetriever()
    generator = QuizGenerator()
    return retriever, generator


def _fetch_chunks(retriever, topic):
    return retriever.retrieve(topic) if topic.strip() else retriever.random_topic_chunks()


# ── CREATE QUIZ (trainer preview) ─────────────────────────────────────────────

def generate_quiz_preview(topic, n_questions, difficulty, fmt):
    """Generate questions and return a full formatted preview for the trainer."""
    global _generated_quiz
    _generated_quiz = {}

    try:
        retriever, generator = _build_retriever_and_generator()
    except FileNotFoundError:
        return "❌ No manuals ingested yet. Go to **Ingest Manuals** tab first."
    except ValueError as e:
        return f"⚙️ {e}"
    except Exception as e:
        return f"❌ Error initialising: {e}"

    try:
        chunks = _fetch_chunks(retriever, topic)
    except Exception as e:
        return f"❌ RAG retrieval error: {e}"

    if not chunks:
        return "❌ No content found for that topic."

    try:
        quiz = generator.generate(chunks, n_questions=int(n_questions), difficulty=difficulty, format=fmt)
    except Exception as e:
        return f"❌ Quiz generation error: {e}"

    _generated_quiz = quiz
    return _render_full_quiz_html(quiz, show_answers=True)


def _render_full_quiz_html(quiz, show_answers=True):
    """Render all questions as styled HTML for the trainer preview."""
    questions = quiz.get("questions", [])
    sources = ", ".join(quiz.get("manual_sources", []))
    topic_summary = quiz.get("topic_summary", "")
    fmt = quiz.get("format", "mcq")

    html = f"""
    <div style="font-family: sans-serif; max-width: 860px;">
      <div style="background:#1e3a5f; color:#e8f4fd; border-radius:10px; padding:16px 20px; margin-bottom:20px;">
        <h3 style="margin:0 0 6px 0;">✈️ Quiz Preview</h3>
        <p style="margin:2px 0; font-size:0.9em;">📖 {topic_summary}</p>
        <p style="margin:2px 0; font-size:0.9em;">📚 Sources: {sources}</p>
        <p style="margin:2px 0; font-size:0.9em;">❓ {len(questions)} questions · {fmt.upper()}</p>
      </div>
    """

    for i, q in enumerate(questions, 1):
        diff_color = {"easy": "#2d6a2d", "medium": "#7a5a00", "hard": "#7a1f1f"}.get(
            q.get("difficulty", "medium"), "#444"
        )
        html += f"""
      <div style="background:#1a1a2e; border:1px solid #2a2a4a; border-radius:10px;
                  padding:18px 22px; margin-bottom:16px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
          <span style="color:#a0c4ff; font-weight:600; font-size:0.95em;">
            Question {i} of {len(questions)}
          </span>
          <span style="background:{diff_color}; color:#fff; padding:2px 10px;
                       border-radius:12px; font-size:0.78em; text-transform:uppercase;">
            {q.get('difficulty','medium')} · {q.get('topic','General')}
          </span>
        </div>
        <p style="font-size:1.05em; font-weight:500; color:#f0f0f0; margin:0 0 14px 0;">
          {q['question']}
        </p>
        """

        if fmt == "mcq":
            opts = q.get("options", {})
            correct = q.get("correct_answer", "").upper()
            for key, val in opts.items():
                is_correct = show_answers and key.upper() == correct
                bg = "#1a3d1a" if is_correct else "#16213e"
                border = "#4caf50" if is_correct else "#2a2a4a"
                tick = " ✅" if is_correct else ""
                html += f"""
        <div style="background:{bg}; border:1px solid {border}; border-radius:7px;
                    padding:10px 14px; margin-bottom:8px; color:#e0e0e0;">
          <strong style="color:#a0c4ff;">{key}.</strong>&nbsp;&nbsp;{val}{tick}
        </div>"""
            if show_answers:
                html += f"""
        <div style="margin-top:12px; padding:10px 14px; background:#0d1b2a;
                    border-left:3px solid #4a9eff; border-radius:4px; font-size:0.88em; color:#b0c8e8;">
          📖 {q.get('explanation','')}
        </div>"""
        else:
            html += f"""
        <div style="background:#16213e; border:1px solid #2a2a4a; border-radius:7px;
                    padding:10px 14px; color:#c0d8f0; font-size:0.9em;">
          <strong>Model Answer:</strong> {q.get('model_answer','')}
        </div>"""

        html += "\n      </div>"

    html += "\n    </div>"
    return html


# ── TAKE QUIZ (interactive) ───────────────────────────────────────────────────

def start_quiz(topic, n_questions, difficulty, fmt):
    global _session
    _session = {}

    # Pull from question bank — no API call
    from quiz.bank import get_quiz, get_random_quiz
    clean_topic = (topic or "").replace("🎲 ", "").strip()
    is_random = not clean_topic or clean_topic.lower() in ["random", "🎲 random"]

    quiz = get_random_quiz() if is_random else get_quiz(clean_topic)

    if not quiz:
        return (
            _error_html(f"No questions found for '{clean_topic}'. Generate them in the Create Quiz tab first."),
            "", gr.update(visible=False), gr.update(visible=False)
        )

    _session = {"quiz": quiz, "index": 0, "score": 0, "answers": [], "format": quiz.get("format", "mcq")}

    sources = ", ".join(quiz.get("manual_sources", []))
    header_html = f"""
    <div style="background:#1e3a5f; color:#e8f4fd; border-radius:10px;
                padding:14px 20px; font-family:sans-serif;">
      <strong>✈️ Quiz Started</strong> &nbsp;|&nbsp;
      📖 {quiz.get('topic_summary','Aircraft maintenance')} &nbsp;|&nbsp;
      📚 {sources} &nbsp;|&nbsp;
      ❓ {len(quiz['questions'])} questions
    </div>"""

    q_html = _render_question_html(0)
    show_mcq = fmt == "mcq"
    return header_html, q_html, gr.update(visible=show_mcq), gr.update(visible=not show_mcq)


def _render_question_html(index):
    quiz = _session.get("quiz", {})
    questions = quiz.get("questions", [])
    if index >= len(questions):
        return ""
    q = questions[index]
    total = len(questions)
    fmt = _session.get("format", "mcq")

    diff_color = {"easy": "#2d6a2d", "medium": "#7a5a00", "hard": "#7a1f1f"}.get(
        q.get("difficulty", "medium"), "#444"
    )

    html = f"""
    <div style="font-family:sans-serif; max-width:800px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <span style="color:#a0c4ff; font-weight:600;">Question {index + 1} of {total}</span>
        <span style="background:{diff_color}; color:#fff; padding:2px 10px;
                     border-radius:12px; font-size:0.78em; text-transform:uppercase;">
          {q.get('difficulty','medium')} · {q.get('topic','General')}
        </span>
      </div>
      <p style="font-size:1.08em; font-weight:500; color:#f0f0f0; line-height:1.6;
                background:#1a1a2e; padding:16px 18px; border-radius:8px; margin-bottom:16px;">
        {q['question']}
      </p>"""

    if fmt == "mcq":
        for key, val in q.get("options", {}).items():
            html += f"""
      <div style="background:#16213e; border:1px solid #2a2a4a; border-radius:8px;
                  padding:12px 16px; margin-bottom:8px; color:#e0e0e0; cursor:pointer;">
        <strong style="color:#a0c4ff; font-size:1em;">{key}.</strong>
        &nbsp;&nbsp;<span style="font-size:0.97em;">{val}</span>
      </div>"""
    else:
        html += """
      <p style="color:#a0c4ff; font-style:italic; margin-top:4px;">
        ✏️ Type your answer in the box below.
      </p>"""

    html += "\n    </div>"
    return html


def _error_html(msg):
    return f"""<div style="background:#3d1a1a; border:1px solid #a03030; border-radius:8px;
                padding:14px 18px; color:#f0a0a0; font-family:sans-serif;">
      ❌ {msg}</div>"""


def submit_answer(mcq_choice, short_text):
    global _session
    if not _session:
        return _error_html("Start a quiz first."), "", gr.update(visible=True), gr.update(visible=False)

    fmt = _session.get("format", "mcq")
    quiz = _session["quiz"]
    index = _session["index"]
    q = quiz["questions"][index]

    if fmt == "mcq":
        if not mcq_choice:
            return _feedback_html("⚠️ Please select A, B, C, or D.", "warn"), \
                   _render_question_html(index), gr.update(visible=True), gr.update(visible=False)
        submitted = mcq_choice.strip().upper()
        correct = q["correct_answer"].upper()
        is_correct = submitted == correct
        if is_correct:
            _session["score"] += 1
        _session["answers"].append({"id": q["id"], "correct": is_correct})
        _session["index"] += 1
        feedback = _feedback_html(
            f"{'✅ Correct!' if is_correct else f'❌ Incorrect — correct answer: <strong>{correct}</strong>'}"
            f"<br><small>📖 {q.get('explanation','')}</small>",
            "correct" if is_correct else "wrong"
        )
        show_mcq = gr.update(visible=True)
        show_sa = gr.update(visible=False)
    else:
        if not short_text.strip():
            return _feedback_html("⚠️ Please type your answer.", "warn"), \
                   _render_question_html(index), gr.update(visible=False), gr.update(visible=True)
        try:
            generator = QuizGenerator()
            evaluation = generator.evaluate_short_answer(q, short_text)
        except Exception as e:
            return _feedback_html(str(e), "wrong"), _render_question_html(index), \
                   gr.update(visible=False), gr.update(visible=True)
        passed = evaluation.get("is_passing", False)
        if passed:
            _session["score"] += 1
        _session["answers"].append({"id": q["id"], "correct": passed})
        _session["index"] += 1
        score = evaluation.get("score", 0)
        feedback = _feedback_html(
            f"{'✅ Pass' if passed else '❌ Not yet passing'} — {score}/{evaluation.get('max_score',10)}"
            f"<br>{evaluation.get('feedback','')}"
            f"<br><small>📌 Model: {q.get('model_answer','')}</small>",
            "correct" if passed else "wrong"
        )
        show_mcq = gr.update(visible=False)
        show_sa = gr.update(visible=True)

    if _session["index"] >= len(quiz["questions"]):
        return feedback, _build_summary_html(), gr.update(visible=False), gr.update(visible=False)

    return feedback, _render_question_html(_session["index"]), show_mcq, show_sa


def _feedback_html(msg, kind="correct"):
    colors = {
        "correct": ("#1a3d1a", "#4caf50", "#c8f0c8"),
        "wrong":   ("#3d1a1a", "#e05050", "#f0c8c8"),
        "warn":    ("#3d3000", "#c8a000", "#f0e090"),
    }
    bg, border, text = colors.get(kind, colors["correct"])
    return f"""<div style="background:{bg}; border:1px solid {border}; border-radius:8px;
               padding:13px 16px; color:{text}; font-family:sans-serif; line-height:1.6;">
      {msg}</div>"""


def _build_summary_html():
    quiz = _session.get("quiz", {})
    total = len(quiz.get("questions", []))
    score = _session.get("score", 0)
    pct = round((score / total) * 100) if total else 0
    passed = pct >= 70
    filled = round(pct / 10)
    bar = "█" * filled + "░" * (10 - filled)
    color = "#4caf50" if passed else "#e05050"
    return f"""
    <div style="font-family:sans-serif; background:#1a1a2e; border:2px solid {color};
                border-radius:12px; padding:24px 28px; max-width:500px;">
      <h2 style="color:{color}; margin-top:0;">🏁 Quiz Complete!</h2>
      <p style="font-size:1.3em; color:#f0f0f0;"><strong>{score}/{total}</strong> &nbsp;({pct}%)</p>
      <p style="font-family:monospace; font-size:1.4em; color:{color}; letter-spacing:2px;">{bar}</p>
      <p style="font-size:1.1em; color:{color};">
        {'✅ PASS' if passed else '❌ Did not pass (70% required)'}
      </p>
      <p style="color:#888; font-size:0.85em;">
        📚 {', '.join(quiz.get('manual_sources',[]))}
      </p>
      <p style="color:#aaa; font-size:0.85em;">Click <strong>Start Quiz</strong> to try again.</p>
    </div>"""


def get_leaderboard_text():
    board = get_leaderboard()
    if not board:
        return "No scores yet. Complete a quiz to appear here."
    lines = ["### 🏆 Leaderboard\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, entry in enumerate(board):
        medal = medals[i] if i < 3 else f"{i+1}."
        lines.append(
            f"{medal} **{entry['user_name']}** — {entry['percentage']}% "
            f"({'✅' if entry['passed'] else '❌'}) | {entry['time_taken']}"
        )
    return "\n".join(lines)


# ── UI ────────────────────────────────────────────────────────────────────────

with gr.Blocks(title="✈️ AeroQuiz") as demo:

    gr.HTML("""
    <div style="padding:18px 0 8px 0; font-family:sans-serif;">
      <h1 style="margin:0; font-size:1.6em;">✈️ AeroQuiz</h1>
      <p style="margin:4px 0 0 0; color:#888; font-size:0.9em;">
        Aircraft Engineer Quiz Bot &nbsp;·&nbsp; Powered by Claude + RAG
      </p>
    </div>""")

    with gr.Tabs():

        # ── Tab 1: Ingest ──────────────────────────────────────────────────────
        with gr.Tab("📚 Ingest Manuals"):
            gr.Markdown("Upload aircraft maintenance manual PDFs to build the knowledge base.")
            upload = gr.File(label="Drop PDFs here", file_types=[".pdf"], file_count="multiple")
            with gr.Row():
                ingest_btn = gr.Button("⚡ Ingest PDFs", variant="primary")
                refresh_btn = gr.Button("🔄 Refresh List")
                reset_btn = gr.Button("🗑️ Clear Store", variant="stop")
            ingest_out = gr.Markdown()
            manual_list = gr.Markdown(value=list_manuals())

            ingest_btn.click(upload_and_ingest, inputs=upload, outputs=[ingest_out, manual_list])
            refresh_btn.click(list_manuals, outputs=manual_list)
            reset_btn.click(reset_collection, outputs=[ingest_out, manual_list])

        # ── Tab 2: Manage Topics ───────────────────────────────────────────────
        with gr.Tab("📝 Topics"):
            gr.Markdown(
                "### Manage Quiz Topics\n"
                "Topics you add here will appear as buttons when engineers type `/quiz` in Telegram.\n"
                "Each topic is used to search the manuals — so use names that match your manual content."
            )
            with gr.Row():
                topic_input = gr.Textbox(
                    label="New Topic",
                    placeholder="e.g. EFB Installation, Hydraulic Systems, Landing Gear...",
                    scale=3
                )
                add_btn = gr.Button("➕ Add Topic", variant="primary", scale=1)

            topic_status = gr.Markdown()
            topic_list = gr.Markdown(value=render_topics())

            gr.Markdown("**Remove a topic:**")
            with gr.Row():
                del_input = gr.Textbox(label="Topic to remove (type exactly)", scale=3)
                del_btn = gr.Button("🗑️ Remove", variant="stop", scale=1)

            add_btn.click(add_topic, inputs=topic_input, outputs=[topic_status, topic_list])
            topic_input.submit(add_topic, inputs=topic_input, outputs=[topic_status, topic_list])
            del_btn.click(delete_topic, inputs=del_input, outputs=[topic_status, topic_list])

        # ── Tab 3: Create Quiz (trainer) ───────────────────────────────────────
        with gr.Tab("🔧 Create Quiz"):
            gr.Markdown(
                "**Trainer view** — type a topic, generate questions, review them.\n\n"
                "✅ The topic is **automatically saved** and will appear as a button when engineers type `/quiz` in Telegram."
            )
            with gr.Row():
                cq_topic = gr.Textbox(label="Topic (optional)", placeholder="e.g. event panel installation — blank = random")
                cq_n = gr.Slider(1, 15, value=5, step=1, label="Questions")
                cq_diff = gr.Dropdown(["easy", "medium", "hard", "mixed"], value="mixed", label="Difficulty")
                cq_fmt = gr.Dropdown(["mcq", "short_answer"], value="mcq", label="Format")
            cq_btn = gr.Button("⚡ Generate Questions", variant="primary", size="lg")
            cq_topic_saved = gr.Markdown()
            cq_out = gr.HTML(value="<p style='color:#888;font-family:sans-serif;'>Generated questions will appear here with answers highlighted.</p>")

            def generate_and_save_topic(topic, n, diff, fmt):
                html = generate_quiz_preview(topic, n, diff, fmt)

                # Save quiz to question bank for Telegram bot to use
                if topic and topic.strip() and _generated_quiz:
                    quiz = _generated_quiz.copy()
                    save_quiz(topic.strip(), quiz)

                    # Also save topic name to topics list
                    topics = load_topics()
                    if topic.strip() not in topics:
                        topics.append(topic.strip())
                        save_topics(topics)

                    saved_msg = (
                        f"✅ **{topic.strip()}** — {len(quiz.get('questions', []))} questions saved to bot.\n\n"
                        f"Engineers will see this topic when they type `/quiz` in Telegram."
                    )
                elif not topic or not topic.strip():
                    saved_msg = "ℹ️ No topic entered — questions not saved to bot (random quiz only)."
                else:
                    saved_msg = "⚠️ Quiz generation may have failed — check questions above."

                return saved_msg, html

            cq_btn.click(
                generate_and_save_topic,
                inputs=[cq_topic, cq_n, cq_diff, cq_fmt],
                outputs=[cq_topic_saved, cq_out]
            )

        # ── Tab 3: Take Quiz (interactive) ─────────────────────────────────────
        with gr.Tab("🧠 Take Quiz"):
            gr.Markdown("**Engineer view** — pick a topic and answer questions. No API calls — uses saved questions from Create Quiz tab.")

            def get_bank_topics():
                from quiz.bank import list_topics as bank_topics
                topics = bank_topics()
                return ["🎲 Random"] + topics

            with gr.Row():
                tq_topic = gr.Dropdown(
                    choices=get_bank_topics(),
                    value="🎲 Random",
                    label="Topic",
                    allow_custom_value=True
                )
                tq_refresh = gr.Button("🔄", scale=0)
                tq_n = gr.Slider(1, 10, value=5, step=1, label="Questions")
                tq_diff = gr.Dropdown(["easy", "medium", "hard", "mixed"], value="mixed", label="Difficulty")
                tq_fmt = gr.Dropdown(["mcq", "short_answer"], value="mcq", label="Format")

            tq_refresh.click(get_bank_topics, outputs=tq_topic)
            tq_start_btn = gr.Button("🚀 Start Quiz", variant="primary", size="lg")

            tq_header = gr.HTML()
            tq_question = gr.HTML()

            with gr.Row(visible=True) as mcq_row:
                tq_mcq = gr.Radio(["A", "B", "C", "D"], label="Select your answer")

            with gr.Row(visible=False) as sa_row:
                tq_short = gr.Textbox(label="Your answer", lines=4, placeholder="Type your answer here…")

            tq_submit_btn = gr.Button("✅ Submit Answer", variant="primary")
            tq_feedback = gr.HTML()

            tq_start_btn.click(
                start_quiz,
                inputs=[tq_topic, tq_n, tq_diff, tq_fmt],
                outputs=[tq_header, tq_question, mcq_row, sa_row]
            )
            tq_submit_btn.click(
                submit_answer,
                inputs=[tq_mcq, tq_short],
                outputs=[tq_feedback, tq_question, mcq_row, sa_row]
            )

        # ── Tab 4: Leaderboard ─────────────────────────────────────────────────
        with gr.Tab("🏆 Leaderboard"):
            gr.Markdown("### Live leaderboard — auto-updates every 30 seconds as engineers complete quizzes via Telegram.")
            lb_btn = gr.Button("🔄 Refresh Now")
            lb_out = gr.Markdown(value=get_leaderboard_text())
            lb_btn.click(get_leaderboard_text, outputs=lb_out)


if __name__ == "__main__":
    print("🚀 AeroQuiz UI → http://127.0.0.1:7860")
    demo.queue()
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)
