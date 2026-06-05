from __future__ import annotations

from sqlalchemy.orm import Session

from app.db import repositories


def canonical_invoice_process() -> dict:
    nodes = [
        node("start", "Invoice received in Coupa", "start", "System", "Coupa"),
        node("validate", "Validate invoice data", "task", "AP Clerk", "Coupa"),
        node("check_po", "Check purchase order exists in SAP", "task", "System", "SAP", True),
        node("three_way", "Run three-way match in SAP", "task", "System", "SAP", True),
        node("po_match_ok", "PO and match OK?", "gateway", "System", "SAP"),
        node("resolve_exception", "Review and correct exception", "task", "AP Clerk", "ServiceNow"),
        node("duplicate_check", "Run duplicate invoice check", "task", "System", "SAP", True),
        node("duplicate_found", "Duplicate found?", "gateway", "System", "SAP", True),
        node("risk_threshold", "Check vendor risk and amount threshold", "task", "System", "SAP", True),
        node("manual_approval_required", "Manual approval required?", "gateway", "System", "SAP", True),
        node("approval", "Manager or compliance approval", "task", "Finance Manager", "SAP", True),
        node("schedule_payment", "Schedule payment in SAP", "task", "System", "Payment System"),
        node("remittance", "Send remittance notice", "task", "System", "Payment System"),
        node("end_paid", "Invoice paid", "end", "System", "Payment System"),
        node("end_rejected", "Invoice rejected", "end", "System", "SAP"),
    ]
    edges = [
        edge("start", "validate"),
        edge("validate", "check_po"),
        edge("check_po", "three_way"),
        edge("three_way", "po_match_ok"),
        edge("po_match_ok", "resolve_exception", "no"),
        edge("resolve_exception", "duplicate_check", "resolved"),
        edge("po_match_ok", "duplicate_check", "yes"),
        edge("duplicate_check", "duplicate_found"),
        edge("duplicate_found", "end_rejected", "yes"),
        edge("duplicate_found", "risk_threshold", "no"),
        edge("risk_threshold", "manual_approval_required"),
        edge("manual_approval_required", "approval", "yes"),
        edge("approval", "schedule_payment"),
        edge("manual_approval_required", "schedule_payment", "no"),
        edge("schedule_payment", "remittance"),
        edge("remittance", "end_paid"),
    ]
    return {
        "name": "Canonical Invoice Exception Handling Process",
        "version": "1.0",
        "nodes": nodes,
        "edges": edges,
        "bpmn_xml": "<!-- TODO: replace with full BPMN 2.0 XML if bpmn-js rendering is required. Canonical JSON is authoritative. -->",
    }


def node(
    node_id: str,
    label: str,
    node_type: str,
    role: str,
    system: str,
    is_control_point: bool = False,
) -> dict:
    return {
        "id": node_id,
        "label": label,
        "node_type": node_type,
        "role": role,
        "system": system,
        "is_control_point": is_control_point,
    }


def edge(source: str, target: str, label: str = "") -> dict:
    return {"id": f"{source}->{target}", "source": source, "target": target, "label": label}


def generate_and_store(session: Session):
    return repositories.create_ideal_process(session, canonical_invoice_process())
