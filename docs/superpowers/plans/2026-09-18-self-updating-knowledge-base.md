# Self-updating Knowledge Base Implementation Plan

**Goal:** Add a safe learning loop that detects likely knowledge gaps in chat, groups repeated questions, lets a teacher review/edit them, and makes approved answers immediately searchable.

**Safety boundary:** Conversation-derived content is only a candidate. It cannot affect future answers until an authenticated teacher approves it. Store the question and draft answer, not full chat history.

## Task 1: Persistent learning inbox

**Files:** `app/learning.py`, `tests/test_learning.py`, `.gitignore`

- Write failing tests for question normalization, duplicate counting, persistence, approve/reject transitions, and approved-entry search.
- Implement an atomic JSON-backed `LearningStore` guarded by a lock.
- Keep runtime learning data under `data/` and out of Git.

## Task 2: Detect gaps and use approved knowledge

**Files:** `app/main.py`, `tests/test_chat_api.py`

- Write failing chat tests proving an empty/weak retrieval creates a candidate while a strong retrieval does not.
- Merge approved entries with uploaded-document results before answer generation.
- Record only low-confidence questions after generating the draft answer.
- Add authenticated list, approve, and reject endpoints.

## Task 3: Teacher review interface

**Files:** `app/static/admin.html`, `app/static/admin.js`, `app/static/admin.css`, `tests/test_admin_frontend.py`

- Write failing static contract tests for the review queue and controls.
- Render occurrence count, timestamps, editable draft answer, and approve/reject actions.
- Refresh counters after review and explain that approval is required before publication.
- Version admin assets to avoid stale browser caches.

## Task 4: Verification and project record

**Files:** `MEMORY.md`

- Run targeted tests, full Python suite, JavaScript syntax checks, animation runtime test, and `git diff --check`.
- Verify the authenticated admin page and review queue in the local browser without publishing test data.
- Append the dated implementation record, verification results, and remaining limitations to `MEMORY.md`.

