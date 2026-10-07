# Product Requirements Document (PRD)

## 1. Product Overview

### Product Name
Project Management & Progress Monitoring System

### Product Type
Internal Project Management / Project Control Center

### Product Purpose

Aplikasi ini digunakan oleh Project Manager, Project Lead, dan Management untuk mengelola dan memonitor project secara terpusat.

Fokus utama aplikasi bukan hanya task management, tetapi memberikan visibility terhadap:

1. Progress project secara keseluruhan
2. Perbandingan Planned Progress vs Actual Progress
3. Timeline project menggunakan Waterfall / Gantt
4. Milestone dan phase project
5. Task dan issue yang sedang dikerjakan
6. Task yang akan dikerjakan
7. Project notes dan project documentation
8. Status project dan risiko
9. Ringkasan project untuk kebutuhan reporting management

Aplikasi harus memberikan kemampuan kepada PM untuk menjawab dengan cepat:

- Project sedang berada di fase apa?
- Seberapa jauh project sudah berjalan?
- Apakah actual progress sesuai dengan plan?
- Apakah project terlambat?
- Task apa yang sedang dikerjakan?
- Apa yang akan dikerjakan berikutnya?
- Apa issue yang sedang menghambat project?
- Milestone apa yang akan datang?
- Project mana yang membutuhkan perhatian management?

---

# 2. Product Vision

Membangun satu centralized Project Control Center yang membuat PM tidak perlu menggunakan banyak tools terpisah untuk melihat:

- Project
- Timeline
- Progress
- Task
- Issue
- Notes
- Milestone
- Reporting

Semua informasi project harus dapat dilihat dari satu aplikasi dengan visualisasi yang sederhana, clean, dan mudah dipahami oleh management.

---

# 3. Target Users

## 3.1 Project Manager

Primary user.

Kebutuhan:

- Membuat project
- Mengatur timeline
- Membuat milestone
- Mengatur task
- Mengelola issue
- Melihat planned progress
- Melihat actual progress
- Membuat project notes
- Monitoring project health
- Menyiapkan informasi untuk reporting

---

## 3.2 Project Member

Kebutuhan:

- Melihat task
- Update task
- Mengubah status task
- Menambahkan comment
- Melaporkan issue
- Melihat timeline
- Melihat milestone

---

## 3.3 Management / Stakeholder

Kebutuhan:

- Melihat seluruh project
- Melihat status project
- Melihat progress
- Melihat deviasi plan vs actual
- Melihat milestone
- Melihat project yang berisiko
- Melihat ringkasan project tanpa harus masuk ke detail teknis

Management tidak perlu mengelola task secara detail.

---

# 4. Core Concept

Aplikasi menggunakan struktur:

Workspace
    ↓
Projects
    ↓
Project
    ├── Overview
    ├── Progress
    ├── Timeline
    ├── Tasks
    ├── Issues
    ├── Milestones
    ├── Notes
    └── Activity

---

# 5. Information Architecture

## Main Navigation

Sidebar:

- Dashboard
- Projects
- My Tasks
- Issues
- Calendar / Timeline
- Notes
- Reports

User Profile

Settings

---

# 6. Dashboard

Dashboard merupakan halaman pertama setelah user login.

Tujuan:

Memberikan overview terhadap seluruh project yang sedang berjalan.

---

## 6.1 Summary Cards

Dashboard harus memiliki summary:

### Total Projects

Contoh:

12 Projects

---

### On Track

Contoh:

8 Projects

---

### At Risk

Contoh:

3 Projects

---

### Delayed

Contoh:

1 Project

---

## 6.2 Project Overview

Tampilkan daftar project dalam bentuk card atau table.

Setiap project menampilkan:

- Project Name
- Project Code
- Project Manager
- Start Date
- Target End Date
- Planned Progress
- Actual Progress
- Variance
- Status
- Current Phase

Contoh:

Project A

Planned:
72%

Actual:
68%

Variance:
-4%

Status:
At Risk

---

# 7. Project List

Halaman Projects digunakan untuk melihat seluruh project.

## View Options

Minimal menyediakan:

- List View
- Card View

Optional:

- Timeline View

---

## Project Card

Project card menampilkan:

Project Name

Project Description

Project Manager

Date Range

Progress

Status

Current Phase

Next Milestone

---

## Project Status

Gunakan status:

- Planning
- On Track
- At Risk
- Delayed
- Completed
- On Hold
- Cancelled

Status tidak boleh hanya berdasarkan actual progress.

Status merupakan status keseluruhan project yang dapat ditentukan berdasarkan:

- Schedule
- Progress
- Issues
- Risk
- Milestone
- PM assessment

---

# 8. Project Detail

Ketika user membuka project, user masuk ke Project Detail.

Header:

Project Name

Project Code

Project Manager

Status

Start Date

Target End Date

Overall Progress

---

## Project Navigation

Gunakan tab:

### Overview
### Progress
### Timeline
### Tasks
### Issues
### Milestones
### Notes
### Activity

Tab harus tetap sederhana dan tidak terlalu banyak.

---

# 9. Project Overview

Overview adalah halaman utama project.

Tujuan:

Memberikan kondisi project dalam satu layar.

---

## 9.1 Project Health

Tampilkan:

Schedule
Progress
Issues
Risk

Contoh:

Schedule
ON TRACK

Progress
68%

Issues
3 Open

Risk
2 Medium

---

## 9.2 Current Phase

Tampilkan phase project saat ini.

Contoh:

Phase 4
Notifications & VMS

Progress:
62%

---

## 9.3 Next Milestone

Contoh:

UAT

Target:
17 October 2026

Status:
Upcoming

---

## 9.4 Current Work

Tampilkan task yang sedang dikerjakan.

Contoh:

Currently Working On

- Scheduler Engine
- Notification API
- Email Reminder Handler

---

## 9.5 Next Up

Tampilkan pekerjaan berikutnya.

Contoh:

Next Up

- Integration Testing
- Performance Testing
- UAT Preparation

---

## 9.6 Recent Activity

Menampilkan aktivitas terbaru:

- Task updated
- Issue created
- Milestone completed
- Note added
- Progress updated
- Timeline changed

---

# 10. Progress Monitoring

Ini merupakan fitur utama aplikasi.

Tujuannya adalah membandingkan:

PLANNED PROGRESS

vs

ACTUAL PROGRESS

dalam satu timeline.

---

# 10.1 Progress Chart

Gunakan line chart.

X Axis:

Tanggal / Week

Y Axis:

0% — 100%

Chart memiliki minimal dua garis:

### Planned Progress

Menunjukkan baseline progress yang seharusnya dicapai berdasarkan project plan.

### Actual Progress

Menunjukkan progress aktual berdasarkan progress task / milestone.

Contoh:

Week 1
Plan: 10%
Actual: 8%

Week 2
Plan: 20%
Actual: 18%

Week 3
Plan: 35%
Actual: 32%

Week 4
Plan: 50%
Actual: 47%

---

# 10.2 Progress Variance

Sistem harus menghitung:

Variance = Actual Progress - Planned Progress

Contoh:

Planned:
61.60%

Actual:
62.44%

Variance:
+0.84%

Interpretasi:

Positive:
Ahead of Schedule

Zero:
On Schedule

Negative:
Behind Schedule

---

# 10.3 Progress Status

Sistem dapat menentukan:

### Ahead

Actual > Plan

### On Track

Actual ≈ Plan

### At Risk

Actual sedikit di bawah Plan

### Delayed

Actual significantly below Plan

Threshold harus configurable.

Contoh default:

Variance >= 0%
    ON TRACK / AHEAD

Variance -1% sampai -5%
    AT RISK

Variance < -5%
    DELAYED

---

# 10.4 Progress Source

Actual Progress dapat dihitung dari:

1. Task completion
2. Milestone completion
3. Phase completion
4. Manual PM adjustment

Default:

Actual Progress dihitung berdasarkan task / milestone.

PM dapat melakukan adjustment apabila diperlukan.

---

# 11. Planned Progress

Planned Progress tidak boleh hanya berupa satu angka.

PM harus dapat membuat baseline progress.

Contoh:

Project Duration:

1 October — 30 November

Plan:

Oct 1
0%

Oct 7
10%

Oct 14
25%

Oct 21
40%

Oct 31
60%

Nov 7
75%

Nov 14
85%

Nov 21
95%

Nov 30
100%

Sistem kemudian membuat Planned Progress Curve.

---

# 12. Actual Progress

Actual progress berasal dari pekerjaan yang benar-benar selesai.

Contoh:

Task:

10 tasks

Completed:

6 tasks

Actual:

60%

Namun sistem harus mendukung weighted progress.

Contoh:

Task A
Weight 10%
Completed

Task B
Weight 30%
Completed

Task C
Weight 60%
50% completed

Actual:

10% + 30% + 30%

= 70%

---

# 13. Waterfall / Gantt Timeline

Project harus memiliki visualisasi timeline menggunakan Waterfall / Gantt Chart.

Tujuannya:

Memberikan gambaran kapan setiap pekerjaan dimulai dan selesai.

---

## Timeline Elements

Setiap task memiliki:

- Task Name
- Start Date
- End Date
- Duration
- Status
- Assignee
- Progress
- Dependency
- Phase

---

## Example

Phase 1
Requirement

| Task | Start | End |
|---|---|---|
| Requirement Gathering | 1 Oct | 3 Oct |
| Requirement Review | 4 Oct | 5 Oct |

Phase 2
Development

| Task | Start | End |
|---|---|---|
| Backend | 6 Oct | 15 Oct |
| Frontend | 8 Oct | 18 Oct |

Phase 3
Testing

| Task | Start | End |
|---|---|---|
| Integration Test | 19 Oct | 22 Oct |
| UAT | 23 Oct | 27 Oct |

---

# 14. Gantt Features

Minimal:

- Zoom Day
- Zoom Week
- Zoom Month
- Current date indicator
- Task bar
- Progress inside task bar
- Milestone marker
- Phase grouping
- Dependency visualization
- Drag to change date
- Resize task duration

---

# 15. Timeline Baseline

Project harus memiliki baseline.

Baseline menunjukkan:

"Pada awal planning, project seharusnya berjalan seperti ini."

Actual timeline menunjukkan:

"Project sebenarnya berjalan seperti ini."

Ini penting untuk melihat schedule deviation.

Contoh:

Baseline:

Development
1 Oct → 10 Oct

Actual:

Development
1 Oct → 14 Oct

Deviation:

+4 Days

---

# 16. Milestones

Milestone merupakan titik penting project.

Contoh:

- Requirement Approved
- Development Complete
- Integration Complete
- UAT Started
- UAT Complete
- Production Release

Milestone memiliki:

- Name
- Date
- Status
- Owner
- Description

Status:

- Upcoming
- In Progress
- Completed
- Delayed

---

# 17. Tasks

Task digunakan untuk mengelola pekerjaan project.

Task memiliki:

- Title
- Description
- Assignee
- Priority
- Status
- Start Date
- Due Date
- Progress
- Phase
- Milestone
- Labels
- Dependencies
- Comments
- Attachments

---

# 18. Task Kanban

Project harus memiliki Kanban Board.

Default columns:

BACKLOG

↓

TODO

↓

IN PROGRESS

↓

BLOCKED

↓

REVIEW

↓

DONE

---

## Kanban Card

Menampilkan:

Task Name

Priority

Assignee

Due Date

Labels

Issue indicator

Progress

---

# 19. Current Work

Sistem harus menyediakan section:

## Currently Working On

Menampilkan task dengan status:

IN PROGRESS

Contoh:

Currently Working On

[ Scheduler Engine ]
Fahril
Due: Oct 10
Progress: 70%

[ Notification API ]
Andi
Due: Oct 11
Progress: 40%

---

# 20. Next Work

Sistem harus menyediakan:

## Next Up

Task yang akan dikerjakan setelah pekerjaan saat ini.

Contoh:

Next Up

1. Integration Testing
2. Performance Testing
3. UAT Preparation

Urutan dapat ditentukan berdasarkan:

- Priority
- Dependency
- Start Date
- Manual ordering

---

# 21. Issues

Issue digunakan untuk mencatat masalah yang menghambat project.

Issue memiliki:

- Title
- Description
- Priority
- Severity
- Status
- Owner
- Created Date
- Due Date
- Resolution
- Related Task

Status:

- Open
- In Progress
- Blocked
- Resolved
- Closed

Priority:

- Critical
- High
- Medium
- Low

---

# 22. Blocked Tasks

Task dapat memiliki status:

BLOCKED

Task yang blocked harus menampilkan alasan.

Contoh:

Task:

Performance Testing

Status:

BLOCKED

Reason:

Production-like environment belum tersedia.

Dependency:

Infrastructure Team

---

# 23. Notes

Project harus memiliki Notes section.

Notes digunakan untuk:

- Meeting notes
- Requirement notes
- Discussion
- Important information
- Decision notes
- Technical notes
- Stakeholder notes

---

## Note

Setiap note memiliki:

- Title
- Content
- Author
- Created Date
- Updated Date
- Tags

Notes dapat dicari.

---

# 24. Decision Log

Project harus memiliki Decision Log.

Tujuannya agar PM dapat mengetahui keputusan penting yang pernah dibuat.

Fields:

- Decision
- Context
- Reason
- Decision Maker
- Date
- Impact

Example:

Decision:

Use Redis for quota management.

Reason:

Reduce database load during high traffic.

Decision Maker:

Technical Lead

Date:

6 October 2026

---

# 25. Activity Log

Sistem harus mencatat aktivitas project.

Contoh:

Fahril updated task "API Integration"

2 hours ago

---

Andi completed "Database Migration"

4 hours ago

---

PM changed project timeline

Yesterday

---

# 26. Reporting

Project harus menyediakan reporting view.

Minimal:

### Executive Summary

- Overall Status
- Progress
- Planned Progress
- Actual Progress
- Variance
- Current Phase
- Next Milestone
- Open Issues
- Open Risks

---

# 27. Management Report

Report harus dapat memberikan informasi:

## Project Status

ON TRACK

## Progress

Planned: 61.60%

Actual: 62.44%

Variance: +0.84%

## Current Phase

Phase 3

## Next Milestone

Phase 4

## Open Issues

3

## Critical Issues

1

## Current Work

3 tasks

## Next Work

4 tasks

---

# 28. Export

System harus mendukung export:

- PDF
- Excel
- CSV

Minimal report yang dapat diexport:

- Project Progress
- Timeline
- Task List
- Issue List
- Milestone
- Project Summary

---

# 29. Project Filters

Project list harus memiliki filter:

- Status
- Project Manager
- Team
- Date
- Progress
- Phase

Search:

Project Name

Project Code

---

# 30. Permissions

## Management

Can:

- View all projects
- View reports
- View progress
- View timeline
- View issues

---

## Project Manager

Can:

- Create project
- Edit project
- Manage timeline
- Manage task
- Manage milestone
- Manage issue
- Add notes
- Update progress
- Manage members

---

## Project Member

Can:

- View assigned projects
- View tasks
- Update assigned task
- Add comments
- Report issue
- Update task status

---

# 31. Project Data Model

## Project

- id
- name
- code
- description
- manager
- start_date
- target_end_date
- actual_end_date
- status
- current_phase
- planned_progress
- actual_progress
- variance

---

## Phase

- id
- project_id
- name
- sequence
- start_date
- end_date
- progress
- status

---

## Task

- id
- project_id
- phase_id
- milestone_id
- title
- description
- assignee
- status
- priority
- start_date
- due_date
- progress
- weight
- parent_task_id

---

## Milestone

- id
- project_id
- name
- date
- status
- description

---

## Issue

- id
- project_id
- task_id
- title
- description
- severity
- priority
- status
- owner
- due_date
- resolution

---

## Note

- id
- project_id
- title
- content
- author
- created_at
- updated_at

---

## Progress Snapshot

- id
- project_id
- date
- planned_progress
- actual_progress
- variance

---

## Decision

- id
- project_id
- title
- context
- decision
- reason
- decision_maker
- created_at

---

# 32. Progress Calculation

System harus mendukung weighted task progress.

Formula:

Actual Project Progress
=
Σ(Task Progress × Task Weight)

Example:

Task A
Weight: 20%
Progress: 100%

Task B
Weight: 30%
Progress: 100%

Task C
Weight: 50%
Progress: 40%

Actual:

20% + 30% + 20%

= 70%

---

# 33. Planned Progress Calculation

Planned progress harus berasal dari project baseline.

PM dapat menentukan:

- Phase
- Task
- Weight
- Planned Start
- Planned End

System kemudian menghasilkan planned cumulative progress.

---

# 34. Progress Snapshot

System harus menyimpan progress secara periodik.

Example:

Date | Plan | Actual | Variance

Oct 1 | 10% | 8% | -2%

Oct 7 | 20% | 18% | -2%

Oct 14 | 35% | 32% | -3%

Oct 21 | 50% | 47% | -3%

Snapshot digunakan untuk membuat historical progress chart.

---

# 35. UX Principles

UI harus:

1. Clean
2. Simple
3. Professional
4. Management-friendly
5. Information dense tetapi tidak overwhelming
6. Mudah dibaca dalam waktu < 30 detik
7. Memprioritaskan informasi penting

Hindari:

- Terlalu banyak warna
- Terlalu banyak card
- Dashboard yang penuh
- Informasi teknis yang tidak diperlukan management
- Terlalu banyak tab
- Visualisasi yang dekoratif tetapi tidak memberikan informasi

---

# 36. Main User Flow

## Flow 1 — View All Projects

Login

↓

Dashboard

↓

Project List

↓

Select Project

↓

Project Overview

---

## Flow 2 — Monitor Project

Project

↓

Overview

↓

Progress

↓

Plan vs Actual

↓

Check Variance

↓

Timeline

↓

Check Delayed Task

↓

Issue

↓

Take Action

---

## Flow 3 — Daily PM Workflow

Login

↓

Dashboard

↓

Check At Risk Projects

↓

Open Project

↓

Check Currently Working On

↓

Check Blocked Tasks

↓

Check Issues

↓

Update Timeline / Task

↓

Add Notes

↓

Review Next Up

---

# 37. Project Overview Layout

Recommended layout:

------------------------------------------------

PROJECT NAME
Status | PM | Start | Target End

------------------------------------------------

Progress

Planned      61.60%
Actual       62.44%
Variance     +0.84%

[ PLAN VS ACTUAL CHART ]

------------------------------------------------

Current Phase

Phase 3 — Development

------------------------------------------------

Timeline

[ MINI GANTT ]

------------------------------------------------

Currently Working On

[Task] [Task] [Task]

------------------------------------------------

Next Up

[Task] [Task] [Task]

------------------------------------------------

Issues

3 Open Issues

------------------------------------------------

Next Milestone

UAT — 17 Oct 2026

------------------------------------------------

Recent Activity

------------------------------------------------

# 38. MVP Scope

MVP harus fokus pada:

### Priority 1

- Project Management
- Project List
- Project Detail
- Project Overview
- Task Management
- Kanban
- Timeline / Gantt
- Planned Progress
- Actual Progress
- Plan vs Actual Chart
- Milestones
- Issues
- Notes

### Priority 2

- Decision Log
- Activity Log
- Export
- Dependencies
- Baseline Timeline

### Priority 3

- Advanced Reporting
- PDF Generator
- Notifications
- Automation
- Resource Management
- Budget Tracking
- Advanced Analytics

---

# 39. Out of Scope for MVP

Tidak perlu membuat:

- Full accounting
- Budget management
- Timesheet
- Payroll
- Chat application
- Full document management
- CRM
- Advanced resource forecasting
- AI project prediction

Fokus MVP adalah:

PROJECT
+
PROGRESS
+
TIMELINE
+
TASK
+
ISSUE
+
NOTES

---

# 40. Success Metrics

Product dianggap berhasil apabila PM dapat menjawab pertanyaan berikut dalam waktu kurang dari 1 menit:

1. Berapa progress project?
2. Planned vs Actual berapa?
3. Project ahead atau behind?
4. Apa yang sedang dikerjakan?
5. Apa yang akan dikerjakan berikutnya?
6. Apa issue terbesar?
7. Kapan milestone berikutnya?
8. Apakah project masih sesuai deadline?

Management harus dapat memahami kondisi project tanpa harus membuka task satu per satu.

---

# 41. Definition of Done — MVP

MVP dianggap selesai apabila:

[ ] PM dapat membuat project

[ ] PM dapat membuat phase

[ ] PM dapat membuat milestone

[ ] PM dapat membuat task

[ ] PM dapat mengatur task melalui Kanban

[ ] PM dapat menentukan start dan end date

[ ] Project memiliki Gantt / Waterfall Timeline

[ ] Project memiliki Planned Progress

[ ] Project memiliki Actual Progress

[ ] System dapat menghitung Progress Variance

[ ] System dapat menampilkan Plan vs Actual Chart

[ ] Project memiliki Issues

[ ] Project memiliki Notes

[ ] Project memiliki Currently Working On

[ ] Project memiliki Next Up

[ ] Project memiliki Activity Log

[ ] Project Overview dapat menampilkan kondisi project secara keseluruhan

[ ] Project dapat difilter berdasarkan status

[ ] Project dapat diexport

---

# 42. Final Product Concept

Aplikasi bukan sekadar:

"Task Management"

Tetapi:

"Project Control Center"

Konsep utamanya:

             PROJECT CONTROL CENTER

                     PROJECT
                        │
       ┌────────────────┼────────────────┐
       │                │                │
    PROGRESS         TIMELINE          WORK
       │                │                │
 Plan vs Actual      Gantt          Kanban
  0% → 100%        Waterfall       Current Work
   Variance         Milestone       Next Up
       │                │                │
       └────────────────┼────────────────┘
                        │
              ┌─────────┴─────────┐
              │                   │
            ISSUES              NOTES
              │                   │
           Blockers          Decisions
           Risks             Meetings
           Problems          Context
              │                   │
              └─────────┬─────────┘
                        │
                   MANAGEMENT
                     REPORT