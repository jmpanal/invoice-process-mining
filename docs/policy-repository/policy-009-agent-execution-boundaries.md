# Policy 009: Agent Execution Boundaries

## Policy statement
Agents generate and store mock configuration only. They must not call real external systems.

## Why the policy exists
The product demo is local and synthetic. Agent output must be inspectable and safe.

## Allowed actions
- Load approved action and related SOP or policy context.
- Generate mock configuration JSON for supported target systems.
- Validate JSON and store it in mock_system_configs.

## Blocked actions
- Calling Coupa, SAP, ServiceNow, banking, payment, or vendor master APIs.
- Running unapproved actions.
- Storing configs without fallback, audit logging, enabled=false, or final human enablement.

## Thresholds
- Payment-related agent configs must be generated with enabled=false and requires_final_human_enablement=true.

## Approval requirements
Agent execution requires a prior approved improvement action with approver and comment.

## System enforcement point
Agent service approval check, target-system validators, and mock_system_configs storage.

## Audit requirements
- Record the policy area: agent execution boundaries.
- Record source document title and file path.
- Record retrieved chunks used by AI or improvement generation.
- Record approver, approval comment, and approval timestamp before agent execution.
- Record generated mock config JSON, validation result, fallback behavior, and audit settings.

## Example compliant case
An approved Coupa rule is generated with enabled=false, requires_final_human_enablement=true, fallback routing, and audit logging.

## Example non-compliant case
The agent sends the generated rule to a live SAP endpoint.
