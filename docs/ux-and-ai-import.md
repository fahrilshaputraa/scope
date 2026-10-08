# Scope — simpler project workflow

The existing main navigation and eight project tabs remain available. Project header actions open a right-hand drawer, save, and retain the current project page. New projects imported from the dashboard open their Tasks page.

## Fast entry

New task: title first, assignee and target date optional. Advanced planning fields remain in Detail tambahan. New project: name first, target date and members visible; manager, generated code, and date defaults reduce setup. Members: search by name/username, click a row to select, then save. Full-page forms remain available when JavaScript is unavailable.

## AI planning

Project → Tambah → Import rencana dari AI → Unduh template JSON. Send the template and brief to the AI; retain version 1 and stable entity keys; use available usernames. Upload the filled JSON. It creates phases, milestones, tasks, assignments and dependencies atomically. Existing data is retained. Identical files do not create duplicates. Export JSON is available for subsequent AI planning; professional CSV/XLSX/PDF exports remain in Reports.

## Verification

85 pytest cases passed, Django system checks, migration consistency and Ruff. Browser checks on an isolated preview database covered searchable member selection, title-only unassigned task creation, current-page preservation, invalid form focus and focus restoration, invalid JSON, complete import, duplicate no-op, dashboard import creating a project, desktop/mobile containment, and no JavaScript exceptions. Live local server remained on port 8001 and serves the new Scope login and assets.

Scope name and logo A were chosen by the user. Brand kit is in docs/brand/scope, downloadable archive docs/brand/scope-kit.zip. Internal PCC identifiers remain stable for compatibility.
