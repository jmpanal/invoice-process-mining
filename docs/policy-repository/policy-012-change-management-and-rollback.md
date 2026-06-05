# Policy 012: Change Management and Rollback

## Policy statement
Approved changes must be generated as disabled mock configurations with rollback and monitoring guidance.

## Why the policy exists
Even safe-looking invoice automation can create financial or compliance risk if enabled without controlled rollout.

## Allowed actions
- Generate disabled mock configs that require final human enablement.
- Include fallback routing, validation notes, monitoring KPIs, and rollback description.
- Keep proposal, approval, and generated config linked.

## Blocked actions
- Generating enabled configs for payment or finance controls.
- Omitting fallback behavior or audit logging.
- Changing thresholds without policy update approval.

## Thresholds
- Finance manager approval required above 10,000 EUR.
- Low-risk price mismatch auto-resolution can be proposed only below 1,000 EUR.
- Price mismatch tolerance for demo is 1.5 percent.
- Payment-related agent configs must be generated with enabled=false and requires_final_human_enablement=true.

## Approval requirements
Process Owner approval is required for rollback plan acceptance. Finance Controller or Compliance Officer approval is required when finance or compliance controls are affected.

## System enforcement point
Agent config validation and mock_system_configs status fields.

## Audit requirements
- Record the policy area: change management and rollback.
- Record source document title and file path.
- Record retrieved chunks used by AI or improvement generation.
- Record approver, approval comment, and approval timestamp before agent execution.
- Record generated mock config JSON, validation result, fallback behavior, and audit settings.

## Example compliant case
A disabled Coupa exception rule is generated with fallback to AP manual review and monitoring KPIs for reopen rate.

## Example non-compliant case
A new approval threshold is generated and enabled because mined cycle time is high.
