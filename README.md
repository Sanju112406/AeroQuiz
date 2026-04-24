# ✈️ Aircraft Engineer Quiz Bot (Telegram)

A private Telegram group bot that quizzes probationary Aircraft Maintenance Engineers (AMEs)
using Anthropic Claude + a RAG system built on your actual maintenance manuals.

---

## Architecture

```
Aircraft Manuals (PDFs)
        │
        ▼
  [rag/ingest.py]          ← Chunks + embeds PDFs into ChromaDB
        │
        ▼
   ChromaDB (local)        ← Persistent vector store
        │
        ▼
  [rag/retriever.py]       ← Semantic search on manual content
        │
        ▼
  [quiz/generator.py]      ← Anthropic Claude generates quiz questions
        │
        ▼
  [quiz/session.py]        ← Per-user session state + scoreboard
        │
        ▼
    [bot/bot.py]           ← Telegram bot logic + formatting
        │
        ▼
    [bot/app.py]           ← python-telegram-bot polling runner
        │
        ▼
  Telegram Private Group   ← Sandboxed via TELEGRAM_ALLOWED_CHAT_ID
```

---

## Quick Start

### 1. Setup environment
```bash
cd aircraft-quiz-bot
bash scripts/setup.sh
```

### 2. Create your Telegram bot
1. Open Telegram → search **@BotFather**
2. Send `/newbot` → follow prompts → copy the token
3. Edit `.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456789:AAF...your-token-here
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   ```

### 3. Get your private group/channel chat ID
1. Add **@userinfobot** to your private group
2. It will reply with the group's chat ID (a negative number like `-1001234567890`)
3. Edit `.env`:
   ```
   TELEGRAM_ALLOWED_CHAT_ID=-1001234567890
   ```
4. Add your bot to the private group and make it an **admin**

### 4. Add manuals
```bash
cp /path/to/your-manual.pdf manuals/
```

### 5. Ingest manuals into vector store
```bash
source .venv/bin/activate
python rag/ingest.py
```

### 6. Test end-to-end (before Telegram)
```bash
bash scripts/ingest_and_test.sh
```

### 7. Run the bot
```bash
source .venv/bin/activate
python -m bot.app
```

The bot uses **polling** — no public URL or webhook setup needed.

---

## Bot Commands (in Telegram)

| Command | Description |
|---|---|
| `/quiz` | Start a random quiz from all manuals |
| `/quiz hydraulics` | Quiz on a specific topic |
| `/leaderboard` | See top scores |
| `/quit` | Cancel current quiz |
| `/help` | Show commands |

MCQ answers are tapped on a reply keyboard (A / B / C / D).

---

## Sandboxing

Set `TELEGRAM_ALLOWED_CHAT_ID` in `.env` to your private group's chat ID.
The bot will silently ignore all messages from any other chat — so even if
someone finds the bot username, they can't interact with it.

---

## Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | *(required)* | From @BotFather |
| `TELEGRAM_ALLOWED_CHAT_ID` | *(recommended)* | Lock bot to one private group |
| `ANTHROPIC_API_KEY` | *(required)* | Your Anthropic API key |
| `ANTHROPIC_MODEL` | `claude-3-5-sonnet-20241022` | Claude model |
| `EMBEDDING_BACKEND` | `local` | `local` (no key) or `openai` |
| `QUIZ_NUM_QUESTIONS` | `5` | Questions per quiz |
| `QUIZ_DIFFICULTY` | `mixed` | `easy` / `medium` / `hard` / `mixed` |
| `QUIZ_FORMAT` | `mcq` | `mcq` / `short_answer` |
| `CHROMA_PERSIST_DIR` | `./data/chromadb` | Vector store path |

---

## Re-ingesting Manuals

```bash
python rag/ingest.py                 # add new, skip existing
python rag/ingest.py --reset         # wipe and re-ingest everything
python rag/ingest.py --file new.pdf  # single file only
```

---

## File Structure

```
aircraft-quiz-bot/
├── .env                    ← Config + secrets (never commit)
├── requirements.txt
├── README.md
├── manuals/                ← Drop PDFs here
├── rag/
│   ├── ingest.py           ← PDF → ChromaDB
│   └── retriever.py        ← Semantic search
├── quiz/
│   ├── generator.py        ← Anthropic quiz generation + evaluation
│   └── session.py          ← Per-user state + scoreboard
├── bot/
│   ├── bot.py              ← Telegram bot handlers
│   └── app.py              ← Polling runner entry point
├── data/
│   ├── chromadb/           ← Vector store (auto-created)
│   ├── sessions/           ← Active quiz states (auto-created)
│   └── scoreboard.json     ← All-time scores
├── logs/
│   └── bot.log
└── scripts/
    ├── setup.sh
    └── ingest_and_test.sh
```

---

## Security Notes

- `.env` is in `.gitignore` — never commit it
- `TELEGRAM_ALLOWED_CHAT_ID` sandboxes the bot to your private group only
- No webhook = no public URL exposed
- Scores stored locally; only Telegram user ID + display name are persisted
