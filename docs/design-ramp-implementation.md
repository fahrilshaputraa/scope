# Ramp UI implementation

DESIGN.md is the visual authority. Inter is self-hosted under the SIL Open Font License as the permitted Lausanne substitute. All interface type uses weight 400 and ss01.

Bone canvas, Paper panels, Ink text, Ash secondary text, and Hairline borders form the shared palette. Chartreuse is reserved for primary actions and selected controls/navigation. Status remains explicit in text, with circles, outlined circles, diamonds, and squares; chart variance uses a dashed outline rather than a second hue.

Contextual create/edit forms use a 600px right-hand drawer and full-width drawer on mobile. Native dialog provides focus containment, Escape dismissal, and background inertness; CSS places it against the viewport edge. Validation stays in the drawer; successful contextual saves reload the underlying page; project import opens the imported project.

Refero MCP returned NO_SUBSCRIPTION. Public Refero Ramp and Linear style pages were fetched successfully; references and bounded adaptation are recorded in docs/ux-simplification.md. No unavailable screen-image fidelity is claimed.

## Visualizations

Timeline and progress panels provide Fullscreen / Keluar fullscreen controls. The same DOM stays mounted, so zoom, data and scroll context are preserved. Native browser fullscreen is preferred; a viewport fallback isolates background controls and supports Escape plus keyboard focus containment. Charts resize with their container.

The current task timeline uses a fixed date axis and mounted CSS rows. Wheel scrolling never triggers re-rendering. Its three data colors distinguish total range, expected progress by today and recorded actual progress. Task/bar links open the existing restricted daily-update drawer inside native fullscreen too. PMs can edit dates via the full planning drawer. Phase management and baseline date comparisons remain available on demand.

Light/Dark/System applies before stylesheet rendering, persists locally and updates Chart.js colors without rebuilding the page. Severity labels include symbols/text independently of color.
