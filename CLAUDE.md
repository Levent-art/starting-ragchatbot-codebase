# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RAG (Retrieval-Augmented Generation) chatbot for course materials. Full-stack app: FastAPI backend + vanilla JS frontend. Users ask questions about courses, the system searches semantically in ChromaDB and generates answers via Claude API with tool use.

## Important

Always use `uv` to run Python files, the server, and manage dependencies. Never use `pip` or `python` directly — use `uv run` instead.

## Commands

```bash
# Install dependencies
uv sync

# Run the app (from repo root)
./run.sh
# Or manually:
cd backend && uv run uvicorn app:app --reload --port 8000

# Access
# Web UI: http://localhost:8000
# API docs: http://localhost:8000/docs
```

## Environment Setup

Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`. The key is loaded in `backend/config.py` via python-dotenv.

## Architecture

### Data Flow

Query → `app.py` (FastAPI) → `rag_system.py` (orchestrator) → `ai_generator.py` (Claude API with tool use) → Claude calls `search_course_content` tool → `search_tools.py` → `vector_store.py` (ChromaDB semantic search) → results back to Claude → final response → frontend

### Backend (`backend/`)

- **app.py** — FastAPI app. Two endpoints: `POST /api/query` (process questions), `GET /api/courses` (course stats). Serves frontend as static files. On startup, auto-loads all `.txt/.pdf/.docx` files from `../docs/`.
- **rag_system.py** — Orchestrator. Wires together all components. `query()` is the main method: gets session history, calls AI generator with tools, collects sources, saves exchange.
- **ai_generator.py** — Claude API integration. Uses tool_use with `tool_choice: auto`. When Claude requests a tool, executes it via ToolManager and sends results back for a final response. Temperature: 0, max_tokens: 800.
- **search_tools.py** — Extensible tool system. `Tool` ABC defines the interface. `CourseSearchTool` wraps vector store search. `ToolManager` is a registry that handles tool execution and source tracking.
- **vector_store.py** — ChromaDB with two collections: `course_catalog` (course metadata, used for fuzzy name resolution) and `course_content` (text chunks). Embedding model: `all-MiniLM-L6-v2` via SentenceTransformers.
- **document_processor.py** — Parses course text files (expected format: `Course Title:`, `Lesson N:` headers). Splits into sentence-based chunks (800 chars, 100 overlap).
- **session_manager.py** — In-memory conversation history. Max 2 exchanges per session.
- **config.py** — Dataclass with all settings (model, chunk size, max results, etc.).
- **models.py** — Pydantic models: `Course`, `Lesson`, `CourseChunk`.

### Frontend (`frontend/`)

Vanilla HTML/CSS/JS. Dark theme. Uses `marked.js` for markdown rendering. Sidebar shows courses and suggested questions. Chat interface posts to `/api/query` and displays responses with collapsible sources.

### Course Documents (`docs/`)

Plain text files with specific format. Parsed by `document_processor.py`. New files placed here are auto-loaded on server startup (duplicates are skipped by title).

## Key Config Values (in `config.py`)

- Model: `claude-sonnet-4-20250514`
- Embedding: `all-MiniLM-L6-v2`
- Chunk size: 800 chars, overlap: 100
- Max search results: 5
- Max conversation history: 2 exchanges
- ChromaDB path: `./chroma_db` (relative to backend/)
