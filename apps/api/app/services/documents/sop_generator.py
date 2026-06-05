from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings

SOP_TITLES = [
    "SOP 001: Invoice Intake and Data Validation",
    "SOP 002: Purchase Order Verification",
    "SOP 003: Three-Way Match Execution",
    "SOP 004: Price Mismatch Exception Handling",
    "SOP 005: Missing PO Exception Handling",
    "SOP 006: Duplicate Invoice Control",
    "SOP 007: Vendor Risk and Compliance Review",
    "SOP 008: Approval Threshold Handling",
    "SOP 009: Payment Scheduling and Remittance",
    "SOP 010: Exception Ticket SLA and Escalation",
    "SOP 011: Manual Workaround Prohibition",
    "SOP 012: AI-Assisted Process Improvement Review",
]

SECTIONS = [
    "Purpose",
    "Scope",
    "Systems involved",
    "Roles involved",
    "Trigger",
    "Step-by-step procedure",
    "Required data fields",
    "Control points",
    "Evidence required",
    "Exceptions",
    "Escalation path",
    "Audit log requirements",
    "KPIs",
    "Common failure modes",
]


def generate_sops(session: Session):
    _ = session
    documents = []
    for title in SOP_TITLES:
        content = build_sop(title)
        file_path = write_document_file("sop-repository", title, content)
        documents.append(file_payload(title, "SOP", file_path, content, {"sections": SECTIONS, "process_area": process_area(title), "version": "1.0"}))
    return documents


def build_sop(title: str) -> str:
    area = process_area(title)
    lines = [f"# {title}", ""]
    for section in SECTIONS:
        lines.append(f"## {section}")
        lines.append(section_text(section, area))
        lines.append("")
    return "\n".join(lines)


def process_area(title: str) -> str:
    return title.split(": ", 1)[1]


def write_document_file(repository_name: str, title: str, content: str) -> Path:
    directory = settings.root_dir / "docs" / repository_name
    directory.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    path = directory / f"{slug}.md"
    path.write_text(content, encoding="utf-8")
    return path


def file_payload(title: str, source_type: str, path: Path, content: str, metadata: dict) -> dict:
    return {
        "id": path.stem,
        "title": title,
        "source_type": source_type,
        "source_file_path": str(path),
        "source_repository": f"docs/{path.parent.name}",
        "metadata": metadata | {"source_file_path": str(path), "source_repository": f"docs/{path.parent.name}"},
        "content": content,
    }


def section_text(section: str, area: str) -> str:
    defaults = {
        "Purpose": f"Define the governed procedure for {area.lower()} in the invoice exception handling process.",
        "Scope": "Applies to synthetic Coupa, SAP, ServiceNow, Vendor Master Data, Payment System, and policy repository records in this local demo.",
        "Systems involved": "Coupa, SAP, ServiceNow, Vendor Master Data, and Payment System as applicable to the canonical BPM process.",
        "Roles involved": "AP Clerk, Procurement Specialist, Finance Manager, Finance Controller, Compliance Officer, and System.",
        "Trigger": f"The procedure starts when the process reaches {area.lower()} or an exception related to that area is detected.",
        "Step-by-step procedure": "Follow the canonical BPM sequence, record every status change, keep exception work inside governed systems, and retry the canonical control point after correction.",
        "Required data fields": "case_id, invoice_id, activity, timestamp, system, role, invoice_amount, currency, vendor_id, vendor_risk, po_number, exception_type, and status.",
        "Control points": "Three-way match, duplicate invoice check, vendor risk check, approval threshold, compliance review, and controller review where applicable.",
        "Evidence required": "System event timestamp, actor role, source system, exception ticket reference, control result, approval decision, and audit note.",
        "Exceptions": "Missing PO, price mismatch, quantity mismatch, missing goods receipt, duplicate invoice, high-risk vendor, approval delay, and reopened ticket.",
        "Escalation path": "AP Team Lead for queue delay, Procurement Specialist for PO or receipt correction, Finance Controller for duplicate or block review, Compliance Officer for high-risk vendors.",
        "Audit log requirements": "Log inputs, decision, approver, timestamp, source document, system state before and after, and any retry path.",
        "KPIs": "Cycle time hours, exception rate, hidden step rate, SLA breach estimate, first-pass match rate, duplicate block rate, and approval aging.",
        "Common failure modes": "Manual email review, Excel correction, reopened tickets, missing evidence, duplicate reprocessing, and unapproved payment block bypass attempts.",
    }
    return defaults[section]
