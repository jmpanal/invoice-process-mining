from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings

SECTIONS = [
    "Policy statement",
    "Why the policy exists",
    "Allowed actions",
    "Blocked actions",
    "Thresholds",
    "Approval requirements",
    "System enforcement point",
    "Audit requirements",
    "Example compliant case",
    "Example non-compliant case",
]

THRESHOLDS = [
    "Finance manager approval required above 10,000 EUR.",
    "Low-risk price mismatch auto-resolution can be proposed only below 1,000 EUR.",
    "Price mismatch tolerance for demo is 1.5 percent.",
    "Duplicate invoice check must pass before any payment-related automation.",
    "High-risk vendors always require compliance review.",
    "Payment-related agent configs must be generated with enabled=false and requires_final_human_enablement=true.",
]

POLICIES = [
    {
        "title": "Policy 001: Invoice Automation Eligibility",
        "area": "invoice automation eligibility",
        "statement": "Invoice automation is permitted only for low-risk, fully evidenced cases that have passed the required process controls.",
        "why": "The invoice process includes financial controls, vendor-risk controls, and duplicate-payment controls. Automation must reduce manual load without bypassing those controls.",
        "allowed": [
            "Recommend automation candidates from mined evidence and retrieved SOP or policy context.",
            "Generate disabled mock workflow rules for low-risk cases after human approval.",
            "Route invoices to payment scheduling only after duplicate check, vendor risk check, and approval threshold checks are satisfied.",
        ],
        "blocked": [
            "Automating invoices with missing PO, missing goods receipt, high-risk vendor status, failed duplicate check, or unresolved compliance review.",
            "Using hidden email or spreadsheet activity as an approved automation path.",
            "Executing any generated configuration without human approval.",
        ],
        "thresholds": [
            THRESHOLDS[3],
            THRESHOLDS[4],
            THRESHOLDS[5],
        ],
        "approvals": "Process Owner approval is required for workflow changes. Finance Controller approval is required when the action affects payment eligibility.",
        "enforcement": "Improve Process proposal validation and agent execution precondition checks.",
        "compliant": "A low-risk invoice with PO, goods receipt, passed duplicate check, and amount below approval threshold is proposed for auto-routing, then approved before mock config generation.",
        "non_compliant": "A missing goods receipt invoice is auto-routed to payment scheduling because the AI inferred that receipt would arrive later.",
    },
    {
        "title": "Policy 002: Low-Risk Price Mismatch Auto-Resolution",
        "area": "low-risk price mismatch auto-resolution",
        "statement": "Low-risk price mismatch auto-resolution may be proposed only for tightly bounded cases below the defined amount and tolerance thresholds.",
        "why": "Price mismatch loops are a major AP delay source, but incorrect auto-resolution can create overpayment and audit risk.",
        "allowed": [
            "Propose auto-resolution when vendor risk is low, invoice amount is below 1,000 EUR, mismatch is at or below 1.5 percent, duplicate check passed, and goods receipt exists.",
            "Generate a disabled Coupa mock exception rule with audit notes and fallback to AP manual review.",
            "Monitor reopened ticket rate and exception reversal rate after approval.",
        ],
        "blocked": [
            "Auto-resolving high-risk vendor price mismatches.",
            "Auto-resolving any mismatch above 1,000 EUR or above 1.5 percent.",
            "Skipping duplicate invoice control or goods receipt evidence.",
        ],
        "thresholds": [
            THRESHOLDS[1],
            THRESHOLDS[2],
            THRESHOLDS[3],
            THRESHOLDS[4],
            THRESHOLDS[5],
        ],
        "approvals": "Finance Controller and Compliance Officer approval are required before agent execution.",
        "enforcement": "Coupa mock configuration schema, improvement action approval status, and RAG policy retrieval.",
        "compliant": "A 740 EUR invoice from a low-risk vendor has a 1.1 percent price mismatch, passed duplicate check, and goods receipt exists. A disabled mock auto-resolution rule is generated after approval.",
        "non_compliant": "A 1,350 EUR invoice with a 1.2 percent price mismatch is auto-resolved because the mismatch percentage is low.",
    },
    {
        "title": "Policy 003: Duplicate Invoice Prevention",
        "area": "duplicate invoice prevention",
        "statement": "Duplicate invoice check must pass before any payment-related action, auto-resolution, or payment scheduling recommendation.",
        "why": "Duplicate reprocessing is a high-impact control failure. It can create duplicate payments and weakens audit evidence.",
        "allowed": [
            "Block invoices where duplicate check fails.",
            "Route blocked invoices to Finance Controller review.",
            "Release blocked invoices only after documented controller decision.",
        ],
        "blocked": [
            "Payment scheduling before duplicate check result exists.",
            "Payment block bypass attempts.",
            "AI recommendations that treat duplicate status as unknown but proceed anyway.",
        ],
        "thresholds": [
            THRESHOLDS[3],
            THRESHOLDS[5],
        ],
        "approvals": "Finance Controller approval is required to release a blocked invoice. Process Owner approval is required for duplicate-check rule changes.",
        "enforcement": "SAP mock payment block, mined hidden-path detection, and agent config validator.",
        "compliant": "Duplicate check fails, invoice is blocked, Finance Controller reviews evidence, and only then releases or rejects the invoice.",
        "non_compliant": "An AP Clerk attempts Payment Block Bypass Attempt after duplicate check fails.",
    },
    {
        "title": "Policy 004: Vendor Risk Controls",
        "area": "vendor risk controls",
        "statement": "High-risk vendors require compliance review before approval, auto-resolution, or payment-related configuration.",
        "why": "Vendor risk controls prevent automation from weakening sanctions, compliance, fraud, or onboarding checks.",
        "allowed": [
            "Retrieve vendor risk status from Vendor Master Data.",
            "Route high-risk vendor invoices to Compliance Officer review.",
            "Use low-risk vendor status as one precondition for bounded automation.",
        ],
        "blocked": [
            "Auto-approving high-risk vendor invoices.",
            "Treating missing vendor risk as low risk.",
            "Generating payment-related configs when vendor risk evidence is absent.",
        ],
        "thresholds": [
            THRESHOLDS[4],
            THRESHOLDS[5],
        ],
        "approvals": "Compliance Officer approval is required for high-risk vendor release and vendor-risk rule changes.",
        "enforcement": "Vendor Master Data mock connector, policy retrieval checks, and improvement proposal preconditions.",
        "compliant": "A high-risk vendor invoice is routed to compliance review and approved before threshold and payment checks continue.",
        "non_compliant": "An invoice with missing vendor risk is assumed low risk because it has no prior exceptions.",
    },
    {
        "title": "Policy 005: Finance Approval Thresholds",
        "area": "finance approval thresholds",
        "statement": "Invoices above 10,000 EUR require Finance Manager approval before payment scheduling.",
        "why": "Large invoices carry higher financial exposure and must remain under explicit human approval control.",
        "allowed": [
            "Auto-approve for payment scheduling only when invoice amount is at or below 10,000 EUR and all prior controls pass.",
            "Route invoices above 10,000 EUR to Finance Manager approval.",
            "Store approval decision, approver, timestamp, and supporting evidence.",
        ],
        "blocked": [
            "Payment scheduling for invoices above 10,000 EUR without manager approval.",
            "Splitting invoices to avoid approval threshold.",
            "AI-generated threshold changes without policy update approval.",
        ],
        "thresholds": [
            THRESHOLDS[0],
            THRESHOLDS[5],
        ],
        "approvals": "Finance Manager approval is required above 10,000 EUR. Finance Controller approval is required for threshold policy changes.",
        "enforcement": "SAP approval threshold task and mock agent validator.",
        "compliant": "A 14,500 EUR invoice passes matching and duplicate checks, then waits for Finance Manager approval before scheduling.",
        "non_compliant": "A 14,500 EUR invoice is auto-approved because it is from a preferred vendor.",
    },
    {
        "title": "Policy 006: Payment Block Controls",
        "area": "payment block controls",
        "statement": "Payment blocks must not be bypassed. Release requires documented controller review and preserved audit evidence.",
        "why": "Payment block bypass is a critical hidden-risk path that can lead to duplicate or unauthorized payments.",
        "allowed": [
            "Create a payment block when duplicate check fails or required control evidence is missing.",
            "Release a payment block after Finance Controller review.",
            "Generate monitoring alerts for bypass attempts.",
        ],
        "blocked": [
            "Manual payment block bypass.",
            "Agent-generated config that enables payment release automatically.",
            "Payment scheduling when block status is active or unknown.",
        ],
        "thresholds": [
            THRESHOLDS[3],
            THRESHOLDS[5],
        ],
        "approvals": "Finance Controller approval is required for release. Process Owner approval is required for block-control workflow changes.",
        "enforcement": "SAP mock payment block controls and agent schema validation.",
        "compliant": "Duplicate check fails, SAP blocks payment, controller reviews, and rejection or release is logged.",
        "non_compliant": "An AP Clerk uses a hidden bypass step to schedule payment before controller review.",
    },
    {
        "title": "Policy 007: Human Approval for Process Changes",
        "area": "human approval for process changes",
        "statement": "Every improvement action must remain pending until a named human approves or rejects it.",
        "why": "The system demonstrates safe agentic execution. AI can propose, but humans authorize process changes.",
        "allowed": [
            "Generate proposals with evidence and required approvers.",
            "Approve or reject individual actions with approver name and comment.",
            "Expose approved actions to the Agents tab.",
        ],
        "blocked": [
            "Executing pending or rejected actions.",
            "Bulk approval without reviewing individual actions.",
            "Changing approval state after approved or rejected without a future admin reset endpoint.",
        ],
        "thresholds": [
            THRESHOLDS[5],
        ],
        "approvals": "Approver role must match the target system and risk level: AP Team Lead, Process Owner, Finance Controller, Finance Manager, or Compliance Officer.",
        "enforcement": "Improvement action approval_status and agent run-action endpoint.",
        "compliant": "A ServiceNow escalation rule is generated, reviewed, approved by AP Team Lead, and only then run by the mock agent.",
        "non_compliant": "An action is generated and immediately executed because its risk level is low.",
    },
    {
        "title": "Policy 008: AI Recommendation Governance",
        "area": "AI recommendation governance",
        "statement": "AI recommendations must be grounded in retrieved documents and mined process evidence, with visible trace and missing information.",
        "why": "The demo must not hallucinate thresholds, systems, metrics, approvals, or policies.",
        "allowed": [
            "Answer using retrieved SOP, policy, canonical process, and mined summary chunks.",
            "Show retrieved sources, mined facts, assumptions, missing information, and confidence.",
            "Refuse when context is insufficient.",
        ],
        "blocked": [
            "Inventing policy thresholds or approval roles.",
            "Presenting hidden chain-of-thought.",
            "Recommending automation when policy context is missing.",
        ],
        "thresholds": [
            "No minimum similarity threshold may be bypassed manually.",
            "If no relevant chunks are retrieved, answer must state context is insufficient.",
        ],
        "approvals": "AI recommendations do not approve actions. Human approval is still required through the improvement workflow.",
        "enforcement": "AI analysis service, RAG search result checks, and visible trace UI labels.",
        "compliant": "The AI cites Policy 002 and mined bottleneck metrics before recommending low-risk price mismatch automation.",
        "non_compliant": "The AI invents a 2 percent tolerance because the retrieved policy did not define one.",
    },
    {
        "title": "Policy 009: Agent Execution Boundaries",
        "area": "agent execution boundaries",
        "statement": "Agents generate and store mock configuration only. They must not call real external systems.",
        "why": "The product demo is local and synthetic. Agent output must be inspectable and safe.",
        "allowed": [
            "Load approved action and related SOP or policy context.",
            "Generate mock configuration JSON for supported target systems.",
            "Validate JSON and store it in mock_system_configs.",
        ],
        "blocked": [
            "Calling Coupa, SAP, ServiceNow, banking, payment, or vendor master APIs.",
            "Running unapproved actions.",
            "Storing configs without fallback, audit logging, enabled=false, or final human enablement.",
        ],
        "thresholds": [
            THRESHOLDS[5],
        ],
        "approvals": "Agent execution requires a prior approved improvement action with approver and comment.",
        "enforcement": "Agent service approval check, target-system validators, and mock_system_configs storage.",
        "compliant": "An approved Coupa rule is generated with enabled=false, requires_final_human_enablement=true, fallback routing, and audit logging.",
        "non_compliant": "The agent sends the generated rule to a live SAP endpoint.",
    },
    {
        "title": "Policy 010: Process Mining Data Quality Requirements",
        "area": "process mining data quality requirements",
        "statement": "Process mining inputs must contain required event-log fields and ordered timestamps per case.",
        "why": "Bad event logs produce misleading hidden paths, bottlenecks, and improvement proposals.",
        "allowed": [
            "Mine CSVs with required columns, case identifiers, activity names, timestamps, system, role, status, and hidden-step indicators.",
            "Reject uploads with missing required columns.",
            "Mark non-canonical or hidden steps as red paths.",
        ],
        "blocked": [
            "Mining uploads with missing timestamps or case identifiers.",
            "Embedding raw event rows into RAG.",
            "Treating synthetic data as production evidence.",
        ],
        "thresholds": [
            "All required columns must be present before mining.",
            "Timestamps must be ordered within each case after parsing.",
        ],
        "approvals": "No human approval is required to mine synthetic logs, but interpretation must label outputs as mined evidence.",
        "enforcement": "CSV upload validator, process miner, and RAG indexing exclusions.",
        "compliant": "A generated event log with hidden_issue_type and is_hidden_step columns is mined and hidden paths are colored red.",
        "non_compliant": "A spreadsheet with activity names only is mined and used for automation proposals.",
    },
    {
        "title": "Policy 011: Audit Logging and Traceability",
        "area": "audit logging and traceability",
        "statement": "Every recommendation, approval, and mock agent execution must retain traceable evidence.",
        "why": "Traceability lets users distinguish mined facts, retrieved sources, AI recommendations, human approvals, and mock generated configurations.",
        "allowed": [
            "Store retrieved chunks used by AI analysis.",
            "Store proposal evidence references and approval comments.",
            "Store agent steps with inputs, outputs, validation result, and final config.",
        ],
        "blocked": [
            "Hiding source chunks used by an answer.",
            "Executing an agent without recording steps.",
            "Logging secrets, credentials, or real external system tokens.",
        ],
        "thresholds": [
            "Every agent run must record seven audit steps.",
            "Every stored mock config must include validation_result.",
        ],
        "approvals": "Approver name and comment are required for human approval records.",
        "enforcement": "rag_queries, improvement_actions, agent_runs, agent_steps, and mock_system_configs tables.",
        "compliant": "An AI answer shows retrieved sources, visible trace, assumptions, missing information, and stored query ID.",
        "non_compliant": "A mock config is stored without showing what action generated it or who approved it.",
    },
    {
        "title": "Policy 012: Change Management and Rollback",
        "area": "change management and rollback",
        "statement": "Approved changes must be generated as disabled mock configurations with rollback and monitoring guidance.",
        "why": "Even safe-looking invoice automation can create financial or compliance risk if enabled without controlled rollout.",
        "allowed": [
            "Generate disabled mock configs that require final human enablement.",
            "Include fallback routing, validation notes, monitoring KPIs, and rollback description.",
            "Keep proposal, approval, and generated config linked.",
        ],
        "blocked": [
            "Generating enabled configs for payment or finance controls.",
            "Omitting fallback behavior or audit logging.",
            "Changing thresholds without policy update approval.",
        ],
        "thresholds": [
            THRESHOLDS[0],
            THRESHOLDS[1],
            THRESHOLDS[2],
            THRESHOLDS[5],
        ],
        "approvals": "Process Owner approval is required for rollback plan acceptance. Finance Controller or Compliance Officer approval is required when finance or compliance controls are affected.",
        "enforcement": "Agent config validation and mock_system_configs status fields.",
        "compliant": "A disabled Coupa exception rule is generated with fallback to AP manual review and monitoring KPIs for reopen rate.",
        "non_compliant": "A new approval threshold is generated and enabled because mined cycle time is high.",
    },
]


def generate_policies(session: Session):
    _ = session
    documents = []
    for policy in POLICIES:
        content = build_policy(policy)
        file_path = write_document_file(policy["title"], content)
        metadata = {"sections": SECTIONS, "thresholds": policy["thresholds"], "process_area": policy["area"], "version": "1.0"}
        documents.append(file_payload(policy["title"], "POLICY", file_path, content, metadata))
    return documents


def build_policy(policy: dict) -> str:
    lines = [f"# {policy['title']}", ""]
    lines.extend(section("Policy statement", policy["statement"]))
    lines.extend(section("Why the policy exists", policy["why"]))
    lines.extend(section("Allowed actions", policy["allowed"]))
    lines.extend(section("Blocked actions", policy["blocked"]))
    lines.extend(section("Thresholds", policy["thresholds"]))
    lines.extend(section("Approval requirements", policy["approvals"]))
    lines.extend(section("System enforcement point", policy["enforcement"]))
    lines.extend(section("Audit requirements", audit_requirements(policy["area"])))
    lines.extend(section("Example compliant case", policy["compliant"]))
    lines.extend(section("Example non-compliant case", policy["non_compliant"]))
    return "\n".join(lines)


def section(title: str, value: str | list[str]) -> list[str]:
    lines = [f"## {title}"]
    if isinstance(value, list):
        lines.extend(f"- {item}" for item in value)
    else:
        lines.append(value)
    lines.append("")
    return lines


def audit_requirements(area: str) -> list[str]:
    return [
        f"Record the policy area: {area}.",
        "Record source document title and file path.",
        "Record retrieved chunks used by AI or improvement generation.",
        "Record approver, approval comment, and approval timestamp before agent execution.",
        "Record generated mock config JSON, validation result, fallback behavior, and audit settings.",
    ]


def write_document_file(title: str, content: str) -> Path:
    directory = settings.root_dir / "docs" / "policy-repository"
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
        "source_repository": "docs/policy-repository",
        "metadata": metadata | {"source_file_path": str(path), "source_repository": "docs/policy-repository"},
        "content": content,
    }
