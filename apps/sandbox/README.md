# Sandbox Service

Python-based LLM orchestration service for report-writer.

## Setup

1. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -e .
   # Or for development:
   pip install -e ".[dev]"
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. **Run the server:**
   ```bash
   python src/sandbox/main.py
   # Or:
   uvicorn sandbox.main:app --reload
   ```

## API Endpoints

### Health Check
```
GET /health
```

### Agent Run
```
POST /v1/agent/run
```

**Request:**
```json
{
  "thread_id": "string",
  "messages": [{"role": "user", "content": "string"}],
  "context": {
    "sections": [{"id": "string", "title": "string"}],
    "blocks": [{"id": "string", "markdown_text": "string"}]
  }
}
```

**Response:**
```json
{
  "agent_message": "string",
  "proposed_edits": [
    {"block_id": "string", "new_markdown_text": "string"}
  ]
}
```

## Project Structure

```
apps/sandbox/
├── src/sandbox/
│   ├── main.py              # FastAPI app
│   ├── api/
│   │   └── agent_run.py     # Agent endpoints
│   ├── core/                # Business logic
│   └── test_doubles/        # Test utilities
├── pyproject.toml           # Dependencies
├── Dockerfile               # Container config
└── README.md
```
