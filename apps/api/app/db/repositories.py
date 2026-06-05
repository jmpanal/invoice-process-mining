from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models


def create_ideal_process(session: Session, payload: dict[str, Any]) -> models.IdealProcess:
    process = models.IdealProcess(
        name=payload["name"],
        version=payload.get("version", "1.0"),
        canonical_json=payload,
        bpmn_xml=payload.get("bpmn_xml", ""),
    )
    session.add(process)
    session.flush()
    for node in payload["nodes"]:
        session.add(
            models.IdealProcessNode(
                process_id=process.id,
                node_key=node["id"],
                label=node["label"],
                node_type=node["node_type"],
                role=node["role"],
                system=node["system"],
                is_control_point=node.get("is_control_point", False),
                node_metadata=node,
            )
        )
    for edge in payload["edges"]:
        session.add(
            models.IdealProcessEdge(
                process_id=process.id,
                source_node_key=edge["source"],
                target_node_key=edge["target"],
                label=edge.get("label", ""),
                edge_metadata=edge,
            )
        )
    session.commit()
    session.refresh(process)
    return process


def latest_ideal_process(session: Session) -> models.IdealProcess | None:
    return session.scalars(select(models.IdealProcess).order_by(models.IdealProcess.created_at.desc())).first()


def list_ideal_processes(session: Session) -> list[models.IdealProcess]:
    return list(session.scalars(select(models.IdealProcess).order_by(models.IdealProcess.created_at.desc())).all())


def create_event_log(
    session: Session,
    filename: str,
    source_type: str,
    rows: list[dict[str, Any]],
    csv_path: str,
    metadata: dict[str, Any] | None = None,
) -> models.UploadedEventLog:
    timestamps = [row["timestamp"] for row in rows]
    case_ids = {row["case_id"] for row in rows}
    hidden_count = sum(1 for row in rows if row.get("is_hidden_step"))
    event_log = models.UploadedEventLog(
        filename=filename,
        source_type=source_type,
        row_count=len(rows),
        case_count=len(case_ids),
        hidden_step_count=hidden_count,
        date_start=min(timestamps) if timestamps else None,
        date_end=max(timestamps) if timestamps else None,
        csv_path=csv_path,
        log_metadata=metadata or {},
    )
    session.add(event_log)
    session.flush()
    for row in rows:
        session.add(models.ProcessEvent(event_log_id=event_log.id, **row))
    session.commit()
    session.refresh(event_log)
    return event_log


def list_event_logs(session: Session) -> list[models.UploadedEventLog]:
    return list(session.scalars(select(models.UploadedEventLog).order_by(models.UploadedEventLog.created_at.desc())).all())


def create_agent_step(
    session: Session,
    agent_run_id: str,
    order: int,
    name: str,
    status: str,
    input_json: dict[str, Any],
    output_json: dict[str, Any],
    explanation: str,
) -> models.AgentStep:
    step = models.AgentStep(
        agent_run_id=agent_run_id,
        step_order=order,
        name=name,
        status=status,
        input_json=input_json,
        output_json=output_json,
        explanation=explanation,
    )
    session.add(step)
    session.flush()
    return step


def approve_action(session: Session, action: models.ImprovementAction, approved_by: str, comment: str) -> models.ImprovementAction:
    action.approval_status = "approved"
    action.approved_by = approved_by
    action.approved_at = datetime.utcnow()
    action.approval_comment = comment
    session.commit()
    session.refresh(action)
    return action


def reject_action(session: Session, action: models.ImprovementAction, rejected_by: str, comment: str) -> models.ImprovementAction:
    action.approval_status = "rejected"
    action.rejected_by = rejected_by
    action.rejected_at = datetime.utcnow()
    action.approval_comment = comment
    session.commit()
    session.refresh(action)
    return action
