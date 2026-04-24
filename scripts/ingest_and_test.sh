#!/bin/bash
# Quick test: ingest manuals + run a local quiz generation test
set -e

source .venv/bin/activate 2>/dev/null || true

echo "📚 Ingesting manuals..."
python rag/ingest.py --manuals-dir ./manuals

echo ""
echo "🧪 Running quiz generation test..."
python - <<'EOF'
from dotenv import load_dotenv
load_dotenv()

from rag.retriever import ManualRetriever
from quiz.generator import QuizGenerator

print("Connecting to vector store...")
r = ManualRetriever()
print(f"✅ Collection: {r.collection.count()} chunks indexed")
print(f"📚 Manuals: {r.list_manuals()}")

print("\nRetrieving random chunks...")
chunks = r.random_topic_chunks(top_k=3)
for c in chunks:
    print(f"  [{c['manual']} p.{c['page']}] {c['text'][:80]}...")

print("\nGenerating quiz (this calls Anthropic API)...")
g = QuizGenerator()
quiz = g.generate(chunks, n_questions=2)
print(f"✅ Generated {len(quiz['questions'])} questions")
print(f"   Topic: {quiz.get('topic_summary')}")
print(f"   Q1: {quiz['questions'][0]['question'][:80]}...")
print("\n✅ All systems go! Run: python -m bot.app")
EOF
