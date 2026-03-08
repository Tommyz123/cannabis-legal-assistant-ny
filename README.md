# Cannabis Law Compliance Assistant - New York State

> An AI-powered legal compliance assistant for New York State cannabis retail dispensaries, built on a RAG architecture with hybrid retrieval. Supports regulatory Q&A and marketing content compliance review.

**Version:** MVP v1.0
**Release Date:** 2026-02-12
**Status:** Production-Ready

---

## Overview

Cannabis Law Compliance Assistant is a legal compliance tool purpose-built for NYS cannabis retail dispensaries. It provides two core capabilities:

1. **Regulatory Q&A (General Query)** — Answers compliance questions on licensing, packaging, operations, and taxation, grounded in 14 authoritative regulatory documents.
2. **Marketing Compliance Review (Strategy Review)** — Automatically detects prohibited slang, medical claims, and child-directed elements in advertising copy, and provides actionable remediation suggestions.

### Core Technology

- **RAG Architecture**: Retrieval-Augmented Generation pipeline grounded in official NYS cannabis regulations
- **Hybrid Retrieval**: Vector search (ChromaDB) + BM25 keyword search + RRF (Reciprocal Rank Fusion) re-ranking
- **Agent Orchestration**: LangGraph StateGraph (with automatic fallback to a local orchestrator)
- **LLM**: OpenAI GPT-4o-mini (generation) + text-embedding-3-small (embeddings)
- **Interfaces**: CLI (interactive & single-query) + FastAPI HTTP API
- **Multilingual Input**: Accepts Chinese-language queries with automatic translation before retrieval

---

## Project Structure

```
Cannabis_Law_Assistant/
├── main.py                     # CLI entry point (interactive mode & single-query mode)
├── query.py                    # RAG prototype (stable — do not modify)
├── build_database.py           # Database build script
├── check_database.py           # Database verification script
├── requirements.txt            # Core dependencies
├── .env                        # Environment variables (OPENAI_API_KEY)
│
├── src/
│   ├── retrieval/
│   │   └── pipeline.py         # RetrievalPipeline — Hybrid retrieval + RRF fusion
│   ├── agent/
│   │   ├── intent.py           # IntentClassifier — Intent recognition (rule-based + LLM)
│   │   ├── conversation.py     # ConversationManager — Multi-turn session management
│   │   ├── reviewer.py         # StrategyReviewer — Marketing content compliance review
│   │   ├── core.py             # AgentCore — LangGraph orchestration entry point
│   │   └── prompts.py          # Centralized prompt templates
│   └── api/
│       └── server.py           # FastAPI HTTP API
│
├── tests/
│   ├── conftest.py             # Shared fixtures (Mock OpenAI / ChromaDB)
│   ├── test_pipeline.py        # Task 1: Retrieval pipeline tests (6 cases)
│   ├── test_intent.py          # Task 2: Intent classification tests (6 cases)
│   ├── test_conversation.py    # Task 3: Conversation management tests (6 cases)
│   ├── test_reviewer.py        # Task 4: Strategy review tests (6 cases)
│   ├── test_agent_core.py      # Task 5: Agent core tests (8 cases)
│   └── test_api.py             # Task 7: HTTP API tests (12 cases)
│
├── knowledge/                  # 14 authoritative regulatory source documents (Markdown)
├── chroma_db/                  # ChromaDB vector database (pre-built)
└── bm25_index.pkl              # BM25 index (pre-built)
```

---

## Quick Start

### 1. Set Up the Environment

```bash
# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
pip install langgraph fastapi uvicorn pytest pytest-mock
```

### 2. Configure Your API Key

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
```

### 3. Verify the Database

```bash
# Check ChromaDB vector database
python -c "import chromadb; c=chromadb.PersistentClient('./chroma_db'); print('ChromaDB OK:', len(c.list_collections()), 'collections')"

# Check BM25 index
python -c "import pickle; d=pickle.load(open('bm25_index.pkl','rb')); print('BM25 OK:', len(d['chunk_ids']), 'chunks')"
```

If the database does not exist, build it first:

```bash
python build_database.py
```

---

## Usage

### CLI Mode

**Interactive mode** (multi-turn conversation):

```bash
python main.py
```

Example session:

```
Cannabis Law Assistant (type 'quit' to exit)
You: What are the packaging requirements for cannabis products?
[Answer] Under 9 NYCRR Part 119-120, cannabis products must be packaged in...
[Sources] 02_Packaging_Labeling.md § Part 119

You: Please review this ad copy: "Get High with our premium stoner products!"
[Review Result] Non-compliant — the following issues were detected:
  - prohibited_slang: Contains prohibited terms "High", "stoner"
[Compliance Reminders]
  - Audience age verification: Ensure 90%+ of the audience is 21 or older
  - Geographic restriction: No advertising within 500 feet of schools or childcare facilities
  - Outdoor advertising deadline: All outdoor ads must achieve compliance by 2026-02-24
```

**Single-query mode**:

```bash
python main.py "How do I apply for a New York State cannabis retail license?"
```

### HTTP API Mode

Start the server:

```bash
uvicorn src.api.server:app --reload --port 8000
```

API endpoints:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/session` | Create a session |
| DELETE | `/api/session/{id}` | Delete a session |
| POST | `/api/chat` | Send a message |

**Example requests**:

```bash
# 1. Create a session
curl -X POST http://localhost:8000/api/session
# Response: {"session_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"}

# 2. Send a message
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "your-session-id", "message": "What are the cannabis packaging requirements?"}'
```

**Response format**:

```json
{
  "intent": "general_query",
  "answer": "Under 9 NYCRR Part 119...",
  "sources": [
    {"file_name": "02_Packaging_Labeling.md", "domain": "packaging", "section_title": "Part 119"}
  ],
  "warnings": ["Note: Labeling requirements under Part 120 were updated on 2025-12-01"],
  "suggestions": ["Consult a licensed compliance advisor to confirm current requirements"]
}
```

---

## Module Reference

### RetrievalPipeline (`src/retrieval/pipeline.py`)

The hybrid retrieval core, combining vector search and keyword search:

- `search(query_en, top_k=3)` — Vector Top-10 + BM25 Top-10, fused via RRF, returns `list[ChunkResult]`
- `translate_if_chinese(text)` — Chinese-language detection and automatic translation
- `build_context(chunks)` — Assembles LLM context and collects timeliness warnings

### IntentClassifier (`src/agent/intent.py`)

Three-stage intent classification:

- **Stage 1**: Keyword rules (ad / copy / marketing / promotion / review) → `strategy_review`
- **Stage 2**: Conversation history continuation (defaults to prior intent when context is clear)
- **Stage 3**: LLM confirmation (for ambiguous inputs; degrades gracefully if unavailable)

### ConversationManager (`src/agent/conversation.py`)

In-memory multi-turn session management:

- UUID-based `session_id` with automatic ISO 8601 timestamps
- FIFO eviction policy with a maximum of 10 messages per session
- `create_session()` / `add_message()` / `get_history()` / `clear_session()`

### StrategyReviewer (`src/agent/reviewer.py`)

Rule-based marketing content compliance review:

- Prohibited content detection: slang (stoner / weed / pot / high / 420), medical claims (cure / therapeutic effect), cartoon or child-directed elements
- Three fixed compliance reminders: 21+ audience (90% LDA threshold), 500-foot exclusion zone, outdoor advertising deadline of 2026-02-24

### AgentCore (`src/agent/core.py`)

LangGraph StateGraph orchestration:

```
START → intent_node → route
  ├── general_query   → query_node  → response_node → END
  └── strategy_review → review_node → response_node → END
```

Automatically falls back to a local orchestrator when LangGraph is unavailable.

---

## Testing

```bash
# Activate the virtual environment
source venv/bin/activate

# Run all tests
pytest tests/ -v

# Run tests for a specific module
pytest tests/test_pipeline.py -v
pytest tests/test_api.py -v

# Generate a coverage report
pytest tests/ --cov=src --cov-report=term-missing
```

Test coverage: **44 test cases, all passing**. All tests use mocks to avoid real API calls.

---

## Knowledge Base

Built on 14 authoritative New York State cannabis regulatory documents (~240 KB), covering:

| Domain | Primary Document | Coverage |
|--------|-----------------|----------|
| General Regulations (NYCRR Title 9) | 01_General_Regs.md | 90% |
| Packaging & Labeling | 02_Packaging_Labeling.md | 90% |
| Security & Storage | 03_Security_Storage.md | 90% |
| Retail Operations | 04_Retail_Operations.md | 85% |
| **Marketing & Advertising (Part 129)** | 09_Marketing_Advertising.md | 95% |
| Laboratory Testing (Part 130) | 10_Laboratory_Testing.md | 95% |
| NYC Municipal Licensing (DCWP) | 12_NYC_DCWP_License.md | 85% |
| Violations & Penalties | 09_Violations_Penalties.md | 90% |
| Consumer Protection | 15_Consumer_Protection.md | 95% |
| Tax Compliance | 07_Tax_Guidance.md | 95% |
| Labor Rights | 08_Labor_Rights.md | 90% |
| Fire Safety (FDNY) | 06_FDNY_Fire_Code.md | 95% |

Sources: Cornell LII, NYS OCM, NYC DCWP, NYC FDNY (enacted regulations only)

---

## Code Quality

| Module | Pylint | Bandit |
|--------|--------|--------|
| src/retrieval/ | 8.56/10 | No high-severity findings |
| src/agent/intent.py | 9.58/10 | No high-severity findings |
| src/agent/conversation.py | 10.00/10 | No high-severity findings |
| src/agent/reviewer.py | 10.00/10 | No high-severity findings |
| src/agent/core.py | 9.09/10 | No high-severity findings |
| src/api/ | 9.19/10 | No high-severity findings |
| main.py | 10.00/10 | No high-severity findings |

---

## Dependencies

```
langchain==0.3.18
langchain-openai==0.3.6
openai==1.63.2
chromadb==0.6.3
tiktoken==0.9.0
python-dotenv==1.0.1
rank_bm25==0.2.2
langgraph          # Agent orchestration (optional — auto-fallback if missing)
fastapi            # HTTP API
uvicorn            # ASGI server
pytest             # Testing
pytest-mock        # External API mocking
```

---

## Important Notes

- **API Key Security**: The OpenAI API key is loaded exclusively from the `.env` file and must never be hard-coded.
- **Data Currency**: Regulatory data is current as of 2026-02-08. A quarterly review and update cycle is recommended.
- **Zero Fabrication Principle**: All prompts include an explicit constraint to cite only enacted regulations; the LLM is prohibited from generating fictional legal content.
- **Offline Degradation**: When network access is unavailable, CLI mode automatically falls back to BM25 offline retrieval with local summarization.

---

## Changelog

### MVP v1.0 (2026-02-12) — Agent Application Complete

- Task 1: RetrievalPipeline — Hybrid retrieval (Vector + BM25 + RRF)
- Task 2: IntentClassifier — Intent classification
- Task 3: ConversationManager — Multi-turn session management
- Task 4: StrategyReviewer — Marketing compliance review
- Task 5: AgentCore — LangGraph orchestration
- Task 6: CLI entry point
- Task 7: FastAPI HTTP API

### Legal DB v2.0 (2026-02-08) — Knowledge Base Complete

- 14 authoritative regulatory documents (~240 KB)
- Legal coverage: 85% | Content completeness: 90% | Overall score: 88/100
