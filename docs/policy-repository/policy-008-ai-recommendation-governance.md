# Policy 008: AI Recommendation Governance

## Policy statement
AI recommendations must be grounded in retrieved documents and mined process evidence, with visible trace and missing information.

## Why the policy exists
The demo must not hallucinate thresholds, systems, metrics, approvals, or policies.

## Allowed actions
- Answer using retrieved SOP, policy, canonical process, and mined summary chunks.
- Show retrieved sources, mined facts, assumptions, missing information, and confidence.
- Refuse when context is insufficient.

## Blocked actions
- Inventing policy thresholds or approval roles.
- Presenting hidden chain-of-thought.
- Recommending automation when policy context is missing.

## Thresholds
- No minimum similarity threshold may be bypassed manually.
- If no relevant chunks are retrieved, answer must state context is insufficient.

## Approval requirements
AI recommendations do not approve actions. Human approval is still required through the improvement workflow.

## System enforcement point
AI analysis service, RAG search result checks, and visible trace UI labels.

## Audit requirements
- Record the policy area: AI recommendation governance.
- Record source document title and file path.
- Record retrieved chunks used by AI or improvement generation.
- Record approver, approval comment, and approval timestamp before agent execution.
- Record generated mock config JSON, validation result, fallback behavior, and audit settings.

## Example compliant case
The AI cites Policy 002 and mined bottleneck metrics before recommending low-risk price mismatch automation.

## Example non-compliant case
The AI invents a 2 percent tolerance because the retrieved policy did not define one.
