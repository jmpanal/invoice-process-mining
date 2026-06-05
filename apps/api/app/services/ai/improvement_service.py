from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.services.ai.openai_client import OpenAIResponseError, openai_client
from app.services.rag import rag_service

ALLOWED_TARGET_SYSTEMS = [
    "Coupa",
    "SAP",
    "ServiceNow",
    "Vendor Master Data",
    "Payment System",
    "Policy Repository",
    "Invoice Management System",
]


def generate_improvements(session: Session, mining_run_id: str) -> dict:
    run = session.get(models.MiningRun, mining_run_id)
    if run is None:
        raise ValueError("Mining run not found")
    policy_context = rag_service.search(session, "approval threshold policy duplicate invoice agent execution", top_k=5, filters={"source_type": "POLICY"})
    if not policy_context:
        return {
            "summary": "Policy context is missing. Automation proposals are blocked until policies are generated and indexed.",
            "proposals": [],
            "blocked_recommendations": [{"idea": "Generate automation proposals", "reason_blocked": "Missing policy context"}],
        }

    payload = normalize_improvement_payload(openai_client.structured_json(build_improvement_prompt(run, policy_context)))
    stored = []
    for proposal_data in payload["proposals"]:
        proposal = models.ImprovementProposal(
            mining_run_id=run.id,
            title=proposal_data["title"],
            problem_statement=proposal_data["problem_statement"],
            evidence=proposal_data["evidence"],
            expected_impact=proposal_data["expected_impact"],
            risk_level=proposal_data["risk_level"],
            required_approvers=proposal_data["required_approvers"],
            monitoring_kpis=proposal_data["monitoring_kpis"],
            proposal_metadata={"retrieved_policy_chunks": [chunk["chunk_id"] for chunk in policy_context]},
        )
        session.add(proposal)
        session.flush()
        actions = []
        for action_data in proposal_data["actions"]:
            action = models.ImprovementAction(
                proposal_id=proposal.id,
                title=action_data["title"],
                target_system=action_data["target_system"],
                action_type=action_data["action_type"],
                description=action_data["description"],
                preconditions=action_data["preconditions"],
                approval_required=True,
                required_approvers=proposal_data["required_approvers"],
                expected_config_json=action_data["expected_config_json"],
                approval_status="pending",
            )
            session.add(action)
            session.flush()
            actions.append(action_payload(action))
        stored.append(proposal_payload(proposal) | {"actions": actions})
    session.commit()
    return {"summary": payload["summary"], "proposals": stored, "blocked_recommendations": payload["blocked_recommendations"]}


def build_improvement_prompt(run: models.MiningRun, policy_context: list[dict]) -> str:
    return (
        "Generate bounded invoice process improvement proposals from mined evidence and retrieved policy only.\n"
        "Return JSON with keys: summary, proposals, blocked_recommendations.\n"
        "Each proposal must include title, problem_statement, evidence, expected_impact, risk_level, required_approvers, actions, monitoring_kpis.\n"
        "Each action must include title, target_system, action_type, description, preconditions, expected_config_json.\n"
        f"Allowed target_system values exactly: {', '.join(ALLOWED_TARGET_SYSTEMS)}.\n"
        "Rules: every action requires human approval, generated configs must be disabled by default, no real external systems are changed, "
        "and full payment scheduling automation must stay blocked unless duplicate checks, vendor risk, approval thresholds, and final human enablement are preserved.\n\n"
        f"Mined metrics:\n{json.dumps(run.metrics, default=str)}\n\n"
        f"Top variants:\n{json.dumps(run.top_variants, default=str)}\n\n"
        f"Top hidden issues:\n{json.dumps(run.top_hidden_issues, default=str)}\n\n"
        f"Top bottlenecks:\n{json.dumps(run.top_bottlenecks, default=str)}\n\n"
        f"Retrieved policy context:\n{json.dumps(policy_context, default=str)}"
    )


def normalize_improvement_payload(payload: dict) -> dict:
    proposals = payload.get("proposals")
    if not isinstance(proposals, list) or not proposals:
        raise OpenAIResponseError("OpenAI improvement response must include at least one proposal.")
    normalized_proposals = []
    for proposal in proposals:
        if not isinstance(proposal, dict):
            raise OpenAIResponseError("OpenAI improvement proposal must be an object.")
        actions = proposal.get("actions")
        if not isinstance(actions, list) or not actions:
            raise OpenAIResponseError("OpenAI improvement proposal must include at least one action.")
        normalized_actions = []
        for action in actions:
            if not isinstance(action, dict):
                raise OpenAIResponseError("OpenAI improvement action must be an object.")
            normalized_actions.append(
                {
                    "title": string_value(action.get("title"), "Untitled action"),
                    "target_system": normalize_target_system(action.get("target_system")),
                    "action_type": string_value(action.get("action_type"), "policy_update"),
                    "description": string_value(action.get("description"), ""),
                    "preconditions": list_value(action.get("preconditions")),
                    "expected_config_json": action.get("expected_config_json") if isinstance(action.get("expected_config_json"), dict) else {},
                }
            )
        risk_level = string_value(proposal.get("risk_level"), "medium").lower()
        normalized_proposals.append(
            {
                "title": string_value(proposal.get("title"), "Untitled proposal"),
                "problem_statement": string_value(proposal.get("problem_statement"), ""),
                "evidence": list_value(proposal.get("evidence")),
                "expected_impact": string_value(proposal.get("expected_impact"), ""),
                "risk_level": risk_level if risk_level in {"low", "medium", "high"} else "medium",
                "required_approvers": list_value(proposal.get("required_approvers")),
                "actions": normalized_actions,
                "monitoring_kpis": list_value(proposal.get("monitoring_kpis")),
            }
        )
    return {
        "summary": string_value(payload.get("summary"), "Generated OpenAI-backed improvement proposals."),
        "proposals": normalized_proposals,
        "blocked_recommendations": list_value(payload.get("blocked_recommendations")),
    }


def string_value(value: object, default: str) -> str:
    if value is None or value == "":
        return default
    return str(value)


def normalize_target_system(value: object) -> str:
    raw = string_value(value, "Policy Repository").strip()
    for system in ALLOWED_TARGET_SYSTEMS:
        if raw.lower() == system.lower():
            return system
    aliases = {
        "invoice management": "Invoice Management System",
        "invoice workflow": "Invoice Management System",
        "invoice processing system": "Invoice Management System",
        "ticketing": "ServiceNow",
        "servicenow ticketing": "ServiceNow",
        "procurement": "Coupa",
        "procure to pay": "Coupa",
        "vendor master": "Vendor Master Data",
        "payment": "Payment System",
        "policy": "Policy Repository",
    }
    return aliases.get(raw.lower(), "Policy Repository")


def list_value(value: object) -> list:
    if isinstance(value, list):
        return value
    if value is None or value == "":
        return []
    return [value]


def list_actions(session: Session, status: str | None = None) -> list[dict]:
    stmt = select(models.ImprovementAction).order_by(models.ImprovementAction.created_at.desc())
    if status:
        stmt = stmt.where(models.ImprovementAction.approval_status == status)
    return [action_payload(action) for action in session.scalars(stmt).all()]


def proposal_payload(proposal: models.ImprovementProposal) -> dict:
    return {
        "id": proposal.id,
        "title": proposal.title,
        "problem_statement": proposal.problem_statement,
        "evidence": proposal.evidence,
        "expected_impact": proposal.expected_impact,
        "risk_level": proposal.risk_level,
        "required_approvers": proposal.required_approvers,
        "monitoring_kpis": proposal.monitoring_kpis,
    }


def action_payload(action: models.ImprovementAction) -> dict:
    return {
        "id": action.id,
        "proposal_id": action.proposal_id,
        "title": action.title,
        "target_system": action.target_system,
        "action_type": action.action_type,
        "description": action.description,
        "preconditions": action.preconditions,
        "approval_required": action.approval_required,
        "required_approvers": action.required_approvers,
        "approval_status": action.approval_status,
        "approved_by": action.approved_by,
        "approval_comment": action.approval_comment,
    }
