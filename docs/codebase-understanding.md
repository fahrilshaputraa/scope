# PCC: implementation compared with PRD

## Status setelah perbaikan

Audit awal di bawah dipertahankan sebagai catatan sebelum perubahan. Temuannya
sudah ditangani: login lokal default, keanggotaan dan scope akses, normalisasi
Done, snapshot perubahan + perintah harian, baseline jadwal, dependency, risk
terpisah, attachment privat, ekspor CSV/XLSX/PDF, filter project, serta UI native
yang mengikuti referensi CashPilot (sidebar putih, menu aktif hitam, aksen pastel). Diagram timeline memisahkan baseline/actual,
fase, dan milestone; Gantt menyediakan zoom dan perubahan tanggal untuk PM.

Verifikasi: 60 tes workflow/permission/ekspor, Django check, migration check,
Ruff, build CSS, dan browser Chrome desktop 1440px/mobile 390px. Preview memakai
database demo terpisah. Scheduler snapshot deployment dan konfigurasi Entra ID
bersifat operasional dan belum diaktifkan otomatis. Tidak ada password default.

## Audit awal (sebelum perbaikan)

Reviewed 7 October 2026, revision `3b97925`. Working tree was clean before this document was added. Scope: PRD, login/roles, dashboard/project overview, progress calculations, task workflow, timeline, and feature coverage. This is a source-level requirements review, not a browser-based visual audit.

## Product intent

`PRD.md` describes an internal Project Control Center for PMs, members, and management. Its main outcome is rapid understanding of project health: planned versus actual progress, current phase, current work, next work, blockers, and upcoming milestones. The UI should be clean, professional, information-dense, and readable in under 30 seconds. Prioritize MVP features in PRD section 38 before advanced reporting and automation.

## Architecture and existing functionality

- Django server-rendered templates, Django Cotton components, Tailwind CSS; Alpine and HTMX loaded by the shared shell. `config/urls.py` connects identity, projects, and work routes.
- `apps/identity`: Microsoft Entra OIDC client, Django sessions, user profiles, and global management/PM/member roles.
- `apps/projects`: projects, phases, milestones, baseline points, snapshots, notes, decisions, activity. Services calculate progress and health; views prepare template contexts and perform writes.
- `apps/work`: tasks, issues, comments; endpoints for Kanban status and Gantt date updates.
- Chart.js renders plan versus actual. Frappe Gantt renders tasks. Templates and local vendor assets supply the frontend.
- Existing project list supports list/card views, name/code search, and status/manager/team filters. Dashboard shows status counts and portfolio progress rows. Overview includes health, progress chart, phase, milestone, current/next work, issues, activity.

## Traced flows

### Login and access

`identity:login` renders `templates/identity/login.html`. When Azure is configured, authorize redirects through Authlib; callback obtains claims, calls `upsert_user_from_claims`, synchronizes a profile, creates a Django session, and redirects to a validated local destination. New profiles default to member; SSO claims do not assign application roles. The callback has no application-specific recovery for provider failures or cancellation.

Local login accepts a username and role, creates/reuses a user, and updates their profile role. `dev_login_allowed()` currently returns `DEBUG or not AZURE_ENABLED`. Consequently the local login remains available with debug off if Azure is absent. Authentication configuration must fail closed for normal deployment; role selection belongs in an explicitly enabled development flow.

`permissions.py` restricts project writes to the owning PM (or staff), and task edits to that PM, staff, or assignee. Read queries are broader: dashboard/list/detail, global issues, notes, and reports use authenticated access without project membership scoping. `Project` has a manager and a text team field, but no membership relation or workspace model. PRD section 30 requires members to see assigned projects and PMs to manage members.

### Progress and task completion

`planned_progress_on` linearly interpolates dated baseline points, returning no baseline when empty. `actual_progress` uses a manual override when present; otherwise it normalizes weighted progress of root tasks, excluding subtasks. Variance is actual minus plan. Project status remains a manually stored value distinct from calculated variance level, consistent with the PRD's distinction between overall status and progress status.

Kanban sends PATCH to `work:task_status`. The endpoint checks `can_edit_task`, saves status/completion timestamp, and records activity. It does not set task progress to 100 on Done. `Task.display_progress` nevertheless displays 100 for Done, while `actual_progress` uses raw `task.progress`. A Done task with raw progress 40 therefore displays 100 but contributes 40 to project progress. Completion needs one consistent rule across forms, Kanban, charts, Gantt, and services.

`record_snapshot` updates or creates a snapshot for the selected date. The exposed UI action is manual (`snapshot_now`); no periodic snapshot job was found in the inspected code. Historic chart data uses baseline/snapshot date labels rather than a proportional time axis; uneven date intervals warrant review.

### Kanban and timeline

The board renders six task-status columns. Individual cards allow assignees in their markup, but board-level `data-can-drag` is only set for managers. JavaScript requires both, preventing member drag even when their task API permission allows it. Errors are swallowed rather than shown.

The Gantt context sends task dates and progress, but no dependency edges or milestone markers. Phase names accompany tasks without grouped phase rows. Baseline progress points exist, but separate baseline task start/end dates and baseline-versus-actual timeline rendering do not.

`templates/projects/timeline.html` negates the `can_manage` boolean mapping for `readonly_dates`, reversing the intended lock. Its progress-change handler sends PATCH to the status endpoint without a status value, progress value, or CSRF header. Its date handler ignores unsuccessful responses; `task_dates` also needs chronological validation and safe handling when dates are absent. These are source-level findings pending browser/endpoint regression checks.

## UI and workflow gaps

Based on templates, not screenshots:

- Project header has three progress panels; overview repeats progress in health cards and adds many bordered panels. The hierarchy needs to emphasize project condition and the next PM action rather than giving every section equal weight.
- Overview has no mini Gantt, despite PRD section 37. Blocked tasks appear in Next Up without a dedicated blocker summary or their reason.
- Dashboard lists projects by model ordering, with no attention-first list combining variance, critical issues, blocked work, and imminent milestones. A New Project action is shown to all roles although its destination rejects unauthorized creation.
- Language mixes English and Indonesian; labels, status explanations, errors, and empty states need a consistent convention.
- Login has a basic centered form; development controls and provider login share the same surface. Login errors queued through Django messages are not rendered by this standalone template.
- The shared sidebar's Alpine visibility expression dispatches an event during evaluation. Mobile navigation needs runtime inspection and a clear open/close behavior.
- Global settings is absent from the inspected navigation/routes; membership management is absent. Task forms expose many fields at once and allow assignees to edit planning fields such as weight through the same form as PMs.

## Remaining PRD coverage

| Requirement | Observed state |
| --- | --- |
| Projects, tasks, issues, notes, milestones, decisions, activity | Models and screens implemented; role/workflow details need repair |
| Weighted actual, manual override, dated planned curve | Implemented; Done inconsistency needs repair |
| Member/project access and member management | No membership model; read scoping missing |
| Gantt zoom and date editing | Wiring exists; permissions, persistence feedback, and validation need repair |
| Dependencies and timeline baseline | No dependency edge model or separate baseline task dates found |
| Gantt milestones/phase grouping | Missing from inspected Gantt data/rendering |
| Periodic snapshots | Manual action implemented; scheduled capture not found |
| Risk | Health counts high/critical issues as risks; no independent risk tracking |
| PDF, Excel, CSV export | Reports render HTML; no export implementation found |
| Project filters for date/progress/phase | Status/PM/team/search exist; these filters not implemented in list view |
| Task attachments | No attachment model/flow found |

Risk tracking and export should be scoped against the PRD's priority levels; their absence should not delay the primary monitoring experience unnecessarily.

## Suggested implementation sequence

1. Settle normal login choice (Microsoft SSO or email/password), explicitly gate dev login, add useful auth recovery, define how administrators assign roles, and implement project memberships/read scoping.
2. Repair shared workflow correctness: Done progress, assignee Kanban, Gantt permissions/date persistence, visible failures, and role-appropriate actions/forms. Add targeted regression tests for these invariants.
3. Redesign login and the shared shell, then dashboard and project overview together. Use compact portfolio rows, a prominent progress comparison, clear exception/blocker handling, and restrained status colors. Define a consistent language and responsive behavior.
4. Complete MVP interactions and timeline requirements, then add baseline scheduling, dependencies, periodic snapshots, and exports in PRD priority order.

## Verification and limits

- `.venv/bin/python manage.py check`: passed, no issues. This checks Django configuration, not user workflows.
- In-memory verification using `config.settings.test`, without database writes: a Done task with progress 40 displayed 100 while `actual_progress` returned 40.00.
- `override_settings(DEBUG=False, AZURE_ENABLED=False)`: `dev_login_allowed()` returned True.
- `rg --files tests` returned no test files; README's test command therefore does not establish existing regression coverage.
- No browser rendering, SSO tenant round trip, real account access, database modification, deployment, or application-code changes performed. Visual appearance, mobile behavior, and provider-specific callback behavior remain unverified at runtime.
