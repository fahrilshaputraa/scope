# UX simplification: understand, explain, update

## User brief and reference lock

Preserve the approved Ramp UI in DESIGN.md. Prioritize understanding/explaining project health and daily work updates. Planning is secondary. Users aged 20–39 should understand the next action without learning project-management terminology. The user's 90% ease target is a validation goal, not an achieved claim.

Live Refero screen/flow research returned NO_SUBSCRIPTION. Decisions use the existing application, supplied brief, and bundled Refero craft-details.md (specific labels, semantic controls, keyboard/touch access, URL state) and copywriting.md (orientation, status, action; plain descriptive labels).

| Decision | Evidence/source | Rule | Intended effect |
|---|---|---|---|
| One project brief with next action and presentation/copy | User priorities 1 and 3 | Understand and explain the project without collecting scattered facts | Quicker daily review and updates |
| Daily update drawer from personal work rows | Existing task edit permission + restricted TaskForm | Reuse atomic save, status/progress validation and current page | No detour through task detail or planning fields |
| Task creation direct; less frequent actions under Lainnya | User's simplicity brief | Common action visible, options on demand | Fewer competing header controls |
| Plain Indonesian labels + explanation of progress gap | Refero copywriting | Orientation + status + action | Less terminology to decode |
| Schedule and baseline comparison have distinct URL views | Refero craft-details navigation | URL reflects state; browser Back and bookmarking work | One visualization at a time |
| Consistent chart toolbar | User's control-placement feedback | Zoom/time controls and expand control stay in predictable places | Easier viewing and explanation |

## Verify with users

Recruit at least six people across the intended age range and levels of familiarity. Use actual project scenarios: find its condition and target; explain progress and blocker; identify the next work; update progress; report a blocker. Do not coach. Record completion, time, navigation detours and requested assistance. Aim for at least 27/30 tasks completed without help, with project explanation within one minute and routine updates within two minutes. Compare against the current experience before claiming a 90% result. Functional/browser tests verify behavior, not usability or adoption.

## Implementation verification

88 pytest cases pass, including restricted daily-update saves for PM/member, blocker validation, and separate schedule views. Browser regressions cover Gantt wheel stability, fullscreen position preservation, fallback keyboard escape, chart resizing, brief copy/presentation, drawer fields, and 390px mobile containment. Desktop/mobile screenshots were inspected. Django checks and targeted Ruff checks pass. User usability testing remains pending.

## Revision: user's explicit page hierarchy (7 October 2026)

Public Refero styles were fetched after MCP returned NO_SUBSCRIPTION:
- Ramp: https://styles.refero.design/style/b38702a0-75ab-474c-9106-00b624535825 — primary light visual contract already supplied in DESIGN.md; retain Inter, paper surfaces, thin borders and action-only chartreuse.
- Linear: https://styles.refero.design/style/90ce5883-bb24-4466-93f7-801cd617b0d1 — borrow compact spacing, issue identifiers and quiet metadata/control hierarchy, not its dark canvas or decorative color tokens.
- Refero Linear task-management public metadata: https://refero.design/pages/7a7ea171-0cf4-4475-8b45-cc8ec44fde8f — list/badge/progress-bar patterns. Full screen image unavailable via web fetch; do not claim screenshot inspection.

| Decision | Source | Implementation rule |
|---|---|---|
| Compact summary above tabs; large plan/actual chart first | User's numbered breakdown | No standalone brief panel ahead of the chart |
| Same tasks in overview timeline and work list | User's breakdown | Single shared timeline data set, completed/current/next states visible |
| Single current timeline, task/bar opens daily update | User's breakdown | Existing permission checked drawer; detail link and PM planning edit retained |
| Gray future, amber plan, teal actual | User's explicit three-color requirement | Separate data-role tokens; do not repurpose brand CTA accent |
| Issues with severity/status/owner/task/update | User + Linear metadata rules | Severity uses icon + text and dedicated semantic colors |
| Chronological notes/decisions | User's GitHub analogy + craft navigation | Dated feed, type labels, URL filters and clearly labeled decision content |
| Management portfolio overview | User's report objection | All projects compared on shared axis/table; exports secondary |
| Two assignees | User's task request | Existing primary plus one collaborator, both can update; one task weight counted once |

## Final verification of revised layout

93 pytest cases pass, including collaborator permissions, two-person form validation, plan export/import round-trip, PM issue resolution without an owner and inclusive timeline percentages. Browser checks pass for stable timeline wheel scrolling, native/fallback fullscreen, update drawers inside fullscreen, chart resizing, theme persistence and mobile containment. Light/dark desktop and 390px mobile captures were inspected. The main development database has the non-destructive collaborator migration applied. The original 88-test results above describe the superseded first layout.
