from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

os.environ["DATABASE_URL"] = "sqlite:///./test_invoice_lab.db"
os.environ["APP_ENV"] = "test"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy import select, text

from app.db import models
from app.db.session import Base, SessionLocal, engine
from app.main import app
from app.services.data_generation.invoice_event_generator import REQUIRED_COLUMNS, parse_csv_rows

client = TestClient(app)


@pytest.fixture(autouse=True)
def stub_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.ai.openai_client import openai_client

    def embed(_text: str) -> list[float]:
        vector = [0.0] * 1536
        vector[0] = 1.0
        return vector

    def structured_json(prompt: str) -> dict:
        if "improvement proposals" in prompt:
            return improvement_payload()
        return analysis_payload()

    monkeypatch.setattr(openai_client, "embed", embed)
    monkeypatch.setattr(openai_client, "structured_json", structured_json)


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS documents"))
    Base.metadata.create_all(bind=engine)


def test_health() -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/health/db").json()["status"] == "ok"


def test_bpm_generation_contains_controls_and_no_hidden_steps() -> None:
    response = client.post("/bpm/generate-invoice-process")
    assert response.status_code == 200
    data = response.json()
    labels = {node["label"] for node in data["nodes"]}
    assert "Run three-way match in SAP" in labels
    assert "Manual Email Review" not in labels
    assert any(node["is_control_point"] for node in data["nodes"])
    assert client.get("/bpm/ideal-process/latest").status_code == 200


def test_seeded_event_generation_is_deterministic_and_hidden() -> None:
    first = client.post("/data/generate-invoice-events", json={"case_count": 25, "seed": 7}).json()
    second = client.post("/data/generate-invoice-events", json={"case_count": 25, "seed": 7}).json()
    first_rows = [(row["case_id"], row["activity"], row["timestamp"]) for row in first["preview"]]
    second_rows = [(row["case_id"], row["activity"], row["timestamp"]) for row in second["preview"]]
    assert first_rows == second_rows
    assert set(REQUIRED_COLUMNS).issubset(first["preview"][0].keys())
    assert first["hidden_step_count"] > 0
    assert first["metadata"]["total_cases"] == 25
    assert len({row["system"] for row in first["preview"]}) > 1
    rows = parse_csv_rows(Path(first["csv_path"]).read_text(encoding="utf-8"))
    by_case: dict[str, list] = {}
    for row in rows:
        by_case.setdefault(row["case_id"], []).append(row["timestamp"])
    assert all(values == sorted(values) for values in by_case.values())


def test_upload_validation_rejects_invalid_csv() -> None:
    response = client.post("/data/upload-event-log", files={"file": ("bad.csv", "case_id,activity\n1,A\n", "text/csv")})
    assert response.status_code == 400
    assert "Missing required columns" in response.text


def test_mining_marks_hidden_and_bottlenecks() -> None:
    process = client.post("/bpm/generate-invoice-process").json()
    log = client.post("/data/generate-invoice-events", json={"case_count": 60, "seed": 42}).json()
    run = client.post("/mining/run", json={"ideal_process_id": process["id"], "event_log_id": log["id"]}).json()
    assert run["metrics"]["case_count"] == 60
    assert run["metrics"]["mining_engine"] == "pm4py"
    assert any(node["severity"] == "hidden" for node in run["nodes"])
    assert any(edge["severity"] in {"hidden", "bottleneck"} for edge in run["edges"])
    with SessionLocal() as session:
        stored = session.scalars(select(models.MiningRun)).first()
        assert stored is not None
        assert stored.metrics["case_count"] == 60


def test_documents_and_rag_indexing() -> None:
    client.post("/bpm/generate-invoice-process")
    client.post("/documents/generate-sops")
    client.post("/documents/generate-policies")
    sops = client.get("/documents?source_type=SOP").json()
    policies = client.get("/documents?source_type=POLICY").json()
    assert len(sops) == 12
    assert len(policies) == 12
    sop_detail = client.get(f"/documents/{sops[0]['id']}").json()
    assert "## Purpose" in sop_detail["content"]
    assert Path(sop_detail["source_file_path"]).exists()
    assert "docs/sop-repository" in sop_detail["source_repository"]
    policy_detail = client.get(f"/documents/{policies[0]['id']}").json()
    assert Path(policy_detail["source_file_path"]).exists()
    assert "docs/policy-repository" in policy_detail["source_repository"]
    policy_texts = [client.get(f"/documents/{policy['id']}").json()["content"] for policy in policies]
    assert len(set(policy_texts)) == 12
    assert any("10,000 EUR" in text for text in policy_texts)
    assert any("enabled=false" in text for text in policy_texts)
    assert any("Payment blocks must not be bypassed" in text for text in policy_texts)
    assert any("AI recommendations must be grounded" in text for text in policy_texts)
    status = client.post("/rag/reindex").json()
    assert status["total_chunks"] > 0
    results = client.post("/rag/search", json={"query": "price mismatch below 1000 EUR", "top_k": 3, "filters": {}}).json()
    assert results
    chunks = client.get(f"/rag/chunks?source_file_path={sop_detail['source_file_path']}").json()
    assert chunks
    assert chunks[0]["embedding_dimensions"] == 1536
    assert chunks[0]["embedding_preview"]
    with engine.connect() as connection:
        assert "documents" not in inspect(connection).get_table_names()
    assert not any("CASE-" in result["chunk_text"] for result in results)


def test_ai_refuses_without_context() -> None:
    response = client.post("/ai/analyze", json={"question": "What can we automate safely?", "mining_run_id": None}).json()
    assert "insufficient" in response["answer"].lower()
    assert "visible_trace" in response


def test_openai_embedding_retries_retryable_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.ai.openai_client import OpenAIClient

    class RateLimitError(Exception):
        status_code = 429
        code = "rate_limit_exceeded"

    calls = []
    api_client = OpenAIClient()
    api_client.embedding_dimensions = 3

    class Embeddings:
        def create(self, **_request: object) -> object:
            calls.append(1)
            if len(calls) < 3:
                raise RateLimitError()
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])])

    monkeypatch.setattr(api_client, "_client", lambda: SimpleNamespace(embeddings=Embeddings()))
    monkeypatch.setattr("app.services.ai.openai_client.time.sleep", lambda _seconds: None)

    assert api_client.embed("hello") == [0.1, 0.2, 0.3]
    assert len(calls) == 3


def test_openai_embedding_rate_limit_returns_429(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.ai.openai_client import OpenAIRateLimitError, openai_client

    def embed(_text: str) -> list[float]:
        raise OpenAIRateLimitError("OpenAI embedding request hit the OpenAI rate limit. Wait a moment and retry, or reduce request volume.")

    monkeypatch.setattr(openai_client, "embed", embed)

    response = client.post("/rag/search", json={"query": "invoice delay", "top_k": 3, "filters": {}})

    assert response.status_code == 429
    assert "rate limit" in response.json()["detail"].lower()


def test_improvement_approval_and_agent_flow() -> None:
    process = client.post("/bpm/generate-invoice-process").json()
    log = client.post("/data/generate-invoice-events", json={"case_count": 80, "seed": 42}).json()
    run = client.post("/mining/run", json={"ideal_process_id": process["id"], "event_log_id": log["id"]}).json()
    client.post("/documents/generate-sops")
    client.post("/documents/generate-policies")
    client.post("/rag/reindex")
    analysis = client.post("/ai/analyze", json={"question": "Why are invoices delayed?", "mining_run_id": run["id"]}).json()
    assert analysis["retrieved_sources"]
    improvements = client.post("/improvements/generate", json={"mining_run_id": run["id"]}).json()
    assert improvements["proposals"]
    action = improvements["proposals"][0]["actions"][0]
    assert action["approval_status"] == "pending"
    blocked = client.post(f"/agents/run-action/{action['id']}")
    assert blocked.status_code == 403
    approved = client.post(f"/improvements/actions/{action['id']}/approve", json={"approved_by": "Finance Controller", "comment": "ok"}).json()
    assert approved["approval_status"] == "approved"
    agent = client.post(f"/agents/run-action/{action['id']}").json()
    assert agent["status"] == "completed"
    assert len(agent["steps"]) == 7
    assert agent["config_json"]["enabled"] is False
    assert agent["config_json"]["requires_final_human_enablement"] is True
    assert agent["validation_result"]["valid"] is True


def test_agent_runs_invoice_management_system_actions() -> None:
    process = client.post("/bpm/generate-invoice-process").json()
    log = client.post("/data/generate-invoice-events", json={"case_count": 20, "seed": 42}).json()
    run = client.post("/mining/run", json={"ideal_process_id": process["id"], "event_log_id": log["id"]}).json()
    with SessionLocal() as session:
        proposal = models.ImprovementProposal(
            mining_run_id=run["id"],
            title="PO exception guidance",
            problem_statement="PO exception reviews need guidance.",
            evidence=[],
            expected_impact="Improve review consistency.",
            risk_level="low",
            required_approvers=["AP Team Lead"],
            monitoring_kpis=[],
        )
        session.add(proposal)
        session.flush()
        action = models.ImprovementAction(
            proposal_id=proposal.id,
            title="Create Guidance for PO Exception Reviews",
            target_system="Invoice Management System",
            action_type="guidance_rule",
            description="Create mock reviewer guidance.",
            preconditions=[],
            approval_required=True,
            required_approvers=["AP Team Lead"],
            expected_config_json={},
            approval_status="approved",
            approved_by="AP Team Lead",
        )
        session.add(action)
        session.commit()
        action_id = action.id

    agent = client.post(f"/agents/run-action/{action_id}").json()
    assert agent["status"] == "completed"
    assert agent["config_json"]["system"] == "Invoice Management System"
    assert agent["config_json"]["configuration_type"] == "invoice_guidance_rule"


def analysis_payload() -> dict:
    return {
        "answer": "Invoices are delayed by manual exception review and hidden workaround paths.",
        "evidence_used": ["AP review bottleneck", "Hidden workaround path"],
        "retrieved_sources": [{"title": "Policy", "source_type": "POLICY"}],
        "visible_trace": ["Retrieved policy chunks", "Reviewed mined metrics"],
        "assumptions": ["Synthetic test data only"],
        "missing_information": [],
        "confidence": "medium",
    }


def improvement_payload() -> dict:
    return {
        "summary": "Generated OpenAI-backed test proposals.",
        "proposals": [
            {
                "title": "Auto-resolve low-risk price mismatch exceptions below 1,000 EUR",
                "problem_statement": "Price mismatch review creates manual delay for low-risk invoices.",
                "evidence": ["Policy threshold: below 1,000 EUR", "Duplicate check required"],
                "expected_impact": "Reduce AP review volume while preserving controls.",
                "risk_level": "medium",
                "required_approvers": ["Finance Controller", "Compliance Officer"],
                "actions": [
                    {
                        "title": "Create low-risk price mismatch auto-resolution rule",
                        "target_system": "Coupa",
                        "action_type": "configuration_change",
                        "description": "Generate a disabled mock invoice exception rule for low-risk vendors, duplicate-check-passed invoices, and price mismatches below the policy threshold.",
                        "preconditions": ["vendor risk is low", "duplicate check passed", "goods receipt exists", "invoice amount below 1000 EUR"],
                        "expected_config_json": {},
                    }
                ],
                "monitoring_kpis": ["price mismatch cycle time", "exception reopen rate"],
            }
        ],
        "blocked_recommendations": [
            {"idea": "Fully automate payment scheduling", "reason_blocked": "Requires final human enablement and payment controls."}
        ],
    }
