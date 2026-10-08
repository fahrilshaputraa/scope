# Precision UI implementation

DESIGN.md is the visual authority. `input.css` is the single implementation: tokens in `:root` /
`html[data-theme="dark"]`, exposed to Tailwind via `@theme inline`. There are no override layers.

Inter is self-hosted (variable weight `100 900`) under the SIL Open Font License. Body copy is
weight 400; labels, buttons and data use 500; headings and hero numbers use 600.

Neutral canvas, white surfaces, sunken controls and hairline borders form the shared palette. A
single violet accent (`--brand`) is reserved for primary actions, focus, active navigation
indicators, links, and the "actual" chart series. Status stays explicit in text with a colored
dot; severity uses colored chips. Chart variance uses a dashed baseline rather than a second hue.

Contextual create/edit forms use a 600px right-hand drawer and full-width drawer on mobile. Native
`<dialog>` provides focus containment, Escape dismissal, and background inertness; CSS places it
against the viewport edge. Validation stays in the drawer; successful contextual saves reload the
underlying page; project import opens the imported project.

The navbar carries the sidebar-collapse toggle, live search suggestions (htmx), and the account
menu (profile, theme, logout). Search suggestions are fetched from `projects:nav_search`.

## Visualizations

Timeline and progress panels provide Fullscreen / Keluar fullscreen controls. The same DOM stays
mounted, so zoom, data and scroll context are preserved. Native browser fullscreen is preferred; a
viewport fallback isolates background controls and supports Escape plus keyboard focus containment.
Charts resize with their container. Chart controls (zoom group and fullscreen) sit together on the
right of the panel header.

The current task timeline uses a fixed date axis and mounted CSS rows. Wheel scrolling never
triggers re-rendering. Each task uses one bar: a light range track with the plan as a translucent
layer and recorded actual progress as a solid accent layer stacked on top. Task/bar links open the
existing restricted daily-update drawer inside native fullscreen too. PMs can edit dates via the
full planning drawer. Phase management and baseline date comparisons remain available on demand.

Light/Dark/System applies before stylesheet rendering, persists locally and updates Chart.js colors
without rebuilding the page. Severity labels include symbols/text independently of color.
