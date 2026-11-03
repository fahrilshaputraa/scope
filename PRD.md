# PRODUCT REQUIREMENTS DOCUMENT (PRD)
# SCOPE — Project Control Center

**Document Version:** 2.0  
**Document Status:** Revised Draft  
**Product Type:** Internal Project Management & Project Control Platform  
**Product Positioning:** Project Control Center  
**Primary Focus:** Project, Progress, Timeline, Task, Issue, Governance, Reporting

---

# 1. Product Overview

## 1.1 Product Name

**SCOPE — Project Control Center**

## 1.2 Product Description

SCOPE adalah platform internal untuk mengelola, memonitor, dan mengontrol berbagai jenis project secara terpusat.

SCOPE tidak hanya berfungsi sebagai task management application, tetapi sebagai sistem yang menghubungkan:

- Project Planning
- Project Execution
- Progress Monitoring
- Schedule Control
- Issue & Risk Management
- Project Governance
- Reporting & Management Visibility

SCOPE harus mampu digunakan untuk berbagai jenis project, seperti:

- IT & Software Development
- Infrastructure
- Network & System Implementation
- Operational Projects
- Business Improvement
- Digital Transformation
- General Project Management

Karena karakteristik setiap project dapat berbeda, SCOPE menggunakan pendekatan **Universal Core + Configurable Workflow**.

Artinya, setiap project menggunakan fondasi pengelolaan yang sama, tetapi struktur, workflow, field, milestone, dan approval dapat disesuaikan dengan kebutuhan project.

## 1.3 Product Purpose

SCOPE bertujuan menyediakan satu sumber informasi yang terpusat untuk mengetahui:

1. Apa saja project yang sedang berjalan?
2. Project sedang berada di fase apa?
3. Seberapa jauh project sudah berjalan?
4. Apakah actual progress sesuai dengan baseline?
5. Apakah project mengalami keterlambatan?
6. Task apa yang sedang dikerjakan?
7. Siapa yang bertanggung jawab atas setiap pekerjaan?
8. Task mana yang mengalami hambatan?
9. Milestone apa yang akan datang?
10. Project mana yang membutuhkan perhatian?
11. Keputusan apa yang sudah dibuat?
12. Bagaimana kondisi keseluruhan portfolio project?

## 1.4 Product Vision

Membangun satu centralized Project Control Center yang memberikan visibility, structure, progress tracking, dan control terhadap seluruh project dalam organisasi.

SCOPE harus membantu Project Manager mengendalikan pelaksanaan project, membantu Project Member menjalankan pekerjaannya, membantu Project Owner memastikan outcome tercapai, dan membantu Management memahami kondisi project secara menyeluruh.

---

# 2. Product Foundation

## 2.1 Product Principles

SCOPE dibangun berdasarkan lima prinsip utama.

| Principle | Description |
|---|---|
| Progress | Setiap project harus memiliki progress yang terukur. |
| Structure | Project memiliki struktur pekerjaan yang jelas dan fleksibel. |
| Visibility | Informasi project dapat dilihat sesuai role dan permission. |
| Control | Penyimpangan, hambatan, dan perubahan dapat dikendalikan. |
| Focus | Informasi yang ditampilkan harus relevan dengan tanggung jawab pengguna. |

## 2.2 Product Personality

- Operational
- Professional
- Calm
- Clear
- Structured
- Management-friendly

## 2.3 Core Problems

SCOPE dikembangkan untuk menyelesaikan beberapa masalah berikut:

**Fragmented Information**
Informasi project tersebar di berbagai aplikasi, dokumen, spreadsheet, dan komunikasi.

**Low Project Visibility**
Management kesulitan mendapatkan gambaran kondisi project secara cepat.

**Unclear Progress**
Progress project tidak selalu mencerminkan kondisi pekerjaan yang sebenarnya.

**Schedule Deviation**
Penyimpangan antara rencana dan aktual sering terlambat diketahui.

**Coordination Problems**
Pembagian tanggung jawab dan tindak lanjut pekerjaan tidak selalu jelas.

**Weak Project Accountability**
Tidak ada keterkaitan yang konsisten antara pekerjaan, assignee, milestone, dan target project.

**Reporting Overhead**
Project Manager harus mengumpulkan informasi secara manual untuk membuat laporan.

---

# 3. Target Users & Role Model

SCOPE menggunakan sistem multi-role. Satu akun pengguna dapat memiliki beberapa role sesuai tanggung jawabnya.

## 3.1 Workspace Admin

Bertanggung jawab atas pengelolaan platform pada tingkat workspace.

Responsibilities:
- Mengelola user dan membership.
- Mengelola konfigurasi workspace.
- Mengelola project templates.
- Mengelola konfigurasi permission.
- Mengelola pengaturan sistem.
- Melihat aktivitas administratif.

Workspace Admin tidak otomatis menjadi approver project.

## 3.2 Project Manager (PM)

Project Manager merupakan pihak yang bertanggung jawab mengelola dan mengontrol pelaksanaan project.

Responsibilities:
- Membuat dan mengelola project plan.
- Mengatur struktur project.
- Membuat phase, work package, task, dan milestone.
- Menentukan assignee.
- Mengatur timeline dan dependency.
- Memonitor progress seluruh task.
- Memeriksa planned vs actual progress.
- Mengidentifikasi keterlambatan.
- Memantau blocked tasks.
- Mengelola issues dan risks.
- Melakukan follow-up kepada assignee.
- Mengelola change request.
- Menyiapkan project reports.

**Project Manager bukan assignee task.**

Project Manager bertanggung jawab mengontrol pekerjaan yang dilakukan oleh Project Member.

PM tidak memperbarui progress task sebagai pelaksana pekerjaan. PM dapat memperbarui data perencanaan atau informasi kontrol sesuai permission.

## 3.3 Project Member

Project Member merupakan pihak yang melaksanakan pekerjaan dalam project.

Responsibilities:
- Melihat task yang ditugaskan.
- Melaksanakan pekerjaan.
- Memperbarui task status.
- Memperbarui actual progress.
- Memberikan komentar dan update.
- Melaporkan hambatan.
- Melampirkan evidence atau hasil pekerjaan.
- Submit task untuk review jika approval diperlukan.

Project Member hanya dapat memperbarui pekerjaan sesuai assignment dan permission.

## 3.4 Project Owner

Project Owner bertanggung jawab terhadap outcome dan keberhasilan project dari sisi business atau organisasi.

Responsibilities:
- Melihat kondisi project.
- Memantau pencapaian target.
- Memantau milestone dan deliverables.
- Memberikan keputusan strategis.
- Menyetujui perubahan sesuai kewenangan.
- Memberikan arahan kepada Project Manager.
- Memantau project risks dan major issues.

Project Owner tidak otomatis mengelola task operasional.

## 3.5 Client / Stakeholder

Client atau Stakeholder memiliki akses terbatas sesuai keterlibatan dalam project.

Responsibilities:
- Melihat progress yang diizinkan.
- Melihat milestone.
- Melihat deliverables.
- Memberikan feedback.
- Melakukan acceptance jika diberikan kewenangan.
- Melihat informasi project yang dibagikan kepadanya.

## 3.6 Management

Management berfokus pada portfolio visibility dan pengambilan keputusan.

Responsibilities:
- Melihat keseluruhan project sesuai akses.
- Memantau project health.
- Memantau plan vs actual.
- Melihat project yang delayed atau at risk.
- Memantau major issues dan risks.
- Melihat laporan portfolio.
- Melakukan approval jika diberikan kewenangan.

Management tidak perlu mengelola task secara detail.

---

# 4. Multi-Role & Role-Based Workspace Switcher

## 4.1 Core Concept

SCOPE menggunakan satu akun untuk beberapa role.

Satu user dapat memiliki beberapa role sekaligus dan dapat berpindah tampilan melalui Role-Based Workspace Switcher pada sidebar.

Contoh:

User: Andi

Available roles:
- Project Manager
- Project Owner

Ketika Andi memilih Project Manager Workspace, sistem menampilkan navigasi dan dashboard Project Manager.

Ketika Andi memilih Project Owner Workspace, sistem menampilkan navigasi dan dashboard Project Owner.

## 4.2 Role-Based Workspace

Setiap role memiliki workspace mode tersendiri.

| Workspace Mode | Primary Focus |
|---|---|
| Admin Workspace | Workspace administration |
| Project Manager Workspace | Project monitoring and control |
| Project Member Workspace | Task execution and progress updates |
| Project Owner Workspace | Project outcome and strategic oversight |
| Client Workspace | Project visibility and deliverable acceptance |
| Management Workspace | Portfolio monitoring and reporting |

## 4.3 Role Switcher Behavior

Role switcher harus tersedia pada sidebar.

Ketika user berpindah role:

- Sidebar navigation berubah.
- Dashboard berubah.
- Available actions berubah.
- Permission context berubah.
- Data yang ditampilkan mengikuti akses user.
- User tidak perlu login ulang.
- User identity tetap sama.

Role switching tidak boleh memberikan akses baru yang tidak dimiliki user.

## 4.4 Business Rules

| ID | Rule |
|---|---|
| BR-ROLE-001 | Satu user menggunakan satu akun untuk seluruh role yang dimilikinya. |
| BR-ROLE-002 | Satu user dapat memiliki beberapa role. |
| BR-ROLE-003 | User dapat berpindah role melalui sidebar switcher. |
| BR-ROLE-004 | Setiap role memiliki navigasi dan dashboard tersendiri. |
| BR-ROLE-005 | Perpindahan role tidak membutuhkan login ulang. |
| BR-ROLE-006 | Permission mengikuti role context yang aktif. |
| BR-ROLE-007 | Role switch tidak boleh memperluas akses di luar authorization yang diberikan. |
| BR-ROLE-008 | Semua aktivitas tetap tercatat atas identitas user yang sama. |
| BR-ROLE-009 | Data hanya dapat diakses sesuai workspace dan project membership. |
| BR-ROLE-010 | Role yang tidak dimiliki user tidak boleh ditampilkan sebagai pilihan. |

---

# 5. Product Architecture

SCOPE menggunakan pendekatan:

**Universal Core + Configurable Workflow**

## 5.1 Universal Core

Fitur inti yang digunakan oleh seluruh jenis project:

- Project Management
- Project Structure
- Task Management
- Progress Monitoring
- Timeline Management
- Milestone Management
- Issue Management
- Risk Management
- Reporting
- Activity Log
- Approval Management

## 5.2 Configurable Workflow

Setiap project dapat memiliki konfigurasi tersendiri.

Configurable elements:
- Project type.
- Project lifecycle.
- Phase structure.
- Work package structure.
- Task status workflow.
- Milestone templates.
- Custom fields.
- Progress calculation method.
- Weighting method.
- Approval configuration.
- Deliverable requirements.

## 5.3 Template System

Project Template digunakan untuk mempercepat pembuatan project.

Template dapat menyimpan:
- Project type.
- Default project structure.
- Default phases.
- Default work packages.
- Default tasks.
- Default milestones.
- Task workflow.
- Custom fields.
- Progress calculation settings.
- Approval rules.

Perubahan template tidak otomatis mengubah project yang sudah dibuat.

Project yang sudah berjalan hanya berubah melalui proses konfigurasi atau perubahan yang disetujui.

---

# 6. Information Architecture

## 6.1 Role-Based Sidebar

Navigasi harus menyesuaikan workspace mode yang aktif.

### Project Manager Workspace

- Dashboard
- Projects
- Progress Task
- Project Control
- Issues & Risks
- Calendar
- Approvals
- Reports

### Project Member Workspace

- Dashboard
- My Assignments
- Progress Task
- Calendar
- My Reviews (jika ditugaskan sebagai reviewer)

### Project Owner Workspace

- Dashboard
- Projects
- Project Outcomes
- Milestones
- Approvals
- Reports

### Management Workspace

- Portfolio Dashboard
- Projects
- Portfolio Health
- Reports
- Approvals

### Client Workspace

- Dashboard
- Projects
- Progress
- Deliverables
- Approvals / Acceptance
- Updates

### Admin Workspace

- Dashboard
- Users
- Workspaces
- Roles & Permissions
- Templates
- Settings
- Audit Logs

## 6.2 Progress Task vs Project Control

Keduanya merupakan fitur berbeda.

**Progress Task**

Digunakan untuk melihat perkembangan pekerjaan.

Project Member:
- Melihat task yang ditugaskan.
- Memperbarui status.
- Memperbarui progress.
- Menambahkan evidence.
- Mengirim pekerjaan untuk review.

Project Manager:
- Melihat progress seluruh task dalam project.
- Melihat assignee.
- Melihat status dan progress.
- Memantau pekerjaan yang sedang berjalan.
- Melihat pekerjaan yang belum dimulai dan selesai.

PM menggunakan Progress Task untuk monitoring, bukan sebagai pelaksana.

**Project Control**

Digunakan oleh PM untuk melakukan kontrol terhadap pelaksanaan project.

Capabilities:
- Memantau task overdue.
- Memantau blocked tasks.
- Melihat task yang menunggu review.
- Mengidentifikasi keterlambatan.
- Melakukan reassignment.
- Mengelola dependency.
- Memantau schedule deviation.
- Melakukan follow-up.
- Mengelola perubahan project.

---

# 7. Project Management

## 7.1 Project Creation

PM atau user dengan permission yang sesuai dapat membuat project.

Required fields:
- Project Name
- Project Code
- Project Type
- Project Owner
- Project Manager
- Start Date
- Target End Date
- Description

Optional fields:
- Project Template
- Department
- Team
- Client
- Priority
- Custom Fields

## 7.2 Project Lifecycle

Default lifecycle:

- Draft
- Planning
- In Progress
- On Hold
- Completed
- Cancelled

Project health merupakan atribut terpisah dari lifecycle.

Project health:
- On Track
- At Risk
- Delayed
- Critical

Lifecycle menjawab status keberadaan project.

Health menjawab kondisi pelaksanaan project.

Contoh:

Project lifecycle: In Progress

Project health: At Risk

## 7.3 Project Status Rules

- Project baru dibuat dengan status Draft atau Planning.
- Project tidak dapat masuk In Progress sebelum planning requirements terpenuhi.
- Project dapat diubah menjadi On Hold.
- Project Completed membutuhkan closure requirements.
- Project Cancelled membutuhkan cancellation reason.
- Setiap perubahan status harus tercatat dalam activity log.

## 7.4 Project List

Project List menyediakan:

- List View
- Card View
- Filter
- Search
- Sorting
- Pagination

Project list fields:
- Project Name
- Project Code
- Project Manager
- Project Owner
- Start Date
- Target End Date
- Planned Progress
- Actual Progress
- Variance
- Lifecycle Status
- Project Health
- Current Phase
- Next Milestone

Filters:
- Project Type
- Lifecycle Status
- Project Health
- Project Manager
- Project Owner
- Team
- Date Range
- Progress Range
- Current Phase

---

# 8. Project Structure

## 8.1 Hybrid Hierarchy

SCOPE menggunakan struktur project yang fleksibel.

Default hierarchy:

Workspace
→ Project
→ Phase / Stage
→ Work Package (optional)
→ Task / Work Item
→ Subtask (optional)

## 8.2 Entity Definitions

**Project**

Unit utama yang memiliki tujuan, timeline, owner, manager, dan progress.

**Phase / Stage**

Tahapan utama dalam project.

Contoh:
- Planning
- Design
- Development
- Testing
- Deployment

**Work Package**

Pengelompokan pekerjaan dalam suatu phase.

Contoh:
- Backend Development
- Frontend Development
- Infrastructure Setup

**Task / Work Item**

Unit pekerjaan yang memiliki assignee dan dapat diukur progress-nya.

**Subtask**

Pekerjaan turunan dari sebuah task.

## 8.3 Structure Rules

- Project menjadi root dari seluruh struktur.
- Phase dan Work Package dapat digunakan sesuai kebutuhan.
- Task merupakan unit pekerjaan yang dapat dieksekusi.
- Subtask bersifat optional.
- Setiap task harus memiliki project.
- Task dapat memiliki parent task.
- Dependency tidak boleh membentuk circular dependency.
- Struktur dapat diubah oleh user yang memiliki permission.
- Perubahan struktur setelah baseline harus tercatat.
- Data historis tidak boleh hilang akibat perubahan struktur.

## 8.4 Structure Operations

Sistem harus mendukung:
- Create.
- Edit.
- Delete jika aman.
- Archive.
- Reorder.
- Move.
- Duplicate.
- Bulk create.
- Import.
- Expand / collapse hierarchy.

Penghapusan task yang sudah memiliki histori harus mengikuti aturan archival atau soft delete.

---

# 9. Task Management

## 9.1 Task Attributes

Setiap task memiliki:

- Task ID
- Title
- Description
- Project
- Phase
- Work Package
- Parent Task
- Assignee
- Reviewer (optional)
- Priority
- Status
- Progress
- Weight
- Start Date
- Due Date
- Dependencies
- Milestone (optional)
- Labels
- Attachments
- Comments
- Created By
- Created At
- Updated At

## 9.2 Task Responsibility

SCOPE memisahkan empat tanggung jawab:

| Responsibility | Definition |
|---|---|
| Assignee | Orang yang melaksanakan pekerjaan. |
| Reviewer | Orang yang memeriksa hasil pekerjaan. |
| Project Manager | Orang yang mengontrol pekerjaan dalam project. |
| Project Owner | Orang yang bertanggung jawab atas outcome project. |

Project Manager bukan assignee task.

Project Member merupakan pelaksana task.

Reviewer dapat berasal dari Project Member, Project Manager, Project Owner, atau pihak lain jika diberikan kewenangan.

## 9.3 Task Status

Default status:

- Backlog
- To Do
- In Progress
- In Review
- Blocked
- Done

Workflow dapat dikonfigurasi melalui project template.

## 9.4 Task Status Rules

| Status | Meaning |
|---|---|
| Backlog | Pekerjaan belum dijadwalkan atau belum siap. |
| To Do | Pekerjaan siap dikerjakan. |
| In Progress | Pekerjaan sedang dilaksanakan. |
| In Review | Pekerjaan menunggu pemeriksaan. |
| Blocked | Pekerjaan terhambat. |
| Done | Pekerjaan selesai. |

Rules:
- Done berarti progress 100%.
- Blocked harus memiliki blocking reason.
- In Review membutuhkan reviewer jika approval diwajibkan.
- Task yang ditolak saat review kembali ke status yang dapat dikerjakan.
- Perubahan status dicatat dalam activity log.

## 9.5 Task Kanban

Default Kanban columns:

- Backlog
- To Do
- In Progress
- In Review
- Blocked
- Done

Kanban harus mendukung:
- Drag and drop.
- Filtering.
- Grouping.
- Search.
- Assignee filter.
- Priority filter.
- Phase filter.
- Due date filter.

Task card menampilkan:
- Title
- Assignee
- Priority
- Due Date
- Progress
- Labels
- Dependency indicator
- Issue indicator

---

# 10. Progress Task

Progress Task merupakan area untuk melihat perkembangan seluruh pekerjaan.

## 10.1 Member View

Project Member dapat melihat:
- Assigned tasks.
- Task status.
- Actual progress.
- Due date.
- Priority.
- Dependency.
- Blocking reason.
- Reviewer.
- Review feedback.

Member dapat:
- Update status.
- Update progress.
- Add comment.
- Upload evidence.
- Report issue.
- Submit task for review.

Member tidak dapat memperbarui task yang bukan tanggung jawabnya, kecuali diberikan permission khusus.

## 10.2 Project Manager View

Project Manager dapat melihat seluruh task dalam project yang dikelolanya.

Informasi:
- Task
- Phase
- Assignee
- Status
- Progress
- Planned Start
- Planned End
- Actual Start
- Actual End
- Due Date
- Schedule Deviation
- Review Status

PM dapat:
- Filter berdasarkan assignee.
- Filter berdasarkan phase.
- Filter berdasarkan status.
- Filter berdasarkan due date.
- Melihat task overdue.
- Melihat task blocked.
- Melihat task yang belum dimulai.
- Melihat task yang menunggu review.
- Melakukan reassignment jika memiliki permission.
- Melakukan follow-up.

PM tidak memperbarui actual progress sebagai pelaksana task.

## 10.3 Progress Update Rules

- Actual progress diperbarui oleh assignee.
- Progress update harus mencatat user dan timestamp.
- Progress update dapat menyertakan komentar atau evidence.
- Progress yang sudah disetujui tidak boleh diubah tanpa mengikuti aturan koreksi.
- Perubahan progress menjadi bagian dari historical snapshot.

---

# 11. Progress Calculation Engine

Progress Engine merupakan salah satu komponen inti SCOPE.

Sistem harus memisahkan:

1. Work Progress
2. Planned Progress
3. Schedule Performance
4. Project Health

## 11.1 Task Progress Methods

Setiap task menggunakan satu primary progress method.

**Method A — Manual Percentage**

Assignee memperbarui progress secara manual.

Contoh:
- 0%
- 20%
- 50%
- 80%
- 100%

**Method B — Status Based**

Progress dihitung berdasarkan status task.

Contoh default:
- Backlog: 0%
- To Do: 0%
- In Progress: configurable
- In Review: configurable
- Blocked: mempertahankan progress terakhir
- Done: 100%

**Method C — Subtask Based**

Progress parent task dihitung berdasarkan progress subtask.

Parent task tidak boleh menghitung progress dari subtask sekaligus menerima manual progress tanpa aturan override yang jelas.

## 11.2 Weighted Progress

SCOPE menggunakan hybrid weighting.

Default:
- Sistem membuat bobot otomatis dengan pembagian sama rata.

Optional:
- PM dapat mengatur bobot secara manual.

Bobot sibling work items harus memiliki total 100%.

Contoh:

| Task | Weight | Progress |
|---|---:|---:|
| Task A | 20% | 100% |
| Task B | 30% | 100% |
| Task C | 50% | 40% |

Actual Progress:

(20% × 100%) + (30% × 100%) + (50% × 40%)

= 20% + 30% + 20%

= **70%**

## 11.3 Parent Progress

Parent progress:

Parent Progress = Σ (Child Weight × Child Progress)

Sistem harus mencegah double counting antara parent dan child.

## 11.4 Project Actual Progress

Project actual progress dihitung dari weighted leaf work items.

Parent item tidak boleh dihitung kembali apabila child items sudah menjadi sumber progress.

## 11.5 Planned Progress

Planned progress berasal dari approved project baseline.

Baseline mencakup:
- Planned Start.
- Planned End.
- Task Weight.
- Planned Task Progress.
- Milestone Target.
- Phase Schedule.

Sistem menghasilkan cumulative planned progress berdasarkan jadwal pekerjaan.

Untuk MVP, sistem dapat menggunakan distribusi linear berdasarkan durasi task sebagai default.

Sistem harus dapat dikembangkan untuk mendukung:
- Manual planned progress curve.
- Milestone-based curve.
- Custom progress distribution.

## 11.6 Progress Variance

Formula:

Variance = Actual Progress - Planned Progress

Contoh:

Planned: 61.60%

Actual: 62.44%

Variance: +0.84 percentage points

Interpretasi:
- Positive: Ahead.
- Zero: On Schedule.
- Negative: Behind.

## 11.7 Progress Status Threshold

Default thresholds:

| Variance | Status |
|---|---|
| >= 0 percentage points | On Track / Ahead |
| -1 sampai -5 percentage points | At Risk |
| < -5 percentage points | Delayed |

Threshold dapat dikonfigurasi.

## 11.8 Progress Snapshot

Sistem menyimpan snapshot secara periodik.

Snapshot minimal mencakup:
- Snapshot Date.
- Planned Progress.
- Actual Progress.
- Variance.
- Baseline Version.
- Project Health.
- Schedule Performance.

Snapshot digunakan untuk:
- Historical chart.
- Period reporting.
- Trend analysis.
- Management report.

Historical snapshot tidak boleh dihitung ulang menggunakan baseline baru.

---

# 12. Project Timeline & Gantt

## 12.1 Purpose

Timeline digunakan untuk menunjukkan urutan dan durasi pekerjaan dalam project.

SCOPE menggunakan visualisasi Waterfall / Gantt.

## 12.2 Timeline Elements

Setiap task memiliki:
- Task Name
- Planned Start
- Planned End
- Actual Start
- Actual End
- Duration
- Status
- Assignee
- Progress
- Dependency
- Phase
- Work Package

## 12.3 Gantt Features

Minimal:
- Day Zoom
- Week Zoom
- Month Zoom
- Current Date Indicator
- Task Bars
- Progress Indicator
- Milestone Marker
- Phase Grouping
- Dependency Lines
- Drag to Change Date
- Resize Task Duration
- Baseline Comparison

## 12.4 Timeline Baseline

Baseline menunjukkan jadwal yang sudah disetujui.

Current Schedule menunjukkan jadwal terkini.

Contoh:

Baseline:
Development — 1 October sampai 10 October

Current Schedule:
Development — 1 October sampai 14 October

Schedule Deviation:
+4 days

Baseline tidak boleh berubah otomatis ketika current schedule diedit.

## 12.5 Schedule Performance

Sistem harus memantau:
- Overdue task.
- Late start.
- Late finish.
- Schedule deviation.
- Dependency delay.
- Milestone delay.

Task yang melewati due date dan belum selesai tetap dianggap overdue meskipun progress-nya sudah 95%.

---

# 13. Milestone Management

Milestone merupakan titik penting dalam project.

Contoh:
- Requirement Approved.
- Design Completed.
- Development Completed.
- Integration Testing Completed.
- UAT Completed.
- Production Release.

## 13.1 Milestone Attributes

- Name
- Description
- Project
- Phase
- Target Date
- Actual Date
- Owner
- Status
- Related Tasks
- Evidence

## 13.2 Milestone Status

- Upcoming
- In Progress
- Completed
- Delayed

Milestone tidak otomatis selesai hanya karena tanggal target sudah lewat.

Milestone selesai jika completion requirements terpenuhi.

---

# 14. Deliverable Management

Deliverable merupakan hasil pekerjaan yang harus diserahkan atau diterima.

Deliverable berbeda dari milestone.

Milestone adalah titik pencapaian.

Deliverable adalah output pekerjaan.

Deliverable attributes:
- Name
- Description
- Related Task
- Owner
- Submission Date
- Due Date
- Acceptance Criteria
- Evidence
- Reviewer
- Acceptance Status

Acceptance Status:
- Draft
- Submitted
- Under Review
- Accepted
- Rejected

Client atau Project Owner dapat melakukan acceptance jika diberikan permission.

---

# 15. Issue Management

Issue digunakan untuk mencatat masalah yang sudah terjadi dan membutuhkan penyelesaian.

## 15.1 Issue Attributes

- Title
- Description
- Project
- Related Task
- Phase
- Severity
- Priority
- Status
- Owner
- Created Date
- Due Date
- Resolution
- Evidence

## 15.2 Issue Status

- Open
- In Progress
- Blocked
- Resolved
- Closed

## 15.3 Issue Priority

- Critical
- High
- Medium
- Low

Issue yang berstatus Resolved harus memiliki resolution.

## 15.4 Blocked Task

Task yang blocked wajib memiliki:
- Blocking Reason.
- Blocking Dependency (optional).
- Reported By.
- Reported At.

PM harus dapat melihat seluruh blocked task dalam project.

---

# 16. Risk Management

Risk berbeda dari Issue.

Risk merupakan potensi kejadian yang dapat memengaruhi project.

Issue merupakan masalah yang sudah terjadi.

## 16.1 Risk Attributes

- Title
- Description
- Project
- Probability
- Impact
- Risk Score
- Owner
- Mitigation Plan
- Review Date
- Status

## 16.2 Risk Rules

- Risk harus memiliki owner.
- Risk harus memiliki mitigation plan.
- Risk harus memiliki review date.
- Risk score dihitung dari probability dan impact.
- Risk dapat dikonversi menjadi Issue ketika benar-benar terjadi.
- Perubahan risk harus tercatat.

---

# 17. Change Request & Scope Control

Perubahan project dibagi menjadi minor dan major.

## 17.1 Minor Change

Minor changes dapat dilakukan langsung jika tidak berdampak pada approved baseline.

Contoh:
- Typo correction.
- Description correction.
- Label update.
- Informasi tambahan yang tidak mengubah scope.

## 17.2 Major Change

Major changes membutuhkan Change Request.

Contoh:
- Perubahan deliverable.
- Perubahan project scope.
- Perubahan target milestone.
- Perubahan project deadline.
- Perubahan dependency yang signifikan.
- Perubahan bobot pekerjaan yang berdampak pada baseline.

## 17.3 Change Request Workflow

Draft → Submitted → Under Review → Approved / Rejected → Applied

Change Request harus menyimpan:
- Requester.
- Description.
- Reason.
- Impact Assessment.
- Schedule Impact.
- Scope Impact.
- Approval History.

Approved change tidak otomatis mengubah historical baseline.

Perubahan baseline dilakukan melalui baseline revision yang disetujui.

---

# 18. Approval Management

Approval harus configurable berdasarkan kebutuhan project.

## 18.1 Approval Types

- Project Plan Approval.
- Baseline Approval.
- Task Approval.
- Deliverable Acceptance.
- Change Request Approval.
- Project Closure Approval.

## 18.2 Approval Configuration

Setiap project dapat menentukan:
- Approval required or optional.
- Approver.
- Sequential approval.
- Parallel approval.
- Approval conditions.
- Rejection requirements.

## 18.3 Task Approval

Jika task membutuhkan approval:

1. Assignee menyelesaikan pekerjaan.
2. Assignee submit task.
3. Task masuk In Review.
4. Reviewer memeriksa hasil.
5. Reviewer menyetujui atau menolak.
6. Jika approved, task menjadi Done.
7. Jika rejected, task kembali ke status yang dapat dikerjakan dan menyimpan rejection reason.

Task yang tidak membutuhkan approval dapat diselesaikan langsung oleh assignee.

## 18.4 Approval Rules

- Approval authority terpisah dari role umum.
- Assignment tidak otomatis memberikan approval authority.
- Self-approval harus dicegah jika approval policy melarangnya.
- Rejection wajib memiliki alasan.
- Approval history harus disimpan.
- Perubahan approval configuration harus tercatat.

---

# 19. Notes & Decision Log

## 19.1 Project Notes

Notes digunakan untuk menyimpan informasi project.

Use cases:
- Meeting Notes.
- Requirement Notes.
- Discussion.
- Technical Notes.
- Stakeholder Notes.
- Important Information.

Note attributes:
- Title
- Content
- Author
- Created Date
- Updated Date
- Tags
- Attachments

Notes dapat dicari.

## 19.2 Decision Log

Decision Log digunakan untuk mencatat keputusan penting.

Fields:
- Decision Title
- Context
- Decision
- Reason
- Decision Maker
- Date
- Impact
- Related Project
- Related Issue (optional)

Contoh:

Decision:
Use Redis for quota management.

Reason:
Reduce database load during high traffic.

Decision Maker:
Technical Lead.

Date:
6 October 2026.

---

# 20. Activity Log & Audit Trail

SCOPE harus mencatat aktivitas penting.

Contoh:
- User created project.
- PM changed project timeline.
- Member updated task progress.
- Member submitted task for review.
- Reviewer approved task.
- PM reassigned task.
- User created issue.
- Project Owner approved change request.
- User changed baseline.

Audit fields:
- Actor.
- Active Role.
- Workspace Context.
- Timestamp.
- Entity Type.
- Entity ID.
- Action.
- Previous Value.
- New Value.
- Reason (when required).

Activity Log digunakan untuk aktivitas operasional.

Audit Trail digunakan untuk histori perubahan yang membutuhkan traceability.

---

# 21. Dashboard

Dashboard harus berbeda berdasarkan workspace mode.

## 21.1 Project Manager Dashboard

Tujuan: Memberikan gambaran project yang perlu dimonitor dan dikontrol.

KPI:
- Active Projects.
- On Track Projects.
- At Risk Projects.
- Delayed Projects.
- Open Issues.
- Pending Approvals.

Sections:
- Projects Requiring Attention.
- Project Health.
- Planned vs Actual Overview.
- Overdue Tasks.
- Blocked Tasks.
- Pending Reviews.
- Upcoming Milestones.
- Recent Activities.

PM dashboard harus memprioritaskan informasi yang membutuhkan tindakan.

## 21.2 Project Member Dashboard

Tujuan: Membantu Member mengetahui pekerjaan yang perlu dilaksanakan.

Sections:
- Assigned Tasks.
- In Progress.
- Upcoming Tasks.
- Overdue Tasks.
- Blocked Tasks.
- Tasks Waiting for Review.
- Recent Updates.

## 21.3 Project Owner Dashboard

Tujuan: Memantau outcome dan keberhasilan project.

Sections:
- Owned Projects.
- Project Health.
- Target vs Actual Progress.
- Milestone Achievement.
- Major Issues.
- Major Risks.
- Pending Decisions.
- Deliverable Acceptance.

## 21.4 Management Dashboard

Tujuan: Melihat kondisi portfolio secara keseluruhan.

Sections:
- Total Projects.
- Project Health Distribution.
- On Track / At Risk / Delayed.
- Portfolio Progress.
- Planned vs Actual.
- Major Issues.
- Critical Risks.
- Upcoming Major Milestones.
- Projects Requiring Management Attention.

Management dashboard tidak perlu menampilkan detail task teknis secara default.

## 21.5 Client Dashboard

Tujuan: Memberikan transparansi terhadap project yang dibagikan.

Sections:
- Project Overview.
- Project Progress.
- Upcoming Milestones.
- Deliverables.
- Pending Acceptance.
- Recent Updates.

---

# 22. Project Detail

Project Detail merupakan pusat informasi satu project.

Header:
- Project Name.
- Project Code.
- Project Manager.
- Project Owner.
- Lifecycle Status.
- Project Health.
- Start Date.
- Target End Date.
- Overall Progress.

## 22.1 Project Navigation

Recommended tabs:

1. Overview
2. Structure
3. Progress
4. Timeline
5. Work Board
6. Milestones
7. Issues & Risks
8. Deliverables
9. Documents & Notes
10. Activity

Tab yang tidak relevan dapat disembunyikan berdasarkan konfigurasi atau permission.

## 22.2 Project Overview

Overview harus menampilkan kondisi project secara ringkas.

Sections:
- Project Health.
- Planned vs Actual Progress.
- Current Phase.
- Next Milestone.
- Schedule Performance.
- Current Work.
- Next Up.
- Issues & Risks.
- Recent Activity.

---

# 23. Reporting

SCOPE harus menyediakan reporting pada beberapa tingkat.

## 23.1 Project Executive Summary

Minimal:
- Project Name.
- Project Owner.
- Project Manager.
- Lifecycle Status.
- Project Health.
- Planned Progress.
- Actual Progress.
- Variance.
- Current Phase.
- Next Milestone.
- Open Issues.
- Open Risks.
- Schedule Deviation.

## 23.2 Project Progress Report

Menampilkan:
- Planned Progress.
- Actual Progress.
- Variance.
- Historical Progress.
- Progress Trend.
- Phase Progress.
- Task Completion.

## 23.3 Project Schedule Report

Menampilkan:
- Baseline Schedule.
- Current Schedule.
- Schedule Deviation.
- Overdue Tasks.
- Delayed Milestones.
- Upcoming Milestones.

## 23.4 Task Report

Menampilkan:
- Total Tasks.
- Completed.
- In Progress.
- Blocked.
- In Review.
- Overdue.
- Task Distribution by Assignee.

## 23.5 Management Report

Menampilkan:
- Portfolio Summary.
- Project Health.
- Progress Comparison.
- Delayed Projects.
- Critical Issues.
- Major Risks.
- Upcoming Milestones.
- Management Attention Required.

## 23.6 Export

Format:
- PDF.
- Excel.
- CSV.

Exportable reports:
- Project Summary.
- Project Progress.
- Timeline.
- Task List.
- Issue List.
- Risk List.
- Milestones.
- Deliverables.

---

# 24. Business Rules

## 24.1 Project Rules

| ID | Business Rule |
|---|---|
| BR-PROJ-001 | Project harus memiliki nama, code, type, PM, dan target date. |
| BR-PROJ-002 | Project code harus unik dalam workspace. |
| BR-PROJ-003 | Project baru berstatus Draft atau Planning. |
| BR-PROJ-004 | Project hanya dapat berjalan jika planning requirements terpenuhi. |
| BR-PROJ-005 | Lifecycle status terpisah dari project health. |
| BR-PROJ-006 | Completed project harus memenuhi closure requirements. |
| BR-PROJ-007 | Cancelled project wajib memiliki alasan. |
| BR-PROJ-008 | Perubahan status project tercatat dalam audit trail. |

## 24.2 Task Rules

| ID | Business Rule |
|---|---|
| BR-TASK-001 | Setiap task harus terhubung ke project. |
| BR-TASK-002 | Task executable harus memiliki assignee sebelum dieksekusi. |
| BR-TASK-003 | Assignee merupakan pihak yang bertanggung jawab mengerjakan task. |
| BR-TASK-004 | Project Manager bukan assignee task. |
| BR-TASK-005 | Project Member mengerjakan task sesuai assignment. |
| BR-TASK-006 | PM dapat memonitor seluruh task dalam project. |
| BR-TASK-007 | PM dapat melakukan reassignment jika memiliki permission. |
| BR-TASK-008 | PM tidak memperbarui actual progress sebagai pelaksana task. |
| BR-TASK-009 | Actual progress diperbarui oleh assignee. |
| BR-TASK-010 | Task blocked wajib memiliki blocking reason. |
| BR-TASK-011 | Task Done memiliki progress 100%. |
| BR-TASK-012 | Task yang membutuhkan approval harus melalui review workflow. |
| BR-TASK-013 | Setiap perubahan progress dan status dicatat. |
| BR-TASK-014 | Circular dependency tidak diperbolehkan. |

## 24.3 Weighting Rules

| ID | Business Rule |
|---|---|
| BR-WGT-001 | Default weighting menggunakan pembagian otomatis yang sama. |
| BR-WGT-002 | PM dapat mengubah weight secara manual sesuai permission. |
| BR-WGT-003 | Total weight dalam satu kelompok sibling harus 100%. |
| BR-WGT-004 | Perubahan weight setelah baseline harus tercatat. |
| BR-WGT-005 | Perubahan weight yang berdampak pada baseline mengikuti change control. |
| BR-WGT-006 | Parent dan child tidak boleh dihitung dua kali. |

## 24.4 Scope Change Rules

| ID | Business Rule |
|---|---|
| BR-CHG-001 | Minor changes dapat dilakukan langsung jika tidak memengaruhi baseline. |
| BR-CHG-002 | Major changes harus melalui Change Request. |
| BR-CHG-003 | Change Request wajib memiliki reason dan impact assessment. |
| BR-CHG-004 | Rejected Change Request tidak boleh diterapkan. |
| BR-CHG-005 | Approved changes dapat menghasilkan baseline revision. |
| BR-CHG-006 | Baseline lama tetap tersimpan sebagai histori. |

## 24.5 Role & Workspace Rules

| ID | Business Rule |
|---|---|
| BR-ROLE-001 | Satu user memiliki satu account identity. |
| BR-ROLE-002 | Satu user dapat memiliki beberapa role. |
| BR-ROLE-003 | User dapat berpindah role melalui sidebar switcher. |
| BR-ROLE-004 | Setiap role memiliki dashboard dan navigasi sendiri. |
| BR-ROLE-005 | Perpindahan role tidak membutuhkan login ulang. |
| BR-ROLE-006 | Permission mengikuti role context aktif. |
| BR-ROLE-007 | Role switch tidak memberikan akses di luar authorization user. |
| BR-ROLE-008 | Aktivitas mencatat user dan role aktif. |
| BR-ROLE-009 | User hanya dapat melihat data sesuai scope aksesnya. |

## 24.6 Approval Rules

| ID | Business Rule |
|---|---|
| BR-APR-001 | Approval dapat dikonfigurasi per project. |
| BR-APR-002 | Approval authority terpisah dari role umum. |
| BR-APR-003 | Assignee tidak otomatis menjadi approver. |
| BR-APR-004 | Rejection wajib memiliki alasan. |
| BR-APR-005 | Approval history tidak boleh dihapus. |
| BR-APR-006 | Self-approval mengikuti konfigurasi approval policy. |

---

# 25. Permission Matrix

Keterangan:
- ✓ = Allowed.
- Conditional = Allowed jika memiliki permission tambahan atau memenuhi kondisi.
- — = Not allowed by default.

| Action | Admin | PM | Member | Owner | Client | Management |
|---|---|---|---|---|---|---|
| View authorized projects | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Create project | ✓ | Conditional | — | Conditional | — | Conditional |
| Edit project details | ✓ | ✓ | — | Conditional | — | — |
| Manage project structure | ✓ | ✓ | — | Conditional | — | — |
| Create task | ✓ | ✓ | Conditional | Conditional | — | — |
| Assign task | ✓ | ✓ | — | Conditional | — | — |
| Execute task | Conditional | — | ✓ | — | — | — |
| Update task progress | Conditional | — | ✓ | — | — | — |
| Monitor all project tasks | ✓ | ✓ | — | Conditional | — | Conditional |
| Reassign task | ✓ | ✓ | — | Conditional | — | — |
| Review task | Conditional | Conditional | Conditional | Conditional | — | — |
| Approve task | Conditional | Conditional | Conditional | Conditional | — | Conditional |
| Manage milestones | ✓ | ✓ | — | Conditional | — | — |
| Manage issues | ✓ | ✓ | Conditional | Conditional | — | — |
| Manage risks | ✓ | ✓ | — | Conditional | — | — |
| Submit change request | ✓ | ✓ | Conditional | ✓ | Conditional | Conditional |
| Approve change request | Conditional | Conditional | — | Conditional | Conditional | Conditional |
| View reports | ✓ | ✓ | Conditional | ✓ | Conditional | ✓ |
| Manage users | ✓ | — | — | — | — | — |
| Manage templates | ✓ | — | — | — | — | — |

Approval permissions harus diberikan secara eksplisit melalui approval configuration.

## 25.1 Permission Granularity

Permission harus dapat dikonfigurasi melalui action-level permissions.

Contoh:

- `project.view`
- `project.create`
- `project.update`
- `project.archive`
- `project.manage_members`
- `structure.view`
- `structure.create`
- `structure.update`
- `task.view`
- `task.create`
- `task.assign`
- `task.execute`
- `task.update_progress`
- `task.reassign`
- `task.review`
- `task.approve`
- `timeline.view`
- `timeline.update`
- `baseline.view`
- `baseline.approve`
- `issue.manage`
- `risk.manage`
- `change_request.submit`
- `change_request.approve`
- `report.view`
- `report.export`

Permission harus memperhitungkan:
- Role.
- Workspace context.
- Project membership.
- Resource assignment.
- Approval authority.

---

# 26. Data Model

## 26.1 User

- id
- name
- email
- password_hash
- status
- created_at
- updated_at

## 26.2 Workspace

- id
- name
- code
- description
- status
- created_at

## 26.3 User Role / Membership

- id
- user_id
- workspace_id
- role_id
- status
- assigned_at
- assigned_by

Satu user dapat memiliki beberapa membership dan role.

## 26.4 Role

- id
- name
- description
- scope
- permission_config

## 26.5 Project

- id
- workspace_id
- name
- code
- description
- project_type
- project_owner_id
- project_manager_id
- start_date
- target_end_date
- actual_end_date
- lifecycle_status
- health_status
- current_phase_id
- created_at
- updated_at

## 26.6 Project Membership

- id
- project_id
- user_id
- project_role
- status
- joined_at

## 26.7 Project Template

- id
- workspace_id
- name
- project_type
- structure_config
- workflow_config
- progress_config
- approval_config
- custom_fields
- version

## 26.8 Phase

- id
- project_id
- name
- sequence
- start_date
- end_date
- status

## 26.9 Work Package

- id
- project_id
- phase_id
- parent_id
- name
- sequence
- start_date
- end_date

## 26.10 Task

- id
- project_id
- phase_id
- work_package_id
- parent_task_id
- title
- description
- assignee_id
- reviewer_id
- status
- priority
- progress_method
- progress
- weight
- planned_start
- planned_end
- actual_start
- actual_end
- due_date
- created_at
- updated_at

## 26.11 Milestone

- id
- project_id
- phase_id
- name
- description
- target_date
- actual_date
- owner_id
- status

## 26.12 Deliverable

- id
- project_id
- task_id
- name
- description
- acceptance_criteria
- submission_date
- due_date
- reviewer_id
- acceptance_status

## 26.13 Issue

- id
- project_id
- task_id
- title
- description
- severity
- priority
- status
- owner_id
- due_date
- resolution

## 26.14 Risk

- id
- project_id
- title
- description
- probability
- impact
- risk_score
- owner_id
- mitigation_plan
- review_date
- status

## 26.15 Change Request

- id
- project_id
- requester_id
- title
- description
- reason
- impact_assessment
- status
- created_at
- reviewed_at

## 26.16 Approval

- id
- project_id
- entity_type
- entity_id
- approver_id
- approval_type
- status
- decision
- reason
- decided_at

## 26.17 Baseline

- id
- project_id
- version
- approved_by
- approved_at
- baseline_data
- change_request_id

## 26.18 Progress Snapshot

- id
- project_id
- baseline_id
- snapshot_date
- planned_progress
- actual_progress
- variance
- health_status

## 26.19 Note

- id
- project_id
- title
- content
- author_id
- created_at
- updated_at

## 26.20 Decision

- id
- project_id
- title
- context
- decision
- reason
- decision_maker_id
- created_at

## 26.21 Activity Log

- id
- workspace_id
- project_id
- actor_id
- active_role_id
- entity_type
- entity_id
- action
- previous_value
- new_value
- created_at

---

# 27. Main User Flows

## Flow 1 — User Login & Role Switching

Login
→ Dashboard
→ Role-Based Workspace Switcher
→ Select Role
→ Load Role-Specific Dashboard
→ Access Features Based on Permission

## Flow 2 — Create Project

Login as PM
→ PM Workspace
→ Projects
→ Create Project
→ Select Project Type / Template
→ Configure Project
→ Add Project Owner
→ Add Members
→ Configure Structure
→ Create Project Plan
→ Submit Plan for Approval
→ Start Project

## Flow 3 — Project Member Executes Task

Login as Member
→ Member Workspace
→ Progress Task
→ View Assigned Tasks
→ Open Task
→ Execute Work
→ Update Progress
→ Add Evidence
→ Submit for Review (if required)
→ Reviewer Decision
→ Task Completed

## Flow 4 — PM Monitors Project

Login as PM
→ PM Workspace
→ Dashboard
→ Review Project Health
→ Open Project
→ Progress Task
→ Check Assignee Progress
→ Check Overdue / Blocked Tasks
→ Project Control
→ Identify Deviation
→ Follow-up / Reassign / Escalate
→ Review Updated Progress

## Flow 5 — Project Owner Monitors Outcome

Login as Project Owner
→ Owner Workspace
→ Dashboard
→ Select Project
→ Review Project Health
→ Review Milestones
→ Review Deliverables
→ Review Major Issues
→ Approve Decisions When Required

## Flow 6 — Management Portfolio Monitoring

Login as Management
→ Management Workspace
→ Portfolio Dashboard
→ Review Project Health
→ Identify Delayed Projects
→ Review Major Risks
→ Open Management Report
→ Make Strategic Decision

## Flow 7 — Change Request

PM / Authorized User
→ Project
→ Change Request
→ Submit Request
→ Impact Assessment
→ Approval
→ Approved / Rejected
→ Apply Approved Change
→ Create Baseline Revision if Required
→ Record Activity

---

# 28. UX Principles

SCOPE UI harus mengikuti prinsip:

1. Clean.
2. Simple.
3. Professional.
4. Management-friendly.
5. Information-dense without being overwhelming.
6. Easy to understand in less than 30 seconds.
7. Prioritize actionable information.
8. Consistent across role workspaces.

## 28.1 Avoid

- Too many colors.
- Too many summary cards.
- Overloaded dashboards.
- Unnecessary technical information for Management.
- Excessive tabs.
- Decorative charts without meaningful information.
- Duplicate navigation for the same function.
- Showing actions that users are not authorized to perform.

## 28.2 Role-Based UX

Setiap role harus mendapatkan tampilan yang sesuai tanggung jawabnya.

PM:
- Monitoring.
- Control.
- Exception handling.
- Follow-up.

Member:
- Execution.
- Progress update.
- Evidence.
- Review feedback.

Owner:
- Outcome.
- Milestones.
- Strategic decisions.
- Acceptance.

Management:
- Portfolio visibility.
- Project health.
- Reporting.
- Escalation.

---

# 29. MVP Scope

MVP harus fokus pada fondasi project management dan project control.

## Priority 1 — Core Foundation

- User Authentication.
- Role Management.
- Role-Based Workspace Switcher.
- Workspace Membership.
- Permission Management.
- Project Management.
- Project List.
- Project Detail.
- Project Template Basic.

## Priority 2 — Project Execution

- Project Structure.
- Phase Management.
- Work Package.
- Task Management.
- Task Assignment.
- Task Kanban.
- Progress Task.
- Task Status.
- Manual Progress Update.
- Task Comments.
- Basic Attachments.

## Priority 3 — Project Control

- Project Manager Dashboard.
- Project Owner Dashboard.
- Project Health.
- Planned Progress.
- Actual Progress.
- Weighted Progress.
- Progress Variance.
- Progress Snapshot.
- Timeline / Gantt.
- Milestone Management.
- Overdue Task Monitoring.
- Blocked Task Monitoring.

## Priority 4 — Governance

- Issue Management.
- Basic Risk Management.
- Approval Management.
- Baseline.
- Change Request Basic.
- Activity Log.

## Priority 5 — Reporting

- Project Executive Summary.
- Progress Report.
- Task Report.
- Basic Management Report.
- CSV / Excel Export.

---

# 30. Out of Scope for MVP

Tidak perlu membangun:

- Full Accounting.
- Full Budget Management.
- Payroll.
- Timesheet.
- Full CRM.
- Full Chat Application.
- Full Document Management System.
- Advanced Resource Forecasting.
- AI Project Prediction.
- Advanced Portfolio Simulation.
- Advanced Financial Forecasting.

Fokus MVP:

**PROJECT + STRUCTURE + TASK + PROGRESS + TIMELINE + CONTROL + REPORTING**

---

# 31. Acceptance Criteria

## 31.1 Role-Based Workspace

- User dapat login menggunakan satu akun.
- User dapat memiliki beberapa role.
- User hanya melihat role yang diberikan.
- User dapat berpindah role melalui sidebar.
- Navigasi berubah sesuai role aktif.
- Dashboard berubah sesuai role aktif.
- Permission berubah sesuai role context.
- Perpindahan role tidak mengubah identitas user.
- Aktivitas mencatat role yang sedang digunakan.

## 31.2 Project Management

- User dengan permission dapat membuat project.
- Project code harus unik dalam workspace.
- Project dapat menggunakan template.
- Project dapat memiliki owner dan PM.
- Project dapat memiliki lifecycle status dan health status terpisah.
- Project dapat diarsipkan.
- Perubahan penting tercatat dalam audit trail.

## 31.3 Project Structure

- PM dapat membuat phase.
- PM dapat membuat work package.
- PM dapat membuat task.
- Task dapat memiliki subtask.
- Task dapat dipindahkan dalam struktur yang diizinkan.
- Circular dependency ditolak.
- Struktur project dapat ditampilkan dalam tree view.

## 31.4 Task Management

- PM dapat membuat task.
- PM dapat menentukan assignee.
- PM dapat memonitor seluruh task dalam project.
- PM tidak menjadi assignee task.
- Member dapat melihat task yang ditugaskan.
- Member dapat memperbarui progress task miliknya.
- Member dapat melaporkan issue.
- Task dapat memiliki reviewer.
- Task yang membutuhkan approval harus melalui review workflow.

## 31.5 Progress Engine

- Task mendukung manual progress.
- Task mendukung status-based progress.
- Task mendukung subtask-based progress.
- Parent progress dihitung dari child weights.
- Project progress dihitung dari weighted leaf work items.
- Total sibling weight harus 100%.
- Planned progress berasal dari approved baseline.
- Actual progress berasal dari pekerjaan aktual.
- Variance dihitung dengan benar.
- Snapshot menyimpan histori progress.
- Baseline lama tetap dapat ditampilkan.

## 31.6 Timeline

- Project memiliki Gantt view.
- Task memiliki planned start dan end.
- Task dapat memiliki dependency.
- Milestone dapat ditampilkan pada timeline.
- Baseline dapat dibandingkan dengan current schedule.
- Task overdue dapat diidentifikasi.
- Schedule deviation dapat dihitung.

## 31.7 Issues & Risks

- PM dapat membuat issue.
- Issue dapat dihubungkan ke task.
- Blocked task harus memiliki reason.
- Risk memiliki probability dan impact.
- Risk memiliki owner dan mitigation plan.
- Risk dapat dikonversi menjadi issue.

## 31.8 Approval & Change Control

- Approval workflow dapat dikonfigurasi.
- Approval dapat dilakukan oleh user yang berwenang.
- Rejection harus memiliki reason.
- Approval history tersimpan.
- Major change membutuhkan Change Request.
- Rejected change tidak diterapkan.
- Approved baseline revision tidak menghapus baseline lama.

## 31.9 Reporting

- Dashboard menampilkan informasi sesuai role.
- PM dapat melihat project yang dikelola.
- Owner dapat melihat project yang dimiliki.
- Management dapat melihat portfolio sesuai permission.
- Planned vs Actual dapat ditampilkan.
- Historical progress dapat ditampilkan.
- Report dapat diexport sesuai permission.

---

# 32. Success Metrics

SCOPE dianggap berhasil apabila:

## Project Manager

PM dapat menjawab dalam waktu kurang dari satu menit:

1. Berapa progress project?
2. Planned vs Actual berapa?
3. Project ahead atau behind?
4. Task mana yang overdue?
5. Task mana yang blocked?
6. Siapa yang bertanggung jawab atas pekerjaan tersebut?
7. Milestone apa yang akan datang?
8. Apa issue terbesar?
9. Apa yang membutuhkan follow-up?

## Project Member

Member dapat:
- Menemukan task yang ditugaskan.
- Memahami pekerjaan yang harus dilakukan.
- Memperbarui progress dengan mudah.
- Mengirim hasil pekerjaan untuk review.
- Mengetahui feedback reviewer.

## Project Owner

Owner dapat:
- Mengetahui kondisi project.
- Melihat pencapaian milestone.
- Memantau deliverables.
- Mengetahui risiko dan keputusan yang diperlukan.

## Management

Management dapat:
- Memahami kondisi portfolio.
- Mengidentifikasi project delayed.
- Mengetahui major risks.
- Melihat performance project tanpa membuka task satu per satu.

---

# 33. Definition of Done — MVP

## Foundation

- [ ] User authentication.
- [ ] Multi-role user.
- [ ] Role-Based Workspace Switcher.
- [ ] Role-specific sidebar.
- [ ] Role-specific dashboard.
- [ ] Permission management.

## Project

- [ ] Create project.
- [ ] Edit project.
- [ ] Project list.
- [ ] Project detail.
- [ ] Project lifecycle.
- [ ] Project health.
- [ ] Project template basic.

## Structure & Task

- [ ] Create phase.
- [ ] Create work package.
- [ ] Create task.
- [ ] Assign task to member.
- [ ] Task Kanban.
- [ ] Task dependencies.
- [ ] Task comments.
- [ ] Task attachments.

## Progress

- [ ] Member can update task progress.
- [ ] PM can monitor all project tasks.
- [ ] Weighted progress.
- [ ] Planned progress.
- [ ] Actual progress.
- [ ] Progress variance.
- [ ] Progress snapshot.
- [ ] Progress chart.

## Timeline

- [ ] Gantt / Waterfall Timeline.
- [ ] Planned start and end.
- [ ] Actual start and end.
- [ ] Milestone.
- [ ] Dependency visualization.
- [ ] Baseline comparison.
- [ ] Overdue monitoring.

## Project Control

- [ ] PM Dashboard.
- [ ] Project Control view.
- [ ] Overdue tasks.
- [ ] Blocked tasks.
- [ ] Pending reviews.
- [ ] Issues.
- [ ] Basic risks.
- [ ] Activity log.

## Reporting

- [ ] Project Overview.
- [ ] Executive Summary.
- [ ] Progress Report.
- [ ] Task Report.
- [ ] Management Report.
- [ ] Export.

---

# 34. Final Product Concept

SCOPE bukan sekadar Task Management Application.

SCOPE adalah:

**PROJECT CONTROL CENTER**

Dengan empat domain utama:

## 1. Project Management

- Project.
- Structure.
- Phase.
- Work Package.
- Milestone.
- Template.

## 2. Project Execution

- Task.
- Assignment.
- Kanban.
- Progress Update.
- Deliverables.
- Evidence.

## 3. Project Control

- Planned vs Actual.
- Progress Variance.
- Timeline.
- Baseline.
- Issues.
- Risks.
- Change Control.

## 4. Project Governance & Reporting

- Approval.
- Decision Log.
- Activity Log.
- Executive Summary.
- Management Reports.
- Portfolio Visibility.

## Role-Based Experience

Seluruh domain tersebut diakses melalui workspace mode sesuai tanggung jawab pengguna:

- Project Manager — Monitor & Control.
- Project Member — Execute & Update.
- Project Owner — Own Outcomes & Decide.
- Management — Monitor Portfolio.
- Client — Review & Accept.
- Admin — Configure & Govern.

---

**Final Product Statement**

SCOPE is a centralized Project Control Center designed to manage diverse project types through a flexible project structure, measurable progress, timeline visibility, controlled execution, and role-based governance.

SCOPE connects project planning, work execution, project monitoring, and management reporting in one structured platform.
