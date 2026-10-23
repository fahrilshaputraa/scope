# Scope — Gap Analysis & Roadmap Implementasi

Status: draft untuk diskusi  
Tanggal: 22 Oktober 2026  
Sumber: audit kode `apps/`, `templates/`, `static/js/`, `tests/`, serta halaman produk ProjectManager.com (`/software`, `/software/gantt-chart`, `/pricing`).

Dokumen ini memakai ID gap (`A1`, `B3`, dst.) agar bisa dirujuk di diskusi, issue, dan commit. Urutan fase adalah urutan ketergantungan, bukan tanggal atau durasi. Estimasi waktu baru dibuat setelah scope tiap fase disetujui.

## Status implementasi — 22 Oktober 2026

Fase 0 dikerjakan bertahap. Status saat ini:

| Item | Status | Cakupan |
|---|---|---|
| E2 Arsip | Selesai | Project, task, issue, phase; cascade ke detail/phase; restore; riwayat aktivitas |
| E3 Pagination | Selesai untuk list utama | Project, catatan global, issue, aktivitas, issue project, catatan project, komentar task |
| E4 Search | Selesai | Project, task, issue, catatan, milestone, keputusan; halaman hasil dan saran navbar |
| E1 UI manajemen user | Selesai | Daftar + cari/filter, edit identitas & peran, aktif/nonaktif, reset kata sandi, buat akun lokal; khusus staff |
| E5 History/version restore | Selesai | Revision per field untuk project, task, milestone, issue, risk; diff before/after; restore oleh PM/staff dengan validasi |
| H1 Dead code Gantt | Selesai | Vendor Frappe Gantt, CSS, dan payload `gantt_tasks` dihapus |
| H4 Audit aksesibilitas/mobile | Belum | — |
| H6 Scheduler snapshot | Selesai | `--due` idempoten + scheduler internal opt-in + docs deployment |

Kanban dan visualisasi (timeline, laporan, roadmap) sengaja tidak dipaginate karena pagination akan memecah drag-and-drop dan konteks visual.

---

## 1. Ringkasan eksekutif

Scope sudah kuat di inti **project control**: progress berbobot berhierarki, kurva rencana vs aktual, variance otomatis, baseline, snapshot harian, timeline, Kanban, laporan, presentasi, share publik, dan impor rencana dari AI. Gap terbesar bukan di kedalaman progress, tetapi di **loop operasional harian, kapasitas tim, dan tata kelola**.

Lima temuan utama:

1. **Loop kolaborasi harian belum tertutup.** `ActivityEvent` mencatat 21 jenis aksi, tetapi tidak ada notifikasi, mention, watch, atau komentar di luar task. Orang tetap harus membuka aplikasi untuk tahu ada perubahan.
2. **Perencanaan belum punya view alternatif.** Belum ada Calendar, Sheet, critical path, task berulang, copy/template project, dan auto-shift dependensi. Gantt kita sudah punya baseline dan edit tanggal, tetapi belum menjadi alat penjadwalan penuh.
3. **Kapasitas dan waktu belum terukur.** Tidak ada time entry, timesheet, planned vs actual hours, workload, holiday/working days, atau skills. Akibatnya keterlambatan sulit dijelaskan sebagai masalah kapasitas.
4. **Portfolio masih datar.** Dashboard lintas project sudah ada, tetapi belum ada program/portfolio grouping, roadmap portfolio, custom columns, atau team summary.
5. **Fondasi operasional belum lengkap.** Belum ada pagination, soft delete/archive, UI manajemen user, history restore, API, dan scheduler internal untuk snapshot.

Rekomendasi: **enam rilis berurutan** dengan fokus tiga tema — *kepercayaan data*, *loop harian*, dan *kapasitas + portfolio*. Finance dan marketplace integration sengaja tidak dikejar.

Yang harus dijaga dan jangan dikorbankan saat menambah fitur:

- Progress berbobot Phase → Activity → Detail Activity tanpa double count.
- Planned vs actual dengan variance dan threshold yang konsisten.
- Baseline dan snapshot historis.
- Presentasi dari data project dan share link read-only.
- Impor rencana AI yang atomik dan idempoten.

---

## 2. Skala prioritas dan kompleksitas

**Prioritas**

| Kode | Arti | Keputusan |
|---|---|---|
| P0 | Kehilangan data, kebocoran akses, atau blocker operasional | Tidak ditemukan di audit ini |
| P1 | Wajib masuk roadmap; tanpa ini alur utama masih pincang | Dikerjakan di Fase 0–3 |
| P2 | Bernilai, tetapi bisa setelah fondasi dan loop harian stabil | Fase 4–5 |
| P3 | Ditunda atau di luar scope sampai kebutuhan berubah | Tidak dijadwalkan |

**Kompleksitas relatif**: Rendah, Sedang, Tinggi. Ini bukan estimasi waktu.

**Peran**: PM, Member, Management, Admin.

---

## 3. Baseline: kekuatan yang sudah ada

| Kemampuan | Bukti implementasi |
|---|---|
| Progress berbobot tanpa double count | `apps/work/progress.py:6`, `apps/work/models.py:236` |
| Planned curve, actual, variance, threshold | `apps/projects/services.py:16`, `:49`, `:56`, `:80` |
| Baseline capture dan deviasi jadwal | `apps/projects/services.py:304`, `apps/work/models.py:210` |
| Snapshot harian otomatis | `apps/projects/services.py:141`, `apps/projects/signals.py:14` |
| Timeline rencana vs actual, zoom, milestone, detail activity | `templates/projects/partials/_task_timeline.html`, `static/js/task-timeline.js` |
| Kanban drag, kolom kustom, feedback card | `static/js/board.js`, `apps/projects/models.py:382`, `:394` |
| Issue dan risk terpisah | `apps/work/models.py:265`, `apps/projects/models.py:338` |
| Laporan 6 dataset × CSV/XLSX/PDF | `apps/projects/exports.py:144` |
| Presentasi fullscreen dari data project | `apps/projects/presentation_views.py`, `static/js/presentation.js` |
| Share publik read-only dengan token | `apps/projects/share_views.py:40`, `:81` |
| Impor rencana AI atomik dan idempoten | `apps/projects/planning_io.py`, `apps/projects/planning_views.py` |
| Dokumentasi in-app 18 artikel + simulasi | `apps/identity/documentation.py` |
| RBAC 3 role dan scope per project | `apps/identity/permissions.py` |
| Test suite luas | `tests/test_workflows.py`, `test_activity_details.py`, `test_progress.py`, `test_public_project.py`, `test_planning_io.py`, `test_documentation.py`, `test_demo_commands.py` |

---

## 4. Inventory gap lengkap

### A. Perencanaan dan penjadwalan

| ID | Gap | ProjectManager.com | Kondisi Scope | Peran | Pri | Kompleks |
|---|---|---|---|---|---|---|
| A1 | Calendar view | Ada | Belum ada route, template, atau JS kalender | PM, Member | P1 | Sedang |
| A2 | Sheet / spreadsheet view | Ada | Hanya daftar task, belum grid editable | PM | P2 | Sedang |
| A3 | Critical path | Ada, filter otomatis | Dependensi tersimpan, tetapi tidak ada perhitungan critical path | PM, Management | P2 | Sedang |
| A4 | Empat tipe dependency + lintas project | Ada | Satu tipe (finish-to-start), dependency hanya dalam satu project | PM | P2 | Tinggi |
| A5 | Task berulang | Ada | Belum ada recurrence rule atau materialisasi instance | PM, Member | P1 | Sedang |
| A6 | Copy project dan template | Ada | Tidak ada copy, template, atau duplikasi project | PM | P1 | Sedang |
| A7 | Bulk edit dan multi-select | Ada sebagian | Aksi masih satu per satu | PM | P2 | Sedang |
| A8 | Working days dan holiday | Ada | Belum ada kalender kerja; durasi dan planned progress memakai hari kalender | PM, Management | P1 | Sedang |
| A9 | Approval task / workflow | Ada | Belum ada status approval atau aturan | PM | P2 | Tinggi |
| A10 | Print / export Gantt sebagai gambar | Ada | Cetak halaman ada, belum print Gantt khusus | PM, Management | P2 | Rendah |
| A11 | Custom field | Ada | Hanya label dan field tetap | PM | P2 | Tinggi |
| A12 | Auto-shift dependensi saat tanggal berubah | Ada | Tanggal dependency tidak ikut bergeser otomatis | PM | P2 | Tinggi |

### B. Eksekusi harian dan kolaborasi

| ID | Gap | ProjectManager.com | Kondisi Scope | Peran | Pri | Kompleks |
|---|---|---|---|---|---|---|
| B1 | Notification center in-app | Ada | Belum ada model, route, atau bell | Semua | P1 | Sedang |
| B2 | Email notification / digest | Ada | Belum ada pengiriman email | Semua | P1 | Sedang |
| B3 | Mention `@user` | Ada | Komentar task belum mendukung mention | Member, PM | P1 | Rendah |
| B4 | Komentar di issue, note, milestone, project | Ada di task dan dokumen | Hanya `TaskComment` | Member, PM | P1 | Sedang |
| B5 | Watch / follow project atau task | Ada | Tidak ada subscription | Semua | P1 | Sedang |
| B6 | My Tasks upgrade | My Summary | Ada halaman, belum ada due soon/overdue, grouping, filter lanjutan | Member | P1 | Rendah |
| B7 | Quick update dari daftar atau notifikasi | Ada | Update harus buka drawer/detail | Member | P2 | Rendah |
| B8 | Activity diff before/after | Task/project history | Activity hanya pesan teks, tanpa nilai lama/baru | PM, Management | P2 | Sedang |
| B9 | Realtime update | Ada | Tidak ada polling/websocket; refresh manual | Semua | P3 | Tinggi |

### C. Waktu dan kapasitas

| ID | Gap | ProjectManager.com | Kondisi Scope | Peran | Pri | Kompleks |
|---|---|---|---|---|---|---|
| C1 | Time entry per task | Ada | Belum ada pencatatan jam | Member, PM | P1 | Sedang |
| C2 | Timesheet mingguan + submit | Ada | Belum ada periode, submit, atau rekap | Member, PM | P1 | Sedang |
| C3 | Approval timesheet | Ada | Belum ada status approval | PM | P2 | Sedang |
| C4 | Planned hours vs actual hours | Ada | Task hanya punya bobot dan progress, belum jam | PM, Management | P1 | Sedang |
| C5 | Resource availability dan workload | Ada | Belum ada kapasitas user, alokasi, atau heatmap | PM, Management | P1 | Tinggi |
| C6 | Skills dan team assignment | Ada | `team` hanya CharField; tidak ada skill | PM | P2 | Sedang |

### D. Portfolio, risiko, dan pelaporan

| ID | Gap | ProjectManager.com | Kondisi Scope | Peran | Pri | Kompleks |
|---|---|---|---|---|---|---|
| D1 | Program / portfolio grouping | Ada | Project masih daftar datar | Management | P1 | Sedang |
| D2 | Portfolio roadmap | Ada | Ada peta waktu, belum roadmap yang bisa difilter per program | Management | P1 | Sedang |
| D3 | Custom columns di portfolio | Ada | Kolom tabel tetap | Management | P2 | Sedang |
| D4 | Team summary dashboard | Ada | Baru ada My Tasks | PM, Management | P2 | Sedang |
| D5 | Scheduled / email report | Ada | Export manual saja | Management | P2 | Sedang |
| D6 | Custom report builder | Ada | Enam dataset tetap | Management | P3 | Tinggi |
| D7 | Export Word / PPTX dan Gantt print | Word, Excel, PDF | CSV, XLSX, PDF | Management | P2 | Sedang |
| D8 | RAID log + risk matrix | Ada | Issue dan risk sudah terpisah, belum ada matriks atau kategori assumption/change | PM, Management | P2 | Rendah |

### E. Tata kelola dan administrasi

| ID | Gap | ProjectManager.com | Kondisi Scope | Peran | Pri | Kompleks |
|---|---|---|---|---|---|---|
| E1 | UI manajemen user | Ada | Hanya create user oleh staff; edit role/deactivate/reset belum ada | Admin | P1 | Sedang |
| E2 | Soft delete / archive project, task, issue, phase | Ada | Belum ada hapus atau arsip untuk entitas utama | Admin, PM | P1 | Sedang |
| E3 | Pagination | Ada | Issue dibatasi 100, note global 50, activity tanpa paging | Semua | P1 | Rendah |
| E4 | Search coverage | Global | Hanya project dan task | Semua | P1 | Rendah |
| E5 | History / version restore | Ada | Activity log dan snapshot ada, tetapi tidak bisa revert | PM, Admin | P1 | Tinggi |
| E6 | Audit log UI | Ada | Belum ada halaman audit tingkat akun | Admin | P2 | Sedang |
| E7 | Custom role per project | Ada | Tiga role global + membership project | Admin, PM | P2 | Tinggi |
| E8 | MFA | Ada | Belum ada | Admin | P2 | Sedang |
| E9 | Account data export | Ada | Belum ada | Admin | P2 | Rendah |
| E10 | SAML SSO | Ada | Sudah ada Entra ID OIDC; SAML belum | Admin | P3 | Sedang |

### F. Platform dan integrasi

| ID | Gap | ProjectManager.com | Kondisi Scope | Peran | Pri | Kompleks |
|---|---|---|---|---|---|---|
| F1 | REST API + token | Ada | Belum ada API publik | Integrasi | P2 | Tinggi |
| F2 | Webhook | Ada via API/automation | Belum ada | Integrasi | P2 | Sedang |
| F3 | Slack / Teams notification | Ada | Belum ada | Semua | P2 | Sedang |
| F4 | Google / Microsoft Calendar sync | Ada | Belum ada; ICS feed belum ada | PM, Member | P2 | Tinggi |
| F5 | Import Excel / CSV / MPP | Ada | Hanya JSON rencana dari AI | PM | P2 | Sedang |
| F6 | PWA / mobile | Native iOS & Android | Web responsive, belum PWA | Member | P2 | Sedang |
| F7 | Jira / Azure DevOps sync | Ada | Belum ada | Integrasi | P3 | Tinggi |
| F8 | Power BI / BI export | Ada | Belum ada | Management | P3 | Tinggi |

### G. Finance — sengaja di luar scope

| ID | Gap | ProjectManager.com | Keputusan |
|---|---|---|---|
| G1 | Budget dan expense | Ada | P3; beda domain, bukan kebutuhan inti project control |
| G2 | Labor rate dan cost | Ada | P3; hanya jika C1–C5 sudah stabil |
| G3 | QuickBooks Online | Ada | P3; tidak dikejar |

### H. Technical debt dan kualitas

| ID | Gap | Kondisi | Pri | Kompleks |
|---|---|---|---|---|
| H1 | Dead code Frappe Gantt dan payload `gantt_tasks` | Vendor Gantt tidak dipakai; payload tanpa konsumen (`services.py:284`) | P1 | Rendah |
| H2 | Fondasi notifikasi | Belum ada service fan-out, preference, atau dedupe | P1 | Sedang |
| H3 | Index dan performa portfolio/activity | Query lintas project dan activity feed tumbuh tanpa index khusus | P2 | Sedang |
| H4 | Audit aksesibilitas dan mobile | Sudah ada aria dan focus trap, belum audit menyeluruh | P1 | Rendah |
| H5 | Test untuk modul baru | Test lama kuat, belum mencakup fitur baru | Melekat | — |
| H6 | Scheduler snapshot internal | Snapshot harian bergantung cron eksternal | P1 | Rendah |
| H7 | Empty/error state dan konsistensi list | Belum seragam di semua halaman | P2 | Rendah |

---

## 5. Matriks prioritas

|  | Kompleksitas rendah–sedang | Kompleksitas tinggi |
|---|---|---|
| **Nilai tinggi** | B1, B2, B3, B4, B5, B6, C1, C2, C4, E1, E2, E3, E4, H1, H4, H6 | C5, E5, E7, F1, A4, A12 |
| **Nilai menengah** | A1, A5, A6, A8, A10, B7, B8, D1, D2, D8, F2, F3, F5, F6 | A3, A9, A11, D6, F4, F7, F8 |
| **Nilai rendah / ditunda** | E9, H7 | G1, G2, G3, E10 |

Prinsip eksekusi:

1. **Selesaikan fondasi data sebelum fitur yang bergantung padanya.** Pagination, soft delete, user management, dan history adalah prasyarat tidak langsung untuk notifikasi, timesheet, dan API.
2. **Loop harian sebelum perencanaan baru.** Notifikasi dan mention memberi nilai lebih cepat daripada Calendar.
3. **Jangan menambah dashboard sebelum ada data kapasitas.** Team summary dan workload baru bermakna setelah C1–C5.
4. **Satu fase, satu tema.** Jangan campur fitur kolaborasi dengan perubahan model jadwal dalam satu rilis.

---

## 6. Roadmap implementasi

### Fase 0 — Fondasi data dan operasional

**Tujuan**: membuat data aman, bisa dicari, bisa dipulihkan, dan UI tidak melambat sebelum fitur baru ditambah.

**Deliverable**

- E1 UI manajemen user: edit role, deactivate/reactivate, reset password oleh staff.
- E2 Soft delete/archive untuk project, task, issue, phase, dengan restore dan filter "arsip".
- E3 Pagination seragam untuk issue, note, activity, komentar, dan task list.
- E4 Search mencakup project, task, issue, note, milestone, decision.
- E5 History: simpan perubahan field important + tampilan diff + restore.
- H1 Hapus kode Frappe Gantt dan payload `gantt_tasks` yang tidak dipakai.
- H6 Scheduler snapshot internal atau dokumentasi deployment yang tidak bergantung cron manual.
- H4 Audit aksesibilitas dan mobile untuk alur utama.

**Prasyarat**: tidak ada.

**Acceptance criteria**

- Semua daftar panjang punya pagination dan mempertahankan filter di URL.
- Entitas yang diarsipkan hilang dari daftar, ekspor, dan pencarian; bisa dipulihkan oleh Admin/PM.
- Pencarian mengembalikan enam jenis entitas dengan scope izin yang sama seperti halaman aslinya.
- Perubahan jadwal, progress, status, dan penugasan punya diff dan bisa direstore.
- Test regresi lama tetap lulus; test baru mencakup arsip, restore, pagination, dan search.

**Risiko**

- History bisa membengkak; perlu strategi retensi dan hanya field yang relevan.
- Soft delete mengubah semua query; harus lewat manager default agar tidak ada data bocor.

---

### Fase 1 — Loop eksekusi harian

**Tujuan**: orang tahu apa yang berubah dan bisa merespons tanpa meninggalkan aplikasi.

**Deliverable**

- B1 Notification center in-app dengan read/unread dan deep link.
- B2 Email notification dan digest harian/mingguan, opt-in per user.
- B3 Mention `@user` di komentar dengan autocomplete dan validasi akses.
- B4 Komentar di issue, note, milestone, dan project.
- B5 Watch/follow project atau task.
- B6 My Tasks: due soon, overdue, grouping per project/status, filter.
- B7 Quick update status/progress dari daftar.
- B8 Activity diff before/after.
- H2 Service notifikasi: resolver penerima, preference, dedupe, dan template.

**Prasyarat**: Fase 0 (E1, E4, E5).

**Acceptance criteria**

- Assignment, mention, komentar, perubahan status, perubahan tanggal, issue baru, dan milestone selesai menghasilkan notifikasi tepat satu kali.
- Penerima hanya user yang punya akses ke project; management read-only tidak menerima notifikasi aksi yang tidak boleh dilakukannya.
- Email bisa dimatikan per user; digest tidak mengirim duplikat.
- Mention yang tidak valid atau user tanpa akses ditolak dengan pesan jelas.
- Komentar di issue/note tidak mengubah progress atau status.

**Risiko**

- Fan-out notifikasi bisa membanjiri; perlu dedupe dan preferensi per jenis.
- Mention dan komentar memperluas permukaan izin; test kebocoran data wajib.

---

### Fase 2 — Jadwal dan perencanaan

**Tujuan**: menjadikan timeline alat kerja, bukan hanya visualisasi.

**Deliverable**

- A1 Calendar view (bulan, minggu, hari) dengan filter project/assignee dan drag reschedule.
- A8 Working days dan holiday, dipakai durasi, planned progress, dan critical path.
- A5 Task berulang dengan recurrence rule dan materialisasi instance berikutnya.
- A6 Copy project dan template project.
- A3 Critical path.
- A4 Empat tipe dependency dan dependency lintas project.
- A12 Auto-shift dependensi saat tanggal berubah.
- A7 Bulk edit task.
- A10 Print/export Gantt.

**Prasyarat**: Fase 0 (E2, E5), Fase 1 (B1 untuk notifikasi perubahan jadwal).

**Acceptance criteria**

- Calendar menampilkan task dan milestone, menghormati izin, dan menyimpan perubahan tanggal.
- Durasi dan planned progress menghitung hari kerja serta holiday; hasilnya konsisten dengan timeline dan laporan.
- Task berulang menghasilkan instance berikutnya tanpa duplikasi saat disimpan berulang.
- Copy project menyalin phase, milestone, task, dependency, dan kolom board; tidak menyalin komentar, lampiran, activity, atau snapshot.
- Critical path menyorot rantai terpanjang dan tidak error pada DAG dengan cabang.
- Perubahan tanggal pada task yang punya dependensi menggeser task turunan sesuai aturan.
- Bulk edit memvalidasi izin dan dependency per task.

**Risiko**

- Recurrence dan auto-shift bisa membuat loop tak terbatas; wajib ada guard dan batas materialisasi.
- Holiday dan working days mengubah angka historis jika tidak dibekukan di baseline.

---

### Fase 3 — Waktu dan kapasitas

**Tujuan**: membuat keterlambatan bisa dijelaskan sebagai kekurangan kapasitas, bukan opini.

**Deliverable**

- C1 Time entry per task (tanggal, jam, catatan).
- C2 Timesheet mingguan, submit, dan rekap.
- C3 Approval timesheet oleh PM.
- C4 Planned hours vs actual hours per task dan project.
- C5 Resource availability, alokasi, dan workload heatmap.
- C6 Skills dan team assignment.
- D4 Team summary dashboard.

**Prasyarat**: Fase 0 (E1, E3), Fase 2 (A8 working days).

**Acceptance criteria**

- Time entry unik per user/task/tanggal, bisa dikoreksi sebelum submit.
- Timesheet mengunci entri setelah submit; approval/reject tercatat di activity log.
- Planned vs actual hours dihitung per project dan per orang tanpa double count.
- Workload memakai kapasitas mingguan dikurangi holiday dan menandai over-alokasi.
- Member hanya melihat dan mengubah time entry miliknya; PM melihat project yang dikelolanya.

**Risiko**

- Timesheet menambah beban administratif; desain input harus sangat cepat dan opsional per project.
- Jangan mencampur hours dengan bobot progress agar rumus progress yang sudah stabil tidak berubah.

---

### Fase 4 — Portfolio dan management reporting

**Tujuan**: management bisa membaca portofolio dan kapasitas lintas project tanpa membuka satu per satu.

**Deliverable**

- D1 Program/portfolio grouping.
- D2 Portfolio roadmap.
- D3 Custom columns di tabel portfolio.
- D5 Scheduled/email report.
- D7 Export Word/PPTX dan Gantt print.
- D8 RAID log dan risk matrix.

**Prasyarat**: Fase 0 (E3, E5), Fase 3 (C4, C5 untuk kolom kapasitas).

**Acceptance criteria**

- Project bisa dimasukkan ke program; filter program berlaku di dashboard, roadmap, dan laporan.
- Roadmap menampilkan rentang project dan milestone pada satu sumbu waktu.
- Custom column tersimpan per user atau per organisasi dan tidak merusak tampilan default.
- Scheduled report mengirim file yang sama dengan ekspor manual dan menghormati izin penerima.
- Risk matrix memakai severity dan likelihood yang eksplisit; issue tetap terpisah dari risk.

**Risiko**

- Portfolio grouping bisa tumpang tindih dengan `team`; putuskan satu model sebelum migrasi.
- Scheduled report butuh antrean/worker; jangan bergantung pada request cycle.

---

### Fase 5 — Tata kelola dan platform

**Tujuan**: membuka akses terkontrol untuk integrasi dan kebutuhan enterprise tanpa mengorbankan izin.

**Deliverable**

- E6 Audit log UI.
- E7 Custom role per project.
- E8 MFA.
- E9 Account data export.
- F1 REST API + token.
- F2 Webhook.
- F3 Slack/Teams notification.
- F4 Google/Microsoft Calendar sync atau ICS feed.
- F5 Import Excel/CSV/MPP.
- F6 PWA.

**Prasyarat**: Fase 0 (E1, E5), Fase 1 (H2), Fase 3 (C1–C5).

**Acceptance criteria**

- Audit log menampilkan aktor, aksi, objek, waktu, dan perubahan penting; hanya Admin.
- Custom role bisa membatasi baca/tulis per project tanpa mengubah role global.
- API memakai token per user, scope izin sama dengan UI, dan punya dokumentasi OpenAPI.
- Webhook menandatangani payload dan punya retry dengan backoff.
- ICS feed hanya membawa task yang boleh dilihat pemilik feed.
- PWA bisa dibuka offline untuk data yang sudah dimuat dan tidak menyimpan data sensitif di cache publik.

**Risiko**

- API dan custom role memperbesar permukaan keamanan; butuh test otorisasi per endpoint.
- Calendar sync dua arah berisiko konflik; mulai dari ICS read-only.

---

## 7. Catatan arsitektur per fitur

### 7.1 Notifikasi (B1, B2, B8, H2)

- Model `Notification`: recipient, actor, verb, target (project/task/issue/note), url, `read_at`, `dedupe_key`, `created_at`.
- Service `notify(actor, verb, target, recipients)` dipanggil dari `record_activity` atau signal yang sudah ada, bukan dari setiap view.
- Resolver penerima: assignee, collaborator, watcher, manager, dan mention. Selalu filter lewat `visible_projects`.
- Preference per user per jenis (in-app, email, digest).
- Email digest lewat management command terjadwal; jangan kirim email sinkron di request.
- Dedupe memakai `dedupe_key` (mis. `task:12:status:in_progress:2026-10-22`) agar simpan berulang tidak menghasilkan notifikasi ganda.
- Activity diff disimpan sebagai JSON `changes` pada `ActivityEvent` atau tabel revision; UI menampilkan nilai lama → baru.

### 7.2 Komentar dan mention (B3, B4)

- Generalisasi `TaskComment` menjadi `Comment` dengan `content_type`/`object_id` dan migrasi data lama.
- Mention disimpan sebagai relasi `mentioned_users` agar tidak perlu parsing ulang saat render.
- Validasi mention: user aktif dan punya akses ke project.
- Rich text tetap memakai sanitasi `nh3` yang sudah ada (`apps/richtext.py:30`).

### 7.3 Watch/follow (B5)

- `Subscription(user, content_type, object_id)` unik.
- Auto-subscribe assignee, collaborator, dan pembuat komentar; opt-out tetap tersedia.
- Watch project berarti menerima notifikasi milestone, issue, dan perubahan jadwal.

### 7.4 Calendar (A1)

- View baru memakai queryset task yang sama dengan timeline dan board.
- URL state: `?view=month|week|day&date=YYYY-MM-DD&project=&assignee=`.
- Drag reschedule memakai endpoint `task_dates` yang sudah ada; validasi dependency dan izin tetap di server.
- Holiday ditampilkan sebagai overlay, bukan menghapus task.

### 7.5 Working days dan holiday (A8)

- Model `Holiday(date, name, scope)` dengan scope global atau project.
- Utility `working_days_between(start, end, project)` dipakai timeline, planned progress, critical path, dan workload.
- Simpan snapshot hasil perhitungan di baseline agar angka historis tidak berubah saat holiday ditambah belakangan.

### 7.6 Task berulang (A5)

- `RecurrenceRule(freq, interval, weekdays, until, count, next_run)` pada task.
- Materialisasi instance berikutnya saat task selesai, bukan saat dibuat, agar tidak membuat deret tak terbatas.
- `recurrence_parent` menautkan instance; idempotency key mencegah duplikasi saat save berulang.
- Tampilkan penanda seri dan aksi "hentikan seri".

### 7.7 Copy project dan template (A6)

- Service `copy_project(source, actor, options)` dalam satu transaksi.
- Copy: phase, milestone, task, dependency, board column, weight, baseline opsional.
- Tidak copy: komentar, lampiran, activity, snapshot, time entry, share token.
- Opsi reset tanggal, progress, status, dan assignee.
- Template adalah project dengan flag `is_template`; hanya PM/staff yang bisa membuat project dari template.

### 7.8 Critical path dan dependency (A3, A4, A12)

- Critical path dihitung dari DAG dependency dengan durasi hari kerja; simpan hasil sebagai flag sementara atau hitung saat request dengan cache.
- Empat tipe dependency perlu field `dependency_type` pada relasi; validasi siklus tetap wajib.
- Auto-shift hanya menggeser task turunan yang belum selesai dan tidak boleh melanggar dependency lain.
- Tampilkan alasan pergeseran di activity log.

### 7.9 Time entry dan timesheet (C1–C4)

- `TimeEntry(user, task, date, hours, note)` unik per user/task/tanggal.
- `Timesheet(user, week_start, status, submitted_at, approved_by)` dengan status draft/submitted/approved/rejected.
- Hours tidak mengubah progress; keduanya metrik terpisah agar rumus progress tetap stabil.
- Rekap project = sum hours pada task yang terlihat; rekap orang = sum hours per minggu.
- Approval tercatat di activity log dan notifikasi.

### 7.10 Resource dan workload (C5, C6)

- `UserCapacity(user, weekly_hours, effective_from)`.
- Alokasi dihitung dari rentang task dan planned hours; holiday mengurangi kapasitas.
- Heatmap per minggu: under, normal, over.
- Skills sebagai M2M `Skill` pada user dan task; dipakai untuk filter penugasan, bukan otomatis menugaskan.

### 7.11 Portfolio dan program (D1–D3)

- `Program(name, code, owner, projects M2M)`; satu project satu program pada tahap awal.
- Roadmap memakai ulang geometri timeline; filter program dan status.
- Custom column disimpan sebagai konfigurasi JSON per user, dengan daftar kolom yang diizinkan.

### 7.12 History dan restore (E5)

- Pilihan: `django-simple-history` atau tabel revision sendiri. Rekomendasi awal: tabel `Revision` dengan JSON diff untuk Project, Task, Milestone, Issue, dan Risk.
- Restore menyalin field yang dipilih, bukan mengganti seluruh baris, lalu mencatat activity baru.
- Jangan menyimpan data sensitif di diff yang bisa dibaca role lebih rendah.

### 7.13 Soft delete (E2)

- Field `deleted_at` dan `deleted_by`; manager default mengecualikan arsip.
- Restore hanya Admin/PM pengelola.
- Ekspor, pencarian, notifikasi, dan API wajib memakai manager yang sama.

### 7.14 Search (E4)

- Service tunggal `search(query, user)` untuk project, task, issue, note, milestone, decision.
- Tahap awal `icontains`; pertimbangkan PostgreSQL full-text saat volume naik.
- Snippet dan skor sederhana; hasil selalu difilter `visible_projects`.

### 7.15 API dan webhook (F1, F2)

- Django REST Framework atau django-ninja; token per user; read-first.
- Serializer dan queryset memakai aturan izin yang sama dengan UI.
- Webhook: payload bertanda tangan, retry dengan backoff, event minimal (task.created, task.updated, project.updated, issue.created).
- Dokumentasi OpenAPI wajib.

### 7.16 PWA (F6)

- Manifest dan service worker; cache shell dan aset, bukan data project sensitif.
- Mulai dari read-only offline; write offline ditunda sampai ada strategi konflik.

---

## 8. Dampak data dan migrasi

Tabel baru yang diperkirakan:

- `Notification`, `NotificationPreference`, `Subscription`.
- `Comment` (generalisasi `TaskComment`), `Mention`.
- `Holiday`, `WorkingDayConfig`, `RecurrenceRule`.
- `TimeEntry`, `Timesheet`.
- `UserCapacity`, `Skill`, `TaskSkill`.
- `Program`, `PortfolioColumnConfig`.
- `Revision`.
- `ApiToken`, `WebhookEndpoint`, `WebhookDelivery`.
- Field baru: `deleted_at`, `deleted_by`, `dependency_type`, `planned_hours`, `likelihood` pada Risk, `is_template` pada Project.

Prinsip migrasi:

- Semua migrasi harus reversible; tidak ada drop kolom atau tabel lama di fase yang sama dengan pengenalan fitur.
- Backfill default aman: working days Senin–Jumat, holiday kosong, notifikasi in-app aktif, email opt-in.
- Migrasi `TaskComment` → `Comment` dilakukan dengan copy data dan verifikasi jumlah, bukan rename langsung.
- SQLite dan PostgreSQL harus sama-sama diuji; JSONField dan index perlu pengecekan khusus.
- Halaman publik dan share token tidak boleh ikut menampilkan data baru yang sensitif (time entry, komentar internal, audit).

---

## 9. Metrik keberhasilan

| Metrik | Target | Cara ukur |
|---|---|---|
| Aksi rutin selesai di dalam aplikasi | ≥ 90% tanpa email/chat | Observasi penggunaan dan survey singkat |
| Notifikasi dibaca | ≥ 80% dalam 1 hari kerja | `read_at` |
| Kepatuhan timesheet | ≥ 90% submitted tepat waktu | Status timesheet |
| Waktu menyusun laporan management | < 1 menit | Uji tugas, bukan klaim |
| Task overdue terdeteksi | 100% muncul di My Tasks dan dashboard | Test + data demo |
| Kebocoran akses | 0 | Test otorisasi per role dan per project |
| Performa halaman | Tidak lebih lambat dari baseline | Ukur sebelum/sesudah di data demo |

---

## 10. Keputusan yang perlu diambil sebelum Fase 1

1. **Time tracking dan budget**: apakah C1–C5 memang dibutuhkan, atau cukup planned hours tanpa timesheet? Jika tidak, Fase 3 bisa dipersempit.
2. **Channel notifikasi**: in-app saja, in-app + email, atau tambah Slack/Teams lebih awal?
3. **Portfolio grouping**: model `Program` atau cukup tag/kategori pada project?
4. **Approval**: perlu approval task, timesheet, atau keduanya?
5. **API**: ada konsumen nyata (aplikasi internal, BI, otomasi) atau ini spekulatif?
6. **Mobile**: PWA cukup, atau perlu aplikasi native?
7. **History**: `django-simple-history` atau revision diff sendiri?
8. **Custom role**: kebutuhan nyata atau bisa ditunda?
9. **Fase pertama**: apakah Fase 0 (fondasi) disetujui lebih dulu, atau ada kebutuhan mendesak yang harus didahulukan?

---

## 11. Yang sengaja tidak dikerjakan

- Budget, expense, labor rate, dan QuickBooks (G1–G3).
- Marketplace integrasi Jira, Azure DevOps, Power BI, Trello, Acumatica (F7, F8).
- Aplikasi mobile native.
- Custom domain.
- SAML SSO selama Entra ID OIDC mencukupi.
- AI prediction atau insight otomatis; fokus AI tetap pada penyusunan rencana.

---

## Lampiran A — Status fitur ProjectManager.com

| Fitur | Status Scope | Gap |
|---|---|---|
| Projects | Setara | — |
| Task list | Setara | — |
| Gantt chart | Sebagian | A3, A4, A12 |
| Sheet | Belum | A2 |
| Kanban board | Setara | — |
| Calendar | Belum | A1 |
| Project dashboard | Setara | — |
| Imports and exports | Sebagian | F5 |
| Gantt print | Belum | A10 |
| File storage | Sebagian | Lampiran hanya level task |
| Copy projects | Belum | A6 |
| Recurring tasks | Belum | A5 |
| Project baselines | Setara | — |
| Critical path | Belum | A3 |
| Dependencies | Sebagian | A4, A12 |
| Mobile app | Belum | F6 |
| Featured templates | Belum | A6 |
| My Summary | Sebagian | B6 |
| Expenses and budgeting | Belum | G1 |
| RAID log | Sebagian | D8 |
| Workflow automation | Belum | A9 |
| Custom templates | Belum | A6 |
| Approvals | Belum | A9, C3 |
| Team management | Sebagian | E1, C6 |
| Guest licenses | Setara | — |
| Comments | Sebagian | B3, B4 |
| File attachments | Setara | — |
| Document management | Belum | B4, F5 |
| Alerts and notifications | Belum | B1, B2 |
| Meetings | Belum | B4 |
| Team Summary | Belum | D4 |
| Assign teams and skills | Sebagian | C6 |
| Resource management | Belum | C5 |
| Planned hours | Belum | C4 |
| Holidays | Belum | A8 |
| Planned cost | Belum | G2 |
| Labor rates | Belum | G2 |
| Time tracking | Belum | C1 |
| Timesheets | Belum | C2, C3 |
| Real-time availability | Belum | C5 |
| Workload | Belum | C5 |
| Custom roles | Belum | E7 |
| Portfolio management | Sebagian | D1, D2 |
| Projects overview custom columns | Belum | D3 |
| Reports | Setara | D5, D7 |
| Project groups | Belum | D1 |
| Portfolio dashboard | Sebagian | D2 |
| Portfolio roadmap | Belum | D2 |
| Portfolio status report | Sebagian | D5 |
| Portfolio summary dashboard | Belum | D4 |
| Integrations | Belum | F2, F3, F4, F7, F8 |
| API | Belum | F1 |
| QuickBooks | Belum | G3 |
| Jira / Azure DevOps | Belum | F7 |
| Power BI | Belum | F8 |
| Teams / Slack | Belum | F3 |
| Excel import | Belum | F5 |
| Project security | Sebagian | E7 |
| Password policy | Sebagian | E8 |
| Global admin | Sebagian | E1 |
| SSO Google / Microsoft | Sebagian | Entra ID sudah ada |
| MFA | Belum | E8 |
| Version control | Belum | E5 |
| Task and project history | Sebagian | B8, E5 |
| SAML SSO | Belum | E10 |
| Audit log | Belum | E6 |
| Account data export | Belum | E9 |
| Custom domain | Belum | Tidak dijadwalkan |
| AI insights | Berbeda | Scope memakai AI untuk menyusun rencana, bukan insight prediktif |

---

## Lampiran B — Peta bukti kode

| Area | File kunci |
|---|---|
| Model project, risk, program terkait | `apps/projects/models.py` |
| Model task, issue, komentar, lampiran | `apps/work/models.py` |
| Progress dan variance | `apps/work/progress.py`, `apps/projects/services.py` |
| Timeline dan chart | `templates/projects/partials/_task_timeline.html`, `_progress_chart.html`, `static/js/task-timeline.js` |
| Kanban | `static/js/board.js`, `templates/projects/project/tasks.html` |
| Ekspor | `apps/projects/exports.py` |
| Presentasi | `apps/projects/presentation_views.py`, `static/js/presentation.js` |
| Share publik | `apps/projects/share_views.py` |
| Impor AI | `apps/projects/planning_io.py`, `apps/projects/planning_views.py` |
| Izin | `apps/identity/permissions.py` |
| Dokumentasi | `apps/identity/documentation.py` |
| Test | `tests/` |

---

## Lampiran C — Urutan eksekusi ringkas

| Fase | Tema | Gap utama |
|---|---|---|
| 0 | Fondasi data dan operasional | E1–E5, H1, H4, H6 |
| 1 | Loop eksekusi harian | B1–B8, H2 |
| 2 | Jadwal dan perencanaan | A1, A3–A8, A10, A12 |
| 3 | Waktu dan kapasitas | C1–C6, D4 |
| 4 | Portfolio dan management reporting | D1–D3, D5, D7, D8 |
| 5 | Tata kelola dan platform | E6–E9, F1–F6 |
