# Policy 011: Audit Logging and Traceability

## Policy statement
Every recommendation, approval, and mock agent execution must retain traceable evidence.

## Why the policy exists
Traceability lets users distinguish mined facts, retrieved sources, AI recommendations, human approvals, and mock generated configurations.

## Allowed actions
- Store retrieved chunks used by AI analysis.
- Store proposal evidence references and approval comments.
- Store agent steps with inputs, outputs, validation result, and final config.

## Blocked actions
- Hiding source chunks used by an answer.
- Executing an agent without recording steps.
- Logging secrets, credentials, or real external system tokens.

## Thresholds
- Every agent run must record seven audit steps.
- Every stored mock config must include validation_result.

## Approval requirements
Approver name and comment are required for human approval records.

## System enforcement point
rag_queries, improvement_actions, agent_runs, agent_steps, and mock_system_configs tables.

## Audit requirements
- Record the policy area: audit logging and traceability.
- Record source document title and file path.
- Record retrieved chunks used by AI or improvement generation.
- Record approver, approval comment, and approval timestamp before agent execution.
- Record generated mock config JSON, validation result, fallback behavior, and audit settings.

## Example compliant case
An AI answer shows retrieved sources, visible trace, assumptions, missing information, and stored query ID.

## Example non-compliant case
A mock config is stored without showing what action generated it or who approved it.
