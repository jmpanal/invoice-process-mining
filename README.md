# Invoice Process Intelligence Lab

Local full-stack demo for invoice process mining, RAG-grounded AI analysis, human-approved improvements, and mock agent execution.

## Setup

```powershell
cd invoice-process-intel-lab
copy .env.example .env
docker compose up -d
```

Postgres is exposed on host port `55432` to avoid conflicts with local PostgreSQL installs.

## Backend

```powershell
cd apps/api
python -m pip install -e .[dev]
alembic upgrade head
uvicorn app.main:app --reload
pytest
```

## Frontend

```powershell
cd apps/web
npm install
npm run dev
npm run build
```

## Demo Flow

1. Generate ideal invoice process.
2. Generate 2,000 invoice cases with seed 42.
3. Mine the process.
4. Generate SOPs and policies.
5. Rebuild RAG index.
6. Ask an AI question.
7. Generate improvements.
8. Approve one action.
9. Run the mock agent and inspect generated config JSON.

## Limitations

- Uses synthetic data, not real enterprise logs.
- Uses mock connectors, not production systems.
- Requires `OPENAI_API_KEY` for RAG embeddings, RAG search, AI analysis, and improvement proposal generation. Missing or failed OpenAI calls return explicit errors.
- Uses PM4Py for DFG, performance DFG, and variant discovery; invoice-specific governance overlays remain custom.
- Generates mock configs only; no external systems are changed.
