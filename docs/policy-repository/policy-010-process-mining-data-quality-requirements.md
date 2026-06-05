# Policy 010: Process Mining Data Quality Requirements

## Policy statement
Process mining inputs must contain required event-log fields and ordered timestamps per case.

## Why the policy exists
Bad event logs produce misleading hidden paths, bottlenecks, and improvement proposals.

## Allowed actions
- Mine CSVs with required columns, case identifiers, activity names, timestamps, system, role, status, and hidden-step indicators.
- Reject uploads with missing required columns.
- Mark non-canonical or hidden steps as red paths.

## Blocked actions
- Mining uploads with missing timestamps or case identifiers.
- Embedding raw event rows into RAG.
- Treating synthetic data as production evidence.

## Thresholds
- All required columns must be present before mining.
- Timestamps must be ordered within each case after parsing.

## Approval requirements
No human approval is required to mine synthetic logs, but interpretation must label outputs as mined evidence.

## System enforcement point
CSV upload validator, process miner, and RAG indexing exclusions.

## Audit requirements
- Record the policy area: process mining data quality requirements.
- Record source document title and file path.
- Record retrieved chunks used by AI or improvement generation.
- Record approver, approval comment, and approval timestamp before agent execution.
- Record generated mock config JSON, validation result, fallback behavior, and audit settings.

## Example compliant case
A generated event log with hidden_issue_type and is_hidden_step columns is mined and hidden paths are colored red.

## Example non-compliant case
A spreadsheet with activity names only is mined and used for automation proposals.
