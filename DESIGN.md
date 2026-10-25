# Scope — Neutral Workspace

The supplied workspace screenshots replace the previous violet Precision direction. This document records the implementation; `tokens.css` remains the source of truth.

## Product and composition

Scope supports project managers and team members reviewing progress, updating work, and resolving issues. Use real project data and existing permission checks. Keep routes, form contracts, data hooks and shared partials. No invented metrics or decorative photography.

Use a quiet workspace shell with a pale gray collapsible sidebar, white content, compact header, and horizontal project tabs. Center content within 1400px; wide displays grow gutters. The dashboard leads with linked project totals, then a paired actual/planned progress chart beside the attention list, followed by the full project register. Operational pages retain their tables, boards, forms and feeds with consistent controls.

## Color roles

Light surfaces: canvas `#f6f7f8`, surface `#ffffff`, inset `#eef0f1`. Main text and primary actions use `#171b1a`; secondary text uses `#5d6763`. Structural separators use `#e0e5e2`; editable controls use the stronger `#858e89` edge.

Actual progress uses muted teal `#477c6b`; planned progress uses burnt orange `#b45816`. These colors identify data rather than actions. Actual and planned also have text labels and distinct solid/dashed line styles. Risk remains a labelled semantic state, never a decorative dot.

Success: green text on pale mint. Warning: brown text on pale amber. Danger: burgundy text on pale rose. Information: muted plum text on pale lavender. Use the shared `status_style` recipe. Keep badges readable; color alone must never carry meaning.

Dark mode uses charcoal green surfaces with light text, pale primary actions and dark action text. Progress becomes pale teal/orange. Theme changes refresh chart colors from the same tokens. Preserve light/dark/system preference storage.

Legacy token aliases remain for existing consumers. New code uses semantic tokens; literal colors belong only in token or declared print theme blocks.

## Type and spacing

Use locally hosted Inter. Body copy is 16px, supporting UI and table values 14px, concise labels 12px; page titles 28px (24px mobile). Body weight 400, labels 500, headings 600. Sentence case and untracked labels; no uppercase table headings. Use tabular numerals for progress, dates and counts.

Desktop content padding: 28px 32px. Mobile: 20px 16px. Use 16–24px gaps between related sections. Panels have a 12px radius and fine border; avoid nested panels and decorative shadows. Small controls use 6px radii. Reserve elevation for dialogs and menus.

## Components and behavior

Reuse `.pcc-button`, `.pcc-field`, `.pcc-panel`, `.pcc-status`, `.pcc-progress`, pagination and existing form/quick-update partials. Primary actions are filled neutral; secondary actions use a contrasting outline. Filled actions invert correctly in dark mode.

Project tabs scroll within their own region. On mobile, labelled operational table rows expose all values and actions in two-column records. Timeline comparison tables keep horizontal scrolling. Kanban cards emphasize title, priority, progress, assignees and due date. Status/progress/column editing remains available under native “Perbarui task” disclosure, using the existing hooks.

Every interactive element gets an instant visible focus ring. Preserve semantic labels, skip link, dialog behavior, error feedback and disabled states. Motion is limited to short color/transform transitions with reduced-motion support. Both html and body clip horizontal overflow; scroll belongs to boards, tabs and comparison regions.

## Build and review

Run `npm run css:build` after changing `input.css`, `tokens.css`, `base.css` or template utilities. The generated `static/css/output.css` is ignored by git and must be built in each environment. Run Django checks/tests and inspect representative populated, empty, mobile and dark pages before claiming completion.
