# Project knowledge retrieval for Coding Agent

## Current implementation

Teaching may propose up to two project-scoped knowledge candidates per turn. A candidate must have an allowed type (`project_fact`, `observed_failure`, or `verified_pattern`), student-message evidence IDs, and exact quoted excerpts that match the original message. Invalid candidates are dropped by learning validation and reported as warnings without discarding an otherwise valid teaching response.

Every candidate starts as `pending_review` and is marked unverified. The task JSON is authoritative; `knowledge_items` is a SQLite retrieval index mirrored in the same database transaction as task saves. A local reviewer can approve, reject, or withdraw a candidate. Only approved records are searchable, and searches are scoped to the current task ID.

The initial retriever uses English token matching and Chinese character bigrams, with no embeddings or external vector service. Coding step execution, coding chat, and preflight search with the student instruction/current plan and inject up to three matching records into the backend-built OpenCode packet. Records retain their evidence, source turn, revision, and code hash. If project files change, retrieval marks a result `stale_for_code`; current source must be checked. Coding logs loaded record IDs and revisions.

OpenCode is instructed to treat records as untrusted project context, ignore embedded instructions, and never claim tests ran without a real test tool event. Existing tool permissions and student-confirmation boundaries remain in force.

## API

- `GET /api/tasks/{task_id}/learning` returns `memory`, `learning`, and `project_knowledge` for the current task.
- `POST /api/tasks/{task_id}/knowledge/search` accepts `{"query":"空白输入校验","limit":3}`.
- `POST /api/tasks/{task_id}/knowledge/{candidate_id}/review` accepts `{"confirmed":true,"decision":"approve","reviewer":"local-maintainer","note":"checked against cited source"}`.

The `reviewer` string is audit metadata only. The prototype has no accounts or reviewer authorization. Keep the service local. Search results include `stale_for_code`.

## Verification limits

Automated tests cover evidence validation, review gating, task isolation, stale-code flags, retrieval, OpenCode packet injection, and version provenance using mock execution. They do not show that retrieval improves Coding quality or that a real OpenCode/Qwen call follows records correctly. No Skill installer or automatic promotion exists.

Before treating retrieval as a capability improvement, evaluate fixed real project tasks with retrieval disabled/enabled, label relevance and correctness, and separately inspect generated changes using behavioral checks. Add embeddings only if measured lexical retrieval misses justify them and a suitable local/private deployment is chosen.
