# Activity Details Implementation Plan

**Goal:** Support Phase → Activity → optional Detail Activity using existing Task.parent_task.

**Architecture:** Keep Task as the canonical work item. Compute parent display progress from weighted children; retain root-only project and phase weighting. Extend existing forms, views and timeline rather than introduce another model or workflow.

**Tech Stack:** Django, server-rendered templates, existing native JavaScript and CSS.

**Spec:** Agreed conversation: optional details with individual PIC, dates, status and progress; shared project/phase; maximum two Task levels; expandable hierarchy.

## Constraints and review focus

- Reuse TaskForm, task_create, task_detail and timeline_data; preserve authorization.
- Reject cycles, deeper nesting and cross-project parenting. Child phase follows parent, including phase changes.
- A parent with details uses calculated progress even if its stored progress/status says Done. Zero total detail weight produces 0%.
- Parent cannot be marked Done while details remain unfinished; reopening a detail reopens a completed parent.
- Keep existing task and planning-import workflows working; verify hierarchy independently of insertion order.

## Tasks

- [x] Extend Task hierarchy validation and weighted display_progress; protect manual parent progress updates. Cover weighted totals, zero weights, Done/reopen and phase propagation. Weighted calculation is shared in apps/work/progress.py.
- [x] Extend TaskForm and existing creation view with a scoped parent context. Make inherited phase explicit and calculated progress read-only. Test tampering and member permissions.
- [x] Add detail creation/listing to task detail and expandable child links to Kanban. Group timeline rows by parent, expose accessible expand controls, and preserve compact overview behavior.
- [x] Run focused and full pytest suites, Ruff, Django checks, CSS build and desktop/mobile browser verification. Update existing product context where behavior changed.

Verification: 153 pytest tests pass; Ruff and Django checks pass; no migrations needed; CSS builds. Browser checks cover contextual creation, inherited fields, saved parent rollup, timeline collapse/expand, mobile containment and mobile drawer.

Execution continues in the current session under the user's instruction to implement.
