# Invoice Process Intelligence Lab

Build small vertical slices. Keep mock enterprise systems only. Never call real Coupa, SAP, ServiceNow, payment, or banking APIs.

## Stack
- Frontend: React, Vite, TypeScript, Tailwind CSS, React Flow.
- Backend: FastAPI, SQLAlchemy, Alembic, PostgreSQL 16, pgvector.
- AI: OpenAI through environment variables, with deterministic local fallbacks when no key exists.
- Process mining: PM4Py-backed DFG, performance DFG, and variant discovery.

## Commands
- Backend: `cd apps/api; uvicorn app.main:app --reload`
- Backend tests: `cd apps/api; pytest`
- Frontend: `cd apps/web; npm run dev`
- Frontend build: `cd apps/web; npm run build`
- Infra: `docker compose up -d`

## Rules
- Synthetic data only.
- Show visible trace, sources, assumptions, and missing information. Never expose hidden chain-of-thought.
- Improvement actions require human approval before agents run.
- Agent output is mock configuration JSON with audit trail and validation.
- Payment or finance configs must keep `enabled=false` and `requires_final_human_enablement=true`.
