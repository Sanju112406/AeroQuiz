# ✈️ AeroQuiz - AI-Powered Training Platform for Aircraft Engineers

> **Built for the Anthropic x Temasek Hackathon** | Powered by **Claude Sonnet 4.5** & **GenSpark Claw**

<p align="center">
  <img src="https://img.shields.io/badge/Anthropic-Claude%20Sonnet%204.5-blueviolet?style=for-the-badge" alt="Claude Sonnet 4.5"/>
  <img src="https://img.shields.io/badge/GenSpark-Claw-orange?style=for-the-badge" alt="GenSpark Claw"/>
  <img src="https://img.shields.io/badge/Platform-Telegram-blue?style=for-the-badge" alt="Telegram"/>
  <img src="https://img.shields.io/badge/Industry-Aviation%20MRO-green?style=for-the-badge" alt="Aviation MRO"/>
</p>

---

## 🎯 Problem Statement

Singapore Airlines' aircraft maintenance engineers face a critical challenge: **rapidly upskilling probationary engineers** while ensuring they have deep knowledge of complex aircraft systems, safety protocols, and maintenance procedures. Traditional training methods are time-consuming and don't scale effectively.

**The Mobile Workforce Challenge:** Unlike desk workers, aircraft engineers are stationed in **hangars working on planes** — they don't have access to laptops or desktop computers. However, every engineer carries an **iPad** loaded with aircraft manuals and company apps. This creates a unique opportunity for mobile-first training solutions.

---

## 💡 Our Solution

**AeroQuiz** is an intelligent Telegram-based quiz platform that:

- 📱 **Built for the Hangar Floor** - Telegram runs seamlessly on the iPads engineers already carry, enabling training **on-the-fly** between tasks without leaving the hangar
- 🤖 **Leverages GenSpark Claw** to seamlessly connect with Telegram, intelligently handle user queries, and provide real-time conversational interactions
- 🧠 **Powered by Claude Sonnet 4.5** for intelligent question generation, answer evaluation, and detailed explanations for incorrect responses
- 📚 **RAG Pipeline** that ingests aircraft PDF manuals and technical documentation to generate contextually relevant questions
- ⚡ **Expedites certification** by enabling trainees to learn faster through active recall and instant feedback
Link to Demo: https://youtu.be/ysos1zIAldw
---

## 🌟 Key Features

### For Engineers (Trainees)
- 📱 **Telegram-Native** - Quiz anytime, anywhere directly in Telegram
- 🎯 **Adaptive Quizzing** - Questions generated from actual maintenance manuals
- 💬 **Intelligent Feedback** - Wrong answers receive detailed explanations powered by Claude
- 🏆 **Leaderboard** - Track progress and compete with peers
- 📊 **Topic-Specific Training** - Focus on hydraulics, avionics, engines, and more

### For Admins
- 📤 **Easy Document Upload** - Simply upload PDF manuals
- 🔄 **Automatic Ingestion** - GenSpark Claw processes and indexes documents
- 🎚️ **Configurable Difficulty** - Set quiz difficulty levels
- 📈 **Progress Tracking** - Monitor trainee performance

---

## 🚀 Vision: AI MRO Ecosystem

AeroQuiz is designed to be the foundation of a comprehensive **AI-powered MRO (Maintenance, Repair, and Overhaul) Ecosystem**:

| Module | Description |
|--------|-------------|
| 📖 **Tech Log Knowledgebase** | Beyond OEM manuals - integrated technical logs and historical data |
| 🔧 **Procurement & Parts** | Intelligent part identification and warehouse location |
| 📦 **Inventory Optimization** | Smart inventory placement and stock management |
| 👥 **Workforce Matching** | AI-driven assignment of best-fit engineers to tasks |
| 📋 **Customer Orders** | Handle customer complaints and service requests |
| ✅ **Quality Assurance** | Quality checks and delivery verification |
| ⏱️ **TAT & Safety** | Turnaround time optimization linked with safety compliance |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     ADMIN WORKFLOW                               │
│  Aircraft Manuals (PDFs) → GenSpark Claw → Document Ingestion   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      RAG PIPELINE                                │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ rag/ingest.py│ → │   ChromaDB   │ → │rag/retriever │      │
│  │ (Chunking)   │    │ (Vector DB)  │    │  (Search)    │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   INTELLIGENCE LAYER                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Claude Sonnet 4.5 (Anthropic API)            │   │
│  │  • Question Generation    • Answer Evaluation             │   │
│  │  • Explanation Generation • Adaptive Difficulty           │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   GENSPARK CLAW INTEGRATION                      │
│  • Telegram Bot Connection    • Intelligent Query Handling      │
│  • Natural Language Interface • Real-time Response Management   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TELEGRAM BOT                                │
│  Singapore Airlines Engineers ←→ Private Telegram Group         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **LLM** | Claude Sonnet 4.5 (Anthropic) |
| **Orchestration** | GenSpark Claw |
| **Vector Database** | ChromaDB |
| **Bot Platform** | Telegram (python-telegram-bot) |
| **Backend** | Python |
| **Embeddings** | Local / OpenAI |

---

## 📱 Bot Commands

| Command | Description |
|---------|-------------|
| `/quiz` | Start a random quiz from all manuals |
| `/quiz [topic]` | Quiz on a specific topic (e.g., `/quiz hydraulics`) |
| `/leaderboard` | View top scores |
| `/quit` | Cancel current quiz |
| `/help` | Show available commands |

---

## 🚀 Quick Start

### 1. Setup Environment
```bash
cd AeroQuiz
bash scripts/setup.sh
```

### 2. Configure Environment Variables
```bash
# Create .env file with:
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
ANTHROPIC_API_KEY=your-anthropic-api-key
TELEGRAM_ALLOWED_CHAT_ID=your-private-group-id
```

### 3. Add Training Manuals
```bash
cp /path/to/aircraft-manuals/*.pdf manuals/
```

### 4. Ingest Documents
```bash
source .venv/bin/activate
python rag/ingest.py
```

### 5. Run the Bot
```bash
python -m bot.app
```

---

## 📁 Project Structure

```
AeroQuiz/
├── bot/
│   ├── bot.py              # Telegram bot handlers
│   └── app.py              # Polling runner entry point
├── quiz/
│   ├── generator.py        # Claude-powered quiz generation
│   └── session.py          # Per-user session state
├── rag/
│   ├── ingest.py           # PDF → ChromaDB ingestion
│   └── retriever.py        # Semantic search
├── ui/                     # Admin interface
├── scripts/
│   ├── setup.sh
│   └── ingest_and_test.sh
├── data/
│   ├── chromadb/           # Vector store
│   └── scoreboard.json     # Leaderboard data
└── manuals/                # Drop PDFs here
```

---

## 🔒 Security

- Private Telegram group sandboxing via `TELEGRAM_ALLOWED_CHAT_ID`
- No public webhooks - polling-based architecture
- API keys secured in `.env` (never committed)
- Local data storage for scores and sessions

---

## 👥 Team

| Name | Role |
|------|------|
| **Sanju** | Developer |
| **Sahil Sharma** | Developer |
| **Shoeb** | Developer |

---

## 🏆 Hackathon

<p align="center">
  <strong>Anthropic x Temasek Hackathon</strong><br/>
  <em>Organized by GenSpark, Anthropic & Temasek</em>
</p>

---

## 📄 License

This project was built for the Anthropic x Temasek Hackathon.

---

<p align="center">
  Made with ❤️ for Singapore Airlines Engineering
</p>
