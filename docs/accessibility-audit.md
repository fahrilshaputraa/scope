# Accessibility & Mobile Audit — H4

Status: implemented  
Scope: Fase 0 / H4. Main flows audited: login, dashboard, project list, project
detail tabs (overview, progress, timeline, tasks, issues, milestones, notes,
activity, history, members), task form/detail, issue list/detail, my tasks,
search, settings, user management, and in-app documentation.

Method: template and JavaScript review of `templates/`, `static/js/`, and
`input.css`, plus regression tests in `tests/test_accessibility.py`. No visual
redesign and no business-logic changes.

## Findings and fixes

| Sev | Page / component | Finding | Fix |
|---|---|---|---|
| High | Project detail → Members | Two `h1` elements (project header plus the member form). | Changed the form heading to `h2`. |
| High | All Django forms (`_form_fields.html`) | Help text was not associated with inputs; widget error text had no `aria-invalid`/`aria-describedby`; required state was only visual. | `style_form` now sets `aria-describedby` (`help-<field>`, `error-<field>`), `aria-required`, and `aria-invalid`; help text renders with `id="help-<field>"`; the required marker has a visually hidden “(wajib)”. |
| High | Login | Field errors had no `role="alert"`, no `aria-invalid`, and no association with inputs. | Added `role="alert"`, `aria-invalid`, `aria-describedby`, and `aria-required` to username/password. |
| High | Forms with scrollable tables | Horizontal scroll containers were not keyboard reachable and had no region semantics. | Added `tabindex="0"`, `role="region"`, and an `aria-label` to table/timeline/board scroll containers on dashboard, project list, issue list, user list, progress, history, portfolio timeline/reports, timeline comparison, task timeline, public timeline, and Kanban. |
| High | Action drawer (`#project-action-panel`) | Native dialog was modal but not explicitly labelled as such, and async save/validation state was silent for screen readers. | Added `aria-modal="true"`, a visually hidden `role="status"` region, and announcements for loading, saving, validation errors, and request failures. Focus return to the opener and Escape handling were already present and remain. |
| Medium | Cards, nav, panels, timelines | Decorative inline SVGs were exposed to assistive tech. | Every template `<svg>` is now `aria-hidden="true" focusable="false"` unless it is a labelled image (`role="img"`). |
| Medium | Chooser widget (`choice_picker.html`) | Checkboxes relied only on a wrapping label and the group `aria-label`. | Each option input now carries `aria-label` with its option label; the search input was already labelled. |
| Medium | Issue list, user list, project list | Active filter/view state was conveyed by colour only. | Added `aria-current="page"` to the active filter and view links. |
| Medium | Search pages (`search.html`, `notes.html`) | Text inputs had placeholders but no label. | Added visually hidden labels and `role="search"` on the forms. |
| Medium | Progress → baseline form | Labels were not associated with their date/number/text inputs. | Added `for`/`id` pairs and `aria-required` on required controls. |
| Medium | Task detail → comments and attachment | Errors rendered without `role="alert"`; attachment help text was not associated. | Errors now use `role="alert"` with ids; `AttachmentForm` exposes help text via `aria-describedby`. |
| Medium | Header at 360–390 px | Long breadcrumbs could force page-level horizontal overflow. | Breadcrumb is now `min-width: 0`, truncates with ellipsis, and `.workspace-content` clips accidental horizontal overflow. Internal table/timeline regions still scroll. |
| Low | Mobile tap targets | Several controls were below ~40 px (buttons, fields, filter chips, project tabs, mobile menu, avatar). | At `max-width: 767px`, buttons, fields, subtle actions, filter links, project tabs, and header controls have a 40 px minimum. |
| Low | Scroll regions | Keyboard focus on scroll regions had no visible indicator. | Added a focus-visible ring for `[tabindex="0"][role="region"]`. |
| Low | Colour tokens | `--faint` failed WCAG AA for body text in both themes (light `#9a9992`: 2.84:1 on surface, 2.57:1 on sunken; dark `#6c6c75`: 3.47:1 on surface). | Light `--faint` → `#6f6e67` (5.12:1 surface, 4.65:1 sunken); dark `--faint` → `#8a8a93` (5.27:1 surface, 4.85:1 sunken). `--muted` was already compliant (light 5.43:1/4.93:1, dark 6.47:1/5.95:1). No other token changed. |

## Verified structure

- One `<main>` and one `<h1>` on login and on the audited workspace pages
  (dashboard, project list, project detail, progress, timeline, issues, issue
  list, my tasks, task form, task detail, user list, user edit, search).
- Skip link `#main-content` is present on every workspace page; login has no
  navigation to skip.
- Navigation landmarks are labelled (`Navigasi utama`, `Bagian project`,
  `Bagian pengaturan`, `Navigasi halaman`, `Filter …`, `Daftar isi artikel`).
- Status indicators always keep their text labels; semantic colours remain
  decorative additions, not the only signal.

## Deferred (with reason)

| Item | Reason |
|---|---|
| Measured 360/390 px overflow run in a real browser | Parent requested no live browser verification; the structural fixes are covered by tests and the CSS is source-only (`input.css`). |
| Presentation slide deck (`presentation/play.html`) multiple `h1`s | Each slide is an independent fullscreen section and only one is visible; changing the deck heading model would alter presentational markup beyond this audit. |
| Native-dialog custom focus trap | `showModal()` already provides browser focus containment; adding a JS trap would duplicate platform behaviour. |
| Regenerating `static/css/output.css` | It is a generated artifact and was explicitly out of scope; the token and responsive changes are in `input.css`. |

## Regression tests

`tests/test_accessibility.py` renders login, dashboard, project list/detail,
progress, timeline, issues, my tasks, task form/detail, user list/edit, and
search. It asserts: one `<main>`/`h1`, working skip link, accessible names on
icon-only controls, modal dialog naming, labelled form controls and required
state, error `role="alert"` with `aria-describedby`, `aria-live` status in the
drawer, focusable labelled scroll regions, and a static template scan for
`<img>` without `alt` and SVGs without `aria-hidden`/`role="img"`.
