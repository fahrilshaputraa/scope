# Scope Workspace Redesign Implementation Plan

> Execute natively in this session using the existing Django templates and shared components. The user has authorized the redesign and replacement of the previous visual direction.

**Goal:** Redesign the template system around the supplied neutral workspace references, with black actions, teal actual progress, orange planning data, and accessible pastel status labels.

**Architecture:** Keep existing views, permissions, form contracts, route names, selectors and data. Recompose the dashboard and project shell and extend the existing shared styles and partials. Color and type tokens have one canonical definition; existing legacy aliases continue to support charts and template tags.

**Tech Stack:** Django templates, Tailwind CSS 4, Alpine, HTMX, existing local Inter and SVG assets.

**Spec:** User reference screenshots and the replacement `DESIGN.md`.

## Constraints

- Preserve the pre-existing `docs/gap-analysis-roadmap.md` working-tree edit.
- Keep every route, form field, permission condition, event selector and data operation.
- Retain light/dark/system preferences and navigation collapse behavior.
- Reuse `.pcc-button`, `.pcc-field`, `.pcc-panel`, status recipes, pagination, form and quick-update partials.
- No new dependency, invented product data, deleted templates or replacement backend.
- Maintain accessible focus, contrast, mobile navigation, dialog semantics and reduced motion.

## Review focus

- Long project/task names and a large Kanban column must remain navigable.
- Empty and populated pages retain meaningful actions.
- Staff-only user actions retain access checks and confirmation.
- Light and dark active states retain readable text and fields.
- Mobile tables expose identity and actions; project navigation does not consume the screen.

## Tasks

- [x] Extract the existing token and global base rules; replace their palette and document the new system.
- [x] Recompose the dashboard and project chrome; remove duplicate/decorative dashboard surfaces.
- [x] Apply shared typography, statuses, forms, tables and mobile rules throughout templates.
- [x] Collapse Kanban editing controls into accessible disclosure while keeping all hooks.
- [x] Rebuild CSS, render before/after representative routes in an isolated database, inspect mobile/dark views and run Hallmark.
- [x] Run the existing Django tests and checks, review the diff and report remaining limitations accurately.

## Verification outcome

CSS build and Django checks pass. The full suite passed 313 tests; the final accessibility check passed 33 tests. Ten browser interaction checks passed. Source comparison retained all 199 URL references and 547 hook/form attributes across 65 templates. The pre-existing roadmap diff is unchanged.

Hallmark rendered 12 routes and three dark variants. Its raw output still reports findings, primarily external-stylesheet detection, inherited data punctuation, hidden disclosures and long record names. The report in this thread's `hallmark-redesign/report.md` records the counts, manual decisions and limits; this is not an automated clean-lint claim. Four existing notification migrations remain unapplied in the local database; rendering used a migrated in-memory copy.
