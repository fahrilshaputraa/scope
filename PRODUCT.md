# Scope

<!-- impeccable:product-schema 1 -->

## Platform
web

## Users
Project Managers plan work and monitor delivery. Members update assigned tasks, comments, and issues. Management reads portfolio health and reports.

## Product Purpose
Centralize project progress, timeline, tasks, milestones, issues, notes, and reporting. A user should identify project condition, plan versus actual, blockers, and next work within one minute (PRD sections 35 and 40).

## Operating Context
An internal project management workspace with daily PM review and management reporting. Existing Django server-rendered application; preserve its data and functional workflows.

## Capabilities and Constraints
PRD.md is the requirements authority. The user requested completion of missing workflows, default local accounts with minor login changes, and a replacement UI without shadcn. Use native HTML/CSS and existing Django routing rather than adding another frontend framework.

## Brand Commitments
Scope. Latest user direction: follow the Precision design system in DESIGN.md: light-first, hairline surfaces, neutral canvas, one violet accent reserved for primary actions and active states, and self-hosted Inter. Keep all existing navigation menus. Contextual forms and confirmations open in a right-hand drawer, full width on mobile. Simplify actions and form entry; treat the project as the working hub.

## Usability Commitments
- Users should complete ordinary project actions without training or jumping between pages.
- Keep the current menus; open contextual forms from the project and return to the same view after saving.
- Show the minimum useful fields first, sensible visible defaults, and advanced settings on demand.
- Members are searchable checkbox rows with clear names, selection counts, and no Ctrl/Cmd selection requirement.
- AI planning uses a downloadable JSON template, atomic import, scoped username/reference validation, and duplicate-file protection. Existing data remains available.

## Evidence on Hand
PRD.md, existing implementation, isolated demo data from seed_demo. Demo content must not be presented as real company performance.

## Product Principles
- Surface exceptions and actionable blockers before routine information.
- Keep overall project status distinct from calculated progress variance.
- Apply permissions consistently to pages, actions, downloads, and exports.
- Preserve dates and baseline history instead of hiding schedule deviation.


### UX: ringkasan dan pekerjaan harian

Ringkasan compact tampil di atas tab project. Grafik Rencana vs progress menjadi fokus utama dan dapat dipresentasikan fullscreen. Timeline ringkas dan daftar pekerjaan menggunakan kumpulan task yang sama, termasuk selesai, berjalan dan berikutnya; issue dan task terhambat berada di bawahnya. Jadwal menyediakan satu Timeline saat ini, update melalui drawer, edit jadwal untuk PM, serta phase dan perbandingan baseline di pengaturan tambahan.

Satu task dapat dikerjakan oleh assignee dan satu rekan. Keduanya dapat update, tanpa menggandakan bobot progress. PM dapat menyelesaikan issue tanpa owner. Catatan dan keputusan tampil sebagai feed bertanggal dengan jenis yang eksplisit. Laporan portfolio membandingkan semua project yang dapat diakses pada peta waktu dan tabel. Light/Dark/System tersimpan per browser dan menyesuaikan grafik.

Target kemudahan 90% perlu diuji dengan pengguna, mengikuti `docs/ux-simplification.md`; hasil tes teknis bukan ukuran kemudahan.
