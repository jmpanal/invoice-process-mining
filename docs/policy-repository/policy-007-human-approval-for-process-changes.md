# Policy 007: Human Approval for Process Changes

## Policy statement
Every improvement action must remain pending until a named human approves or rejects it.

## Why the policy exists
The system demonstrates safe agentic execution. AI can propose, but humans authorize process changes.

## Allowed actions
- Generate proposals with evidence and required approvers.
- Approve or reject individual actions with approver name and comment.
- Expose approved actions to the Agents tab.

## Blocked actions
- Executing pending or rejected actions.
- Bulk approval without reviewing individual actions.
- Changing approval state after approved or rejected without a future admin reset endpoint.

## Thresholds
- Payment-related agent configs must be generated with enabled=false and requires_final_human_enablement=true.

## Approval requirements
Approver role must match the target system and risk level: AP Team Lead, Process Owner, Finance Controller, Finance Manager, or Compliance Officer.

## System enforcement point
Improvement action approval_status and agent run-action endpoint.

## Audit requirements
- Record the policy area: human approval for process changes.
- Record source document title and file path.
- Record retrieved chunks used by AI or improvement generation.
- Record approver, approval comment, and approval timestamp before agent execution.
- Record generated mock config JSON, validation result, fallback behavior, and audit settings.

## Example compliant case
A ServiceNow escalation rule is generated, reviewed, approved by AP Team Lead, and only then run by the mock agent.

## Example non-compliant case
An action is generated and immediately executed because its risk level is low.
