# Scope — Precision Design System

> A calm, precise light console for project control. Hairline surfaces, one accent, data-forward.
> Light-first with a fully maintained dark mode.

This file is the visual authority. `input.css` is its single implementation — there are no
override layers, no second opinion. Tokens are defined once in `:root` (light) and
`html[data-theme="dark"]` (dark), then exposed to Tailwind through `@theme inline` so utility
classes (`bg-card`, `border-input`, `text-muted-foreground`, …) recolor automatically.

## Theme

`Light / Dark / System`, chosen from the account menu in the navbar and stored per browser
(`localStorage: scope-theme`). Default is **System**. `theme.js` applies the theme before paint and
repaints Chart.js from the same tokens.

## Color tokens

| Role | Light | Dark |
|---|---|---|
| canvas (app background) | `#fbfbfa` | `#0d0d0f` |
| surface (card / panel) | `#ffffff` | `#16161a` |
| sunken (input / hover / rail) | `#f4f4f2` | `#1e1e23` |
| ink (primary text) | `#16150f` | `#ededf0` |
| muted (secondary text) | `#6b6a63` | `#9a9aa3` |
| faint (tertiary text) | `#9a9992` | `#6c6c75` |
| hairline border | `rgba(22,21,15,.10)` | `rgba(237,237,240,.10)` |
| hairline strong (inputs) | `rgba(22,21,15,.18)` | `rgba(237,237,240,.18)` |
| accent (brand) | `#5b5bd6` | `#7c7cf0` |
| accent hover | `#4a4ac4` | `#8f8ff3` |
| accent soft | `rgba(91,91,214,.10)` | `rgba(124,124,240,.14)` |
| ok | `#17803d` | `#3fb950` |
| warn | `#b7791f` | `#d29922` |
| danger | `#d92d20` | `#f85149` |
| info | `#175cd3` | `#4c8dff` |

Legacy variable names (`--color-ink`, `--color-paper`, `--color-bone`, `--color-ash`,
`--color-hairline`, `--color-smoke`, `--color-obsidian`, `--color-violet`) are kept as aliases so
`theme.js`, Chart.js and template tags keep working unchanged.

**Accent discipline.** `--brand` is the only saturated color and is reserved for primary actions,
focus rings, active navigation indicators, links, and the "actual" data series. Semantic colors
(ok / warn / danger / info) appear as status dots and severity chips — never as decoration, and
never as the only signal (the label text always stays).

## Typography

- Family: **Inter** (self-hosted, variable weight `100 900`), fallback system sans.
- Body 14px / 1.5; dense chrome and tables 13px; minimum label 12px.
- Scale: `12 / 13 / 14 / 16 / 20 / 26 / 32`.
- Weights: `400` body · `500` labels, buttons, data · `600` headings and hero numbers.
- Tracking: headings `-0.02em`; uppercase micro-labels `+0.06em`.
- Tabular numerals (`font-variant-numeric: tabular-nums`) on every metric, table figure, and chart axis.

## Shape, depth, motion

- Radii: `4 / 6 / 8 / 10 / 14 / full`. Buttons and inputs `8`, cards `10`, drawer/popover `14`.
- **Cards never elevate.** Separation comes from 1px hairlines. Shadows are reserved for overlays
  (drawer, menus, popovers, fullscreen) via `--shadow-pop`.
- Spacing on a 4px base; content max-width `1280px`.
- Motion: `140ms` `cubic-bezier(.2,.6,.2,1)`. `prefers-reduced-motion` disables transitions.

## Components

- **Shell** — icon rail (64px collapsed / 220px expanded) with a hairline right edge; the collapse
  toggle lives in the navbar. The active route is a sunken pill with ink text and a 2px accent
  left indicator. Content sits in a centered max-width column.
- **Navbar** — breadcrumb at the left (mobile menu + rail toggle come first); search with live
  htmx suggestions; date; account menu.
- **Buttons** — primary = accent fill, white text, radius 8, weight 500. Secondary = surface with
  hairline border. Hover to `--brand-hover` / sunken.
- **Panels** — surface, 1px hairline, radius 10, no shadow. `.pcc-section` padding 20–24px.
- **Metrics strip** — one hairline-bordered surface with hairline-divided cells (not floating
  cards). Numbers 32px/600.
- **Tables** — 11px uppercase hairline headers, 13px rows, hairline row borders, sunken hover.
- **Status** — dot + label; semantic colors per variant; text label always present.
- **Timeline** — one bar per task: a light "range" track with the plan as a translucent layer and
  actual progress as a solid accent layer stacked on top (`bottom`/`top` edges, not side-by-side
  stripes).
- **Charts** — "Rencana" (baseline) is a muted dashed line with thin hollow point dots; "Actual" is
  a solid accent line with solid points. Chart controls (zoom + fullscreen) group on the right.
- **Drawer** — full-height native `<dialog>` against the right edge, radius 14 on the left,
  `--shadow-pop`, sticky header and actions.
- **Forms** — hairline inputs radius 8, 12px/600 labels, sections via `<details class="form-extra">`,
  unified `.form-actions` footer.

## Do / Don't

**Do**
- Separate surfaces with hairlines; keep the canvas, surface and sunken layers distinct.
- Keep accent usage at one action per view region; use it for active nav, links, and the actual series.
- Use tabular numerals for all data.
- Keep the font stack self-hosted; never link a web font CDN.

**Don't**
- Don't add drop shadows to cards, tables, or inputs.
- Don't use semantic colors decoratively or as the sole carrier of meaning.
- Don't introduce a second saturated brand color.
- Don't create new override files or `!important` layers — extend the tokens instead.

## Quick reference (CSS variables)

```css
:root {
  --canvas:#fbfbfa; --surface:#ffffff; --sunken:#f4f4f2;
  --ink:#16150f; --muted:#6b6a63; --faint:#9a9992;
  --line:rgba(22,21,15,.10); --line-strong:rgba(22,21,15,.18);
  --brand:#5b5bd6; --brand-hover:#4a4ac4; --brand-soft:rgba(91,91,214,.10);
  --ok:#17803d; --warn:#b7791f; --danger:#d92d20; --info:#175cd3;
  --radius-inputs:8px; --radius-cards:10px; --radius-buttons:8px;
  --shadow-pop:0 8px 24px rgba(0,0,0,.08);
  --dur:140ms; --ease:cubic-bezier(.2,.6,.2,1);
}
```
