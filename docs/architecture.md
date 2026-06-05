# Architecture

Synthetic enterprise systems emit invoice events into an event log. The backend stores ideal BPM data, generated event rows, PM4Py mined graph output, documents, chunks, AI traces, improvement approvals, and mock agent configurations.

Flow: Ideal BPM process -> Real event log -> Process mining -> SOPs and policies -> RAG index -> AI analysis -> Improvement proposals -> Human approval -> Mock agent execution.
