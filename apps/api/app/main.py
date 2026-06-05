from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import models, repositories
from app.db.session import Base, engine, get_session
from app.services.agents import mock_agent
from app.services.ai import analysis_service, improvement_service
from app.services.ai.openai_client import OpenAIConfigurationError, OpenAIRateLimitError, OpenAIServiceError
from app.services.bpm import invoice_bpm_generator
from app.services.data_generation import invoice_event_generator
from app.services.documents import policy_generator, sop_generator
from app.services.mining import process_miner
from app.services.rag import rag_service

app = FastAPI(title="Invoice Process Intelligence Lab API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(OpenAIServiceError)
def openai_error_handler(_request: Request, exc: OpenAIServiceError) -> JSONResponse:
    if isinstance(exc, OpenAIConfigurationError):
        status_code = 400
    elif isinstance(exc, OpenAIRateLimitError):
        status_code = 429
    else:
        status_code = 503
    return JSONResponse(status_code=status_code, content={"detail": str(exc)})


class GenerateEventsRequest(BaseModel):
    case_count: int = Field(default=2000, ge=1, le=10000)
    seed: int = 42


class MiningRequest(BaseModel):
    event_log_id: str
    ideal_process_id: str


class RagSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    filters: dict[str, Any] = Field(default_factory=dict)


class AnalyzeRequest(BaseModel):
    question: str
    mining_run_id: str | None = None


class ImprovementRequest(BaseModel):
    mining_run_id: str


class ApprovalRequest(BaseModel):
    approved_by: str | None = None
    rejected_by: str | None = None
    comment: str = ""


@app.on_event("startup")
def startup() -> None:
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db")
def health_db(session: Session = Depends(get_session)) -> dict[str, Any]:
    try:
        session.execute(text("SELECT 1"))
        vector_status = "not_applicable_sqlite"
        if not settings.database_url.startswith("sqlite"):
            result = session.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).first()
            vector_status = "enabled" if result else "missing"
        return {"status": "ok", "database": "reachable", "pgvector": vector_status}
    except Exception as exc:
        return {"status": "error", "database": "unreachable", "detail": str(exc)}


@app.post("/bpm/generate-invoice-process")
def generate_bpm(session: Session = Depends(get_session)) -> dict[str, Any]:
    process = invoice_bpm_generator.generate_and_store(session)
    return process_payload(process)


@app.get("/bpm/ideal-process/latest")
def latest_bpm(session: Session = Depends(get_session)) -> dict[str, Any]:
    process = repositories.latest_ideal_process(session)
    if process is None:
        raise HTTPException(status_code=404, detail="No ideal process generated")
    return process_payload(process)


@app.get("/bpm/ideal-processes")
def list_bpm(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [process_summary(process) for process in repositories.list_ideal_processes(session)]


@app.post("/data/generate-invoice-events")
def generate_data(request: GenerateEventsRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
    event_log = invoice_event_generator.generate_event_log(session, request.case_count, request.seed)
    return event_log_payload(session, event_log, include_preview=True)


@app.get("/data/event-logs")
def list_event_logs(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [event_log_payload(session, event_log) for event_log in repositories.list_event_logs(session)]


@app.post("/data/upload-event-log")
async def upload_event_log(file: UploadFile = File(...), session: Session = Depends(get_session)) -> dict[str, Any]:
    content = (await file.read()).decode("utf-8-sig")
    try:
        rows = invoice_event_generator.parse_csv_rows(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    path = settings.root_dir / "data" / "uploads" / (file.filename or "uploaded_event_log.csv")
    invoice_event_generator.write_csv(path, rows)
    event_log = repositories.create_event_log(session, file.filename or path.name, "uploaded", rows, str(path), invoice_event_generator.summarize_rows(rows))
    return event_log_payload(session, event_log, include_preview=True)


@app.get("/data/event-logs/{event_log_id}/download")
def download_event_log(event_log_id: str, session: Session = Depends(get_session)) -> FileResponse:
    event_log = session.get(models.UploadedEventLog, event_log_id)
    if event_log is None or not Path(event_log.csv_path).exists():
        raise HTTPException(status_code=404, detail="CSV file not found")
    return FileResponse(event_log.csv_path, filename=event_log.filename, media_type="text/csv")


@app.post("/mining/run")
def run_mining(request: MiningRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
    try:
        run = process_miner.run_process_mining(session, request.event_log_id, request.ideal_process_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return process_miner.mining_run_payload(session, run)


@app.get("/mining/runs")
def list_mining_runs(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    runs = session.scalars(select(models.MiningRun).order_by(models.MiningRun.created_at.desc())).all()
    return [process_miner.mining_run_payload(session, run) for run in runs]


@app.post("/documents/generate-sops")
def generate_sops(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return sop_generator.generate_sops(session)


@app.post("/documents/generate-policies")
def generate_policies(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return policy_generator.generate_policies(session)


@app.get("/documents")
def list_documents(source_type: str | None = Query(default=None)) -> list[dict[str, Any]]:
    return rag_service.list_source_files(source_type)


@app.get("/documents/{document_id}")
def get_document(document_id: str) -> dict[str, Any]:
    document = rag_service.read_source_file(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document file not found")
    return document


@app.post("/rag/reindex")
def rag_reindex(session: Session = Depends(get_session)) -> dict[str, Any]:
    return rag_service.reindex(session)


@app.post("/rag/search")
def rag_search(request: RagSearchRequest, session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return rag_service.search(session, request.query, request.top_k, request.filters)


@app.get("/rag/status")
def rag_status(session: Session = Depends(get_session)) -> dict[str, Any]:
    return rag_service.status(session)


@app.get("/rag/chunks")
def rag_chunks(
    source_file_path: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    include_embedding: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    return rag_service.list_chunks(session, source_file_path=source_file_path, source_type=source_type, include_embedding=include_embedding)


@app.post("/ai/analyze")
def ai_analyze(request: AnalyzeRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
    return analysis_service.analyze(session, request.question, request.mining_run_id)


@app.post("/improvements/generate")
def generate_improvements(request: ImprovementRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
    return improvement_service.generate_improvements(session, request.mining_run_id)


@app.get("/improvements/proposals")
def list_proposals(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    proposals = session.scalars(select(models.ImprovementProposal).order_by(models.ImprovementProposal.created_at.desc())).all()
    payload = []
    for proposal in proposals:
        actions = session.scalars(select(models.ImprovementAction).where(models.ImprovementAction.proposal_id == proposal.id)).all()
        payload.append(improvement_service.proposal_payload(proposal) | {"actions": [improvement_service.action_payload(action) for action in actions]})
    return payload


@app.get("/improvements/actions")
def list_actions(status: str | None = Query(default=None), session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return improvement_service.list_actions(session, status)


@app.post("/improvements/actions/{action_id}/approve")
def approve_action(action_id: str, request: ApprovalRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
    action = session.get(models.ImprovementAction, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")
    if action.approval_status != "pending":
        raise HTTPException(status_code=409, detail="Action is already approved or rejected")
    repositories.approve_action(session, action, request.approved_by or "Demo Approver", request.comment)
    return improvement_service.action_payload(action)


@app.post("/improvements/actions/{action_id}/reject")
def reject_action(action_id: str, request: ApprovalRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
    action = session.get(models.ImprovementAction, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")
    if action.approval_status != "pending":
        raise HTTPException(status_code=409, detail="Action is already approved or rejected")
    repositories.reject_action(session, action, request.rejected_by or "Demo Reviewer", request.comment)
    return improvement_service.action_payload(action)


@app.post("/agents/run-action/{action_id}")
def run_agent(action_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    try:
        return mock_agent.run_action(session, action_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/agents/runs")
def list_agent_runs(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    runs = session.scalars(select(models.AgentRun).order_by(models.AgentRun.created_at.desc())).all()
    return [mock_agent.run_payload(session, run.id) for run in runs]


@app.get("/agents/runs/{agent_run_id}")
def get_agent_run(agent_run_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    if session.get(models.AgentRun, agent_run_id) is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return mock_agent.run_payload(session, agent_run_id)


@app.get("/mock-system-configs")
def list_mock_configs(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    configs = session.scalars(select(models.MockSystemConfig).order_by(models.MockSystemConfig.created_at.desc())).all()
    return [
        {
            "id": config.id,
            "agent_run_id": config.agent_run_id,
            "action_id": config.action_id,
            "target_system": config.target_system,
            "configuration_type": config.configuration_type,
            "config_json": config.config_json,
            "validation_result": config.validation_result,
            "enabled": config.enabled,
            "requires_final_human_enablement": config.requires_final_human_enablement,
        }
        for config in configs
    ]


@app.post("/demo/reset")
def reset_demo(session: Session = Depends(get_session)) -> dict[str, str]:
    for table in [
        models.MockSystemConfig,
        models.AgentStep,
        models.AgentRun,
        models.ImprovementAction,
        models.ImprovementProposal,
        models.RagQuery,
        models.DocumentChunk,
        models.MinedEdge,
        models.MinedNode,
        models.MiningRun,
        models.ProcessEvent,
        models.UploadedEventLog,
        models.IdealProcessEdge,
        models.IdealProcessNode,
        models.IdealProcess,
    ]:
        session.execute(delete(table))
    session.commit()
    return {"status": "reset"}


def process_summary(process: models.IdealProcess) -> dict[str, Any]:
    return {"id": process.id, "name": process.name, "version": process.version, "created_at": process.created_at.isoformat()}


def process_payload(process: models.IdealProcess) -> dict[str, Any]:
    return {
        **process_summary(process),
        "canonical_json": process.canonical_json,
        "bpmn_xml": process.bpmn_xml,
        "nodes": [
            {
                "id": node.node_key,
                "label": node.label,
                "node_type": node.node_type,
                "role": node.role,
                "system": node.system,
                "is_control_point": node.is_control_point,
                "metadata": node.node_metadata,
            }
            for node in process.nodes
        ],
        "edges": [
            {"id": edge.id, "source": edge.source_node_key, "target": edge.target_node_key, "label": edge.label, "metadata": edge.edge_metadata}
            for edge in process.edges
        ],
    }


def event_log_payload(session: Session, event_log: models.UploadedEventLog, include_preview: bool = False) -> dict[str, Any]:
    payload = {
        "id": event_log.id,
        "filename": event_log.filename,
        "source_type": event_log.source_type,
        "row_count": event_log.row_count,
        "case_count": event_log.case_count,
        "hidden_step_count": event_log.hidden_step_count,
        "date_start": event_log.date_start.isoformat() if event_log.date_start else None,
        "date_end": event_log.date_end.isoformat() if event_log.date_end else None,
        "csv_path": event_log.csv_path,
        "metadata": event_log.log_metadata,
        "download_url": f"/data/event-logs/{event_log.id}/download",
    }
    if include_preview:
        events = session.scalars(select(models.ProcessEvent).where(models.ProcessEvent.event_log_id == event_log.id).order_by(models.ProcessEvent.timestamp).limit(100)).all()
        payload["preview"] = [event_payload(event) for event in events]
    return payload


def event_payload(event: models.ProcessEvent) -> dict[str, Any]:
    return {
        "case_id": event.case_id,
        "invoice_id": event.invoice_id,
        "activity": event.activity,
        "timestamp": event.timestamp.isoformat(),
        "system": event.system,
        "role": event.role,
        "user_id": event.user_id,
        "invoice_amount": event.invoice_amount,
        "currency": event.currency,
        "country": event.country,
        "vendor_id": event.vendor_id,
        "vendor_risk": event.vendor_risk,
        "po_number": event.po_number,
        "exception_type": event.exception_type,
        "status": event.status,
        "is_hidden_step": event.is_hidden_step,
        "hidden_issue_type": event.hidden_issue_type,
    }
