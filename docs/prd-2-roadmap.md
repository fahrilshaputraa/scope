# Scope — Roadmap Implementasi PRD 2.0

Status: draft untuk diskusi
Sumber: `PRD.md` v2.0 dibandingkan dengan kode `apps/`, `templates/`, `tests/`.

Urutan fase adalah urutan ketergantungan, bukan tanggal. Estimasi waktu dibuat setelah scope tiap fase disetujui. ID `R*` dipakai untuk rujukan di issue dan commit. Roadmap lama (`docs/gap-analysis-roadmap.md`) mengacu ke PRD sebelumnya; item yang sudah selesai di sana tetap dipakai sebagai fondasi.

## Keputusan yang harus diambil sebelum Fase 1

| # | Pertanyaan | Rekomendasi |
|---|---|---|
| D1 | Migrasi akun lama (satu `UserProfile.role`) | Satu `Membership` per user di workspace default. `management`→Management, `pm`→PM, `member`→Member. |
| D2 | `is_staff` Django | Dipetakan ke role Admin saat migrasi. `is_staff` tetap untuk Django admin. |
| D3 | Apakah multi-workspace dipakai sekarang | Model `Workspace` dibuat, UI hanya satu workspace default. Jangan bangun switcher antar-workspace dulu. |
| D4 | Project lama tanpa Owner | Owner kosong diizinkan untuk data lama, wajib untuk project baru. |
| D5 | PM yang sekarang mengerjakan task | Task lama dibiarkan, tetapi assignment baru ke PM ditolak. Sediakan laporan task PM yang perlu dialihkan. |

## Ringkasan fase

| Fase | Tema | Bergantung pada |
|---|---|---|
| 1 | Identitas, role, permission | — |
| 2 | Role switcher dan navigasi per role | 1 |
| 3 | Lifecycle, health, aturan task | 1 |
| 4 | Progress Task, Project Control, Project Owner | 2, 3 |
| 5 | Baseline berversi, approval, review | 3 |
| 6 | Change Request, Deliverable | 5 |
| 7 | Risk, struktur, template | 3 |
| 8 | Dashboard, report, audit per role | 2, 5, 7 |

---

## Fase 1 — Identitas, role, permission

Status (3 November 2026): R1.1–R1.5 selesai, kecuali pemilih role di UI (Fase 2). Rincian:
- R1.1: `Workspace`, `RoleDefinition`, `Membership`; 6 akun lama dimigrasi (role lama jadi membership, `is_staff` jadi Admin). Kolom `UserProfile.role` dihapus.
- R1.2: matriks permission default ada di `apps/identity/permission_catalog.py` dan disimpan di `RoleDefinition.permissions`.
- R1.3: `Project.owner` (wajib di form untuk project baru) dan `ProjectMembership` (menggantikan tabel anggota lama, `project.members` tetap bisa dipakai).
- R1.4: `permissions.py` membaca permission role aktif; nama fungsi lama dipertahankan.
- R1.5: `ActivityEvent.active_role` dan `Revision.active_role`.
Perilaku yang sengaja belum berubah: PM masih boleh mengubah progress task (R3.4), dan role aktif bawaan adalah role paling berwenang sampai switcher ada. Owner project yang dipilih di form berasal dari user ber-role Owner atau staff.

Tujuan: satu akun, banyak role, permission berbasis aksi. Semua fase lain bergantung pada ini.

| ID | Item | Cakupan | Selesai bila |
|---|---|---|---|
| R1.1 | Model `Workspace`, `Role`, `Membership` | Role: Admin, PM, Member, Owner, Client, Management. `Membership(user, workspace, role, status, assigned_by)`. User boleh punya banyak membership. | Migrasi D1/D2 jalan dua arah; tidak ada user yang kehilangan akses. |
| R1.2 | Katalog permission | Kode `project.view`, `task.update_progress`, `task.approve`, dst. (PRD 25.1) dan matriks default per role di data, bukan hardcode. | Matriks PRD bagian 25 terwakili; tes per sel matriks. |
| R1.3 | Project Owner dan `ProjectMembership` | `Project.owner`; `ProjectMembership(project, user, project_role)` menggantikan `Project.members`. | Owner wajib untuk project baru (D4); member lama termigrasi. |
| R1.4 | Ganti `permissions.py` | Fungsi `can_*` dan `visible_projects` membaca permission + keanggotaan project, dengan role aktif sebagai konteks. | Semua view lama memakai API baru; tes lama tetap hijau. |
| R1.5 | Catat role aktif | `ActivityEvent` dan `Revision` menyimpan `active_role`. | BR-ROLE-008 terpenuhi di semua jalur tulis. |

Risiko: `visible_projects` dipakai di halaman, export, komentar, dan download. Ubah di satu tempat, lalu jalankan seluruh suite.

## Fase 2 — Role switcher dan navigasi per role

Status (3 November 2026): R2.1–R2.4 selesai.
- R2.1: role aktif disimpan di sesi dan divalidasi terhadap `Membership`; role yang tidak dimiliki ditolak.
- R2.2: pemilih role di sidebar (hanya muncul bila user punya lebih dari satu role), tanpa login ulang; setelah ganti role user diarahkan ke Dashboard.
- R2.3: sidebar per role dari `apps/identity/navigation.py`. Hanya halaman yang sudah ada yang tampil; Progress Task, Project Control, Approvals, Deliverables, dan Templates menyusul di fase terkait. Penyimpangan dari PRD 6.1: PM, Member, Owner, dan Admin tetap punya menu Project agar halaman yang sudah ada tetap terjangkau, dan PM masih punya "Pekerjaan saya" sampai R3.4.
- R2.4: role Client hanya melihat project yang dibagikan dan tidak dapat membuka catatan, issue, aktivitas, atau riwayat (permission `project.view_internal`). Halaman baru Role & permission (khusus Admin) mengatur matriks permission; Admin selalu memiliki semuanya. Halaman Pengguna dan Role & permission mengikuti permission `user.manage` pada role aktif, bukan `is_staff` semata.
Belum dikerjakan: dashboard berbeda per role (R8.1), Templates dan Audit Logs di sidebar Admin (R7.5, R8.4). Update 8 November 2026: ketiganya selesai.

| ID | Item | Cakupan | Selesai bila |
|---|---|---|---|
| R2.1 | Role aktif di sesi | Middleware menyimpan role aktif, memvalidasi terhadap `Membership`. Role yang tidak dimiliki ditolak. | BR-ROLE-007 dan BR-ROLE-010 punya tes. |
| R2.2 | Switcher di sidebar | Muncul hanya bila user punya lebih dari satu role. Tanpa login ulang. | Ganti role mengubah sidebar, dashboard, dan aksi tersedia. |
| R2.3 | Sidebar per role | Menu sesuai PRD 6.1 untuk PM, Member, Owner, Management, Client, Admin. Item yang halamannya belum ada disembunyikan, bukan tautan mati. | Tidak ada tautan ke halaman 404. |
| R2.4 | Role Client dan Admin | Client hanya melihat project yang dibagikan. Admin: Users, Roles & Permissions, Templates, Audit Logs. Halaman user yang ada dipindah ke Admin. | Client tidak bisa melihat data di luar project-nya. |

## Fase 3 — Lifecycle, health, aturan task

Status (3 November 2026): R3.1–R3.5 selesai.
- R3.1: `Project.status` menjadi `lifecycle_status` (Draf, Perencanaan, Berjalan, Ditahan, Selesai, Dibatalkan). Health (Sesuai rencana, Perlu perhatian, Terlambat, Kritis) dihitung dari selisih progress, tenggat, dan issue kritis, hanya untuk project Berjalan atau Ditahan. Tampil terpisah di list, header, dashboard, dan export. Migrasi memetakan `on_track`, `at_risk`, `delayed` menjadi Berjalan.
- R3.2: aturan transisi di `Project.clean()`: project baru hanya Draf atau Perencanaan; Berjalan butuh Owner, PM, task, dan baseline; Selesai butuh semua task selesai dan tidak ada issue terbuka; Dibatalkan butuh alasan (`cancellation_reason`). Aturan tidak diulang bila status tidak berubah.
- R3.3: urutan kolom dan status task: In Progress, In Review, Blocked, Done. Nilai internal `review` tetap.
- R3.4: PM tidak menjadi assignee (di project yang dikelolanya), dan assignee harus berperan pelaksana (permission `task.execute`). Aturan hanya diperiksa saat assignee berubah, jadi data lama tidak rusak. Form PM tidak memuat progress dan alasan hambatan; status PM terbatas Backlog dan To Do; API status dan progress menolak PM (403). Admin tetap boleh keduanya.
- R3.5: mengganti assignee butuh permission `task.reassign` (form dikunci bila tidak ada); perubahan tercatat di activity log.
Catatan: health belum disimpan di snapshot (R5.3). Role Owner belum punya aksi persetujuan sampai Fase 5.

| ID | Item | Cakupan | Selesai bila |
|---|---|---|---|
| R3.1 | Pisahkan lifecycle dan health | `lifecycle_status`: Draft, Planning, In Progress, On Hold, Completed, Cancelled. `health_status`: On Track, At Risk, Delayed, Critical (terhitung, bukan diisi manual). Migrasi memetakan `ProjectStatus` lama. | Keduanya tampil terpisah di list, detail, dan export. |
| R3.2 | Aturan transisi | Masuk In Progress butuh syarat planning (ada phase/task, baseline, owner). Completed butuh syarat closure. Cancelled butuh alasan. | BR-PROJ-003 sampai 007 punya tes. |
| R3.3 | Status task | Urutan dan label `In Review` sebelum `Blocked` sesuai PRD 9.3. Nilai internal `review` dipertahankan agar data aman. | Kanban dan filter mengikuti urutan PRD. |
| R3.4 | PM bukan assignee | Tolak assignment ke user ber-role PM saja (D5). `can_edit_task` tidak lagi memberi PM hak update progress. PM tetap boleh ubah data perencanaan. | BR-TASK-004 dan 008 punya tes; PM tidak bisa mengubah progress task orang lain. |
| R3.5 | Reassign dengan permission | `task.reassign` terpisah dari edit biasa, tercatat di activity log. | BR-TASK-007. |

## Fase 4 — Progress Task, Project Control, Project Owner

Status (4 November 2026): R4.1–R4.4 selesai. Kode baru dipisah dari `views.py` yang sudah besar: `control.py` (query dan tanda pengecualian), `control_views.py` (halaman dan aksi), `dashboards.py` (dashboard per role).
- R4.1: halaman Progress Task (`/progress-task/`, permission `task.monitor`): semua task di project yang dikelola PM, tanpa kontrol update progress. Filter: project, phase, pelaksana, status, rentang target; chip cepat: terlambat, terhambat, menunggu review, terlambat mulai, melewati baseline, belum dimulai, selesai. Kolom rencana (baseline), jadwal, aktual, dan deviasi. Field baru `Task.actual_start` terisi otomatis saat pekerjaan pertama kali dimulai.
- R4.2: Project Control (`/control/` dan tab "Kontrol" di project, permission `project.control`): ringkasan pengecualian per project dan daftar task per kategori (setiap task muncul sekali) dengan aksi reassign.
- R4.3: tindak lanjut ke pelaksana: komentar pada task plus notifikasi; reassign memakai permission `task.reassign` dan tercatat di activity log. Kedua aksi hanya untuk PM project tersebut (atau Admin).
- R4.4: dashboard Owner ("Ringkasan outcome") tampil saat role aktif Owner: project milik Owner, health, target vs aktual, pencapaian milestone, issue dan risiko besar, milestone mendatang.
Belum: "keputusan tertunda" dan "penerimaan deliverable" di dashboard Owner menunggu Fase 5 dan 6; kolom "review status" menunggu Reviewer (R5.5). Menu "Pekerjaan saya" dihapus dari sidebar PM (PM bukan pelaksana).

| ID | Item | Cakupan | Selesai bila |
|---|---|---|---|
| R4.1 | Progress Task | Halaman monitoring seluruh task di project untuk PM (read-only atas progress), update untuk assignee. Menggantikan sebagian `my_tasks` untuk PM. | PM melihat semua task tanpa tombol update progress. |
| R4.2 | Project Control | Satu halaman PM: overdue, blocked, menunggu review, deviasi jadwal, reassign, follow-up. | PM menjawab pertanyaan PRD bagian 32 dalam satu layar. |
| R4.3 | Follow-up | Aksi "tindak lanjuti" ke assignee memakai notifikasi dan komentar yang sudah ada. | Tercatat di activity log. |
| R4.4 | Workspace Owner | Dashboard Owner: milestone, issue besar, risk besar, keputusan tertunda. | Owner hanya melihat project miliknya. |

## Fase 5 — Baseline berversi, approval, review

Status (5 November 2026): hanya baseline berversi yang dibangun (R5.1–R5.3). Mekanisme approval (R5.4–R5.6) sengaja tidak dipakai: tidak ada persetujuan baseline, review task, atau inbox approval.
- R5.1: model `Baseline` (versi, status `active`/`superseded`, pembuat, `baseline_data` JSON). Versi lama tidak dihapus. Simpan baseline dari tab Jadwal membuat versi baru yang langsung berlaku; migrasi mengisi versi 1 untuk project yang sudah punya kurva.
- R5.2: kurva planned progress tetap di `ProgressBaselinePoint` dan diganti saat versi baru dibuat (`capture_baseline`). Kurva manual belum punya antarmuka override terpisah.
- R5.3: `ProgressSnapshot.baseline` dan `health_status` terisi saat snapshot dibuat; snapshot lama tidak dihitung ulang.
- R5.4–R5.6 (8 November 2026, keputusan 5 November dibatalkan): selesai sebagai fitur yang dapat dikonfigurasi dan default mati. App baru `apps/governance`: `ApprovalPolicy` per project dan jenis (plan, baseline, task, deliverable, change request, closure), berurutan atau paralel, maksimal 3 approver, self-approval dilarang kecuali diizinkan; `ApprovalRequest` + `ApprovalStep` menyimpan riwayat dan alasan (penolakan wajib alasan, tidak ada aksi hapus). Otoritas berasal dari penunjukan (approver, `Task.reviewer`, reviewer deliverable, atau Project Owner) dan role aktif harus punya permission jenisnya (`plan.approve`, `baseline.approve`, `task.review`, `deliverable.accept`, `change_request.approve`, `closure.approve`). Baseline yang perlu persetujuan berstatus "Menunggu persetujuan" dan baru berlaku setelah disetujui; persetujuan rencana menjadi syarat Berjalan; persetujuan penutupan menjadi syarat Selesai dan otomatis menutup project. Review task: `Task.reviewer`; pelaksana Kirim untuk diperiksa → In Review → setujui (Done) atau tolak (kembali Sedang dikerjakan, alasan menjadi komentar). Halaman `/approvals/` (Persetujuan) dan `/reviews/` (Pemeriksaan saya), tab project "Persetujuan", keputusan tertunda di dashboard Owner. Perubahan konfigurasi tercatat di activity log.

| ID | Item | Cakupan | Selesai bila |
|---|---|---|---|
| R5.1 | Model `Baseline` | `version`, `approved_by`, `approved_at`, `baseline_data` (snapshot jadwal, bobot, milestone). Baseline lama tidak pernah dihapus. | BR-CHG-006. |
| R5.2 | Planned progress dari baseline | Default linear dari durasi task di baseline. Kurva manual tetap bisa dipakai sebagai override. | Planned progress berubah hanya saat baseline baru disetujui. |
| R5.3 | Snapshot menyimpan versi baseline | `ProgressSnapshot.baseline` dan `health_status`. | Snapshot lama tidak dihitung ulang. |
| R5.4 | Model `Approval` dan konfigurasi per project | Tipe: plan, baseline, task, deliverable, change request, closure. Sequential atau paralel, aturan self-approval. | BR-APR-001 sampai 006. |
| R5.5 | Reviewer dan alur review task | `Task.reviewer`; submit → In Review → approve/reject; reject wajib alasan dan kembali ke status yang bisa dikerjakan. | Alur PRD 18.3 punya tes ujung ke ujung. |
| R5.6 | Halaman Approvals dan My Reviews | Antrean per user. | Item hilang dari antrean setelah diputuskan. |

## Fase 6 — Change Request dan Deliverable

Status (8 November 2026): R6.1–R6.4 selesai.
- R6.1: klasifikasi di `apps/governance/changes.py`. Major: deadline project, tanggal milestone, bobot task, kriteria/target deliverable; selebihnya minor. Perubahan major setelah baseline berlaku selalu tercatat (`change.major`). `Project.change_control` (default mati): bila aktif, perubahan major ditolak kecuali ada change request yang sudah disetujui dan belum diterapkan ("jendela perubahan").
- R6.2: `ChangeRequest` Draf → Diajukan → Sedang ditinjau → Disetujui/Ditolak → Diterapkan; alasan dan penilaian dampak wajib; persetujuan memakai mesin R5 (default Project Owner). Ditolak tidak bisa diterapkan.
- R6.3: Terapkan mengubah target selesai (bila diusulkan) dan membuat versi baseline baru (`ChangeRequest.applied_baseline`); versi lama menjadi Digantikan. Catatan: PRD §26.17 meletakkan `change_request_id` di Baseline; relasinya dibalik untuk menghindari ketergantungan migrasi melingkar, maknanya sama.
- R6.4: `Deliverable` (task terkait, kriteria penerimaan, bukti teks/tautan, pemilik, penerima, target, tanggal serah) Draf → Diajukan → Sedang ditinjau → Diterima/Ditolak; bukti wajib sebelum diajukan; diterima/ditolak oleh penerima yang ditunjuk atau Project Owner dengan `deliverable.accept` (default Owner dan Client). Tab project "Deliverable" (juga untuk Client).

| ID | Item | Cakupan | Selesai bila |
|---|---|---|---|
| R6.1 | Klasifikasi perubahan | Minor boleh langsung; major (deadline, scope, bobot, milestone, deliverable) diarahkan ke Change Request setelah baseline disetujui. | BR-CHG-001 dan 002. |
| R6.2 | Model dan alur `ChangeRequest` | Draft → Submitted → Under Review → Approved/Rejected → Applied; impact, reason, jadwal, scope. | Rejected tidak bisa Applied. |
| R6.3 | Baseline revision | Applied menghasilkan versi baseline baru, lama tersimpan. | BR-CHG-005 dan 006. |
| R6.4 | Model `Deliverable` | Terkait task, acceptance criteria, evidence, status Draft sampai Accepted/Rejected. | Client/Owner dengan permission dapat menerima atau menolak. |

## Fase 7 — Risk, struktur, template

Status (8 November 2026): R7.1–R7.6 selesai.
- R7.1: `Risk` punya deskripsi, probability dan impact (1–5), skor = P × I, tanggal tinjau (rename dari `due_date`), status "Menjadi masalah", dan `issue` hasil konversi. Owner, mitigasi, dan tanggal tinjau wajib di form/`clean()` (data lama tidak dipaksa). `severity` kini diturunkan dari skor (≤4 rendah, ≤9 sedang, ≤16 tinggi, ≥17 kritis) sehingga query lama tetap jalan. Migrasi `projects.0017` memetakan severity lama: low→2×2, medium→3×3, high→4×4, critical→5×5 (tingkat hasilnya sama). Aksi "Jadikan issue".
- R7.2: `WorkPackage` (opsional, di dalam phase); `Task.work_package`; task mengikuti phase work package, detail mengikuti induk. Tab project "Struktur" menampilkan phase → work package → task → detail.
- R7.3: `Task.progress_method` manual / berdasarkan status / dari detail. Persentase In Progress dan In Review diatur per project (`Project.progress_config`, default 50/80); Blocked mempertahankan nilai. Aturan override: activity yang punya detail selalu memakai metode detail (otomatis), manual+detail tidak mungkin terjadi; API progress menolak task bermetode status.
- R7.4: `Project.weight_mode` otomatis/manual. Project baru dari form memakai otomatis (bagi rata, dihitung ulang saat task dibuat, dipindah, diarsipkan); project lama tetap manual agar progress tidak berubah. Aksi Bagi rata, Normalisasi ke 100%, dan Atur bobot (wajib total 100%) per kelompok sibling; ikut kontrol perubahan R6.1.
- R7.5: `ProjectTemplate` (struktur JSON berversi, progress, aturan approval tanpa orang, field tambahan, mode bobot). Admin (`template.manage`) mengelola di `/templates/` dengan outline singkat; "Simpan sebagai template" dari project; form Buat project punya "Mulai dari template" yang menyalin phase, work package, task (dengan tanggal dari tanggal mulai), milestone, dan aturan. Project menyimpan `template` + `template_version`; mengubah template tidak mengubah project.
- R7.6: `Project.project_type` (default Umum) di form, daftar, header, dan export; field tambahan sederhana (`custom_fields` + `custom_values`, jenis teks/angka/tanggal) diatur dari menu Lainnya → Field tambahan, tampil di header dan export.

| ID | Item | Cakupan | Selesai bila |
|---|---|---|---|
| R7.1 | Risk lengkap | Probability, impact, score, review date; owner dan mitigasi wajib; konversi Risk → Issue. | PRD 16.2 terpenuhi; migrasi `severity` ke probability/impact terdokumentasi. |
| R7.2 | Work Package | Level opsional antara phase dan task. | Tree view menampilkan phase → work package → task → subtask. |
| R7.3 | Progress method per task | Tambah status-based; larang kombinasi manual + subtask tanpa aturan override. | Tiga metode PRD 11.1 punya tes. |
| R7.4 | Bobot sibling 100% | Normalisasi otomatis rata dan validasi total 100% per kelompok. | BR-WGT-001 sampai 006. |
| R7.5 | Template project | `ProjectTemplate` (struktur, phase, task, milestone, workflow, approval, progress). Perubahan template tidak mengubah project berjalan. | Project baru dari template; project lama tidak berubah. |
| R7.6 | Project type dan custom field dasar | `project_type` wajib; custom field sederhana per project. | Muncul di form, list, dan export. |

## Fase 8 — Dashboard, report, audit per role

Status (8 November 2026): R8.1–R8.5 selesai.
- R8.1: dashboard sesuai role aktif: PM/Admin (KPI issue terbuka dan menunggu persetujuan, task terlambat, terhambat, menunggu pemeriksaan, milestone, aktivitas), Member (task terbuka, terlambat, terhambat, sedang dikerjakan, menunggu pemeriksaan, akan datang, pembaruan), Owner (ditambah keputusan tertunda), Management (portfolio tanpa judul task), Client (project, milestone, deliverable, menunggu penerimaan, pembaruan).
- R8.2: `portfolio_health()` menghitung distribusi health dan project yang butuh perhatian dari data; tampil di dashboard Management dan laporan Manajemen.
- R8.3: `/reports/<jenis>/` untuk Executive Summary, Progress, Jadwal, Task, dan Manajemen; isi halaman sama dengan unduhan (PDF/Excel/CSV). Export kini mewajibkan `report.export`, memakai `visible_projects`, menolak dataset detail task untuk role Management, dan menolak dataset internal untuk role tanpa `project.view_internal`. Dataset baru juga: risiko dan deliverable.
- R8.4: `/audit/` (permission baru `audit.view`, default Admin) menggabungkan ActivityEvent dan Revision: waktu, pelaku, role aktif, aksi, nilai lama → baru, alasan; filter project, jenis + ID entitas, pelaku, role, tanggal. `ActivityEvent` mendapat `entity_type`, `entity_id`, `reason`; Revision kini juga mencatat deliverable dan change request.
- R8.5: `Decision.related_issue` (issue dari project yang sama) di form dan daftar catatan.

| ID | Item | Cakupan | Selesai bila |
|---|---|---|---|
| R8.1 | Dashboard per role | PM, Member, Owner, Management, Client sesuai PRD bagian 21. | Management tidak melihat detail task teknis. |
| R8.2 | Portfolio health | Distribusi health, project butuh perhatian. | Terhitung dari data, bukan input manual. |
| R8.3 | Report | Executive Summary, Progress, Schedule, Task, Management; export CSV/Excel/PDF mengikuti `report.export`. | Export hanya memuat data yang boleh dilihat. |
| R8.4 | Audit trail | Satukan `ActivityEvent` dan `Revision` dalam tampilan audit dengan actor, role aktif, nilai lama dan baru, alasan. | Admin dapat menelusuri satu entitas. |
| R8.5 | Decision Log terhubung ke issue | Field `related_issue`. | Sesuai PRD 19.2. |

### Sengaja tidak diimplementasikan (Fase 5–8)

- "Perubahan dependency yang signifikan" sebagai perubahan major (PRD §17.2): "signifikan" tidak terdefinisi dan memblokirnya akan mematikan penyuntingan dependency di Gantt. Dependency tetap minor; perubahan tercatat di riwayat.
- Workflow status task yang dapat dikonfigurasi lewat template (PRD §5.2, `workflow_config`): status task (PRD §9.3) dipakai mesin progress, Kanban, kontrol, dan laporan; mengubahnya per project bertentangan dengan aturan tetap itu. Kolom `workflow_config` disiapkan tetapi tidak dibaca.
- Bukti deliverable sebagai unggahan berkas: dipakai teks/tautan agar tidak menambah penyimpanan dan aturan unduhan baru; lampiran tetap bisa lewat task terkait.
- Permission "Conditional" PRD §25 untuk review task: `task.review` diberikan default ke PM, Member, dan Owner karena review hanya berlaku bila reviewer ditunjuk; tanpa itu alur review tidak bisa dipakai tanpa konfigurasi admin. `task.approve` tidak dipakai terpisah (otoritas = penunjukan + `task.review`).
- Tab project sempat 13; sejak U6 (8 November 2026) menjadi tujuh tab dengan tampilan di dalamnya.

---

## Jalur UI/UX — clean, rapi, ramah pengguna

Berjalan paralel dengan fase di atas. Dasar visualnya (`DESIGN.md`: palet netral, Inter, panel 12px) sudah bagus dan dipertahankan; yang dibenahi adalah kepadatan, duplikasi, dan konsistensi. Temuan berasal dari audit halaman Dashboard dan Ringkasan project pada 3 November 2026 (desktop 1440 px, data demo).

### Temuan audit

| # | Temuan | Lokasi |
|---|---|---|
| T1 | Halaman Ringkasan project sangat panjang (~3000 px), memuat grafik besar, timeline, daftar task, issue, task terhambat, aktivitas, dan diskusi sekaligus. | `project/overview.html` |
| T2 | Informasi ganda: "Timeline ringkas" dan "Pekerjaan project" menampilkan task yang sama (teksnya sendiri mengakui). "Task terhambat" mengulang timeline. | `project/overview.html` |
| T3 | Tombol berulang: "Perbesar" muncul 3 kali, "Presentasi" dan "Presentasikan" dua-duanya ada; header punya 4 aksi sejajar. | Header project, overview |
| T4 | Kartu issue terlalu tinggi (tiga baris meta, dua tombol per kartu) untuk sekadar daftar ringkas. | `partials/_issue_row.html` |
| T5 | Kartu KPI dashboard berisi judul, subjudul, angka, dan keterangan. Kartu "Sesuai rencana 0" dan "Terlambat 0" memakai ruang yang sama dengan yang penting. | `portfolio/dashboard.html` |
| T6 | Spanduk "Import rencana" berada di atas judul halaman dan bersaing dengan aksi utama. | `portfolio/dashboard.html` |
| T7 | Panel "Perlu perhatian" jauh lebih pendek daripada grafik di sebelahnya, sehingga ada ruang kosong besar. Grafik batang untuk 3 project terasa berlebihan. | `portfolio/dashboard.html` |
| T8 | Bahasa campur: "Dashboard", "Projects", "Actual", "Board task" bersama label Indonesia. | Sidebar, label |
| T9 | Sembilan tab project (Ringkasan, Progress, Jadwal, Pekerjaan, Masalah, Milestone, Catatan, Aktivitas, Riwayat) dengan fungsi yang saling beririsan. | Navigasi project |

### Item

| ID | Item | Cakupan | Selesai bila |
|---|---|---|---|
| U1 | Kosakata dan bahasa seragam | Satu bahasa antarmuka (Indonesia) dengan glosarium istilah (project, task, milestone dibiarkan). Perbaiki T8. Dokumen `docs/ux-glossary.md`. | Tidak ada label campuran di sidebar, tab, tombol. |
| U2 | Ringkasan project satu layar | Tampilkan: header dengan health dan progress, grafik rencana vs aktual (lebih rendah), 3–5 hal yang perlu tindakan (overdue, blocked, review), milestone berikutnya. Pindahkan timeline, daftar task, issue, dan diskusi ke tab masing-masing. Perbaiki T1, T2. | Ringkasan muat sekitar dua layar; setiap blok punya satu tujuan. |
| U3 | Aksi header yang jelas | Satu aksi utama (Tambah task), sisanya ke menu "Lainnya". Satu nama untuk Presentasi, satu pola untuk Perbesar. Perbaiki T3. | Maksimal dua tombol terlihat di header. |
| U4 | Daftar issue dan task yang ringkas | Baris satu sampai dua baris, aksi di menu baris, severity sebagai lencana. Perbaiki T4. | Tinggi baris turun sekitar setengahnya, semua aksi tetap bisa dijangkau keyboard. |
| U5 | Dashboard berfokus pada tindakan | Ganti empat kartu KPI dengan ringkasan satu baris (angka plus label). Panel "Perlu perhatian" menjadi daftar utama; grafik portfolio dipindah ke bawah atau ke Laporan. Spanduk import dipindah ke menu "Buat project". Perbaiki T5, T6, T7. | Hal yang perlu tindakan terlihat tanpa scroll. |
| U6 | Tab project dirapikan | Gabungkan menjadi: Ringkasan, Pekerjaan (daftar, board, jadwal sebagai tampilan), Progress, Masalah dan risiko, Milestone, Catatan, Aktivitas (termasuk Riwayat). Perbaiki T9. Menyesuaikan PRD 22.1. | Tab maksimal tujuh, tidak ada fungsi yang hilang. |
| U7 | Empty state dan umpan balik | Setiap daftar kosong menjelaskan langkah berikutnya; konfirmasi dan pesan galat yang konsisten; status simpan pada update cepat. | Semua halaman utama punya empty state yang diuji. |
| U8 | Pola formulir | Satu pola field, bantuan, galat, dan tombol; pisahkan field wajib dari lanjutan (disclosure). Terutama form project dan task yang akan bertambah dengan Fase 1–7. | Form project baru tidak lebih dari satu layar untuk field wajib. |
| U9 | UX per role | Setelah Fase 2: tiap workspace mempunyai halaman awal sendiri dan hanya menampilkan aksi yang boleh dilakukan (PRD 28.1). | Tidak ada tombol yang menghasilkan galat izin. |
| U10 | Verifikasi | Tangkapan layar desktop, mobile 390 px, dan gelap untuk halaman utama sebelum dan sesudah; jalankan audit aksesibilitas yang ada (`tests/test_accessibility.py`). | Tidak ada regresi aksesibilitas; ada perbandingan sebelum dan sesudah. |

Status (3 November 2026): U1–U5 selesai. Ringkasan project turun dari ~2980 px ke ~1630 px pada data demo; seluruh tes lulus. U6 dan seterusnya belum dikerjakan. Pada U1, halaman publik (`templates/public/`) sengaja belum diseragamkan karena `tests/test_public_project.py` masih mengacu ke teks "Actual".

Status (8 November 2026): U6–U10 selesai (belum di-commit).
- U6: tujuh tab project — Ringkasan, Pekerjaan (Daftar/Board/Jadwal/Struktur), Progress, Masalah & risiko, Milestone & deliverable, Catatan & keputusan, Aktivitas (Log, Riwayat, Persetujuan & perubahan, Kontrol). Pengaturan project (`/projects/<id>/settings/`: info, anggota, field, bobot, kolom, rencana AI, template, persetujuan, kontrol perubahan, tautan publik, integrasi, arsip) untuk PM. Semua URL lama tetap; `PROJECT_GROUPS` di `apps/projects/views.py`. Sidebar per role dua grup (Kerja, Pantau); Pengguna, Role, Template, Jejak audit, Integrasi pindah ke Pengaturan. Catatan semua project dan Pemeriksaan saya (PM) lewat Quick actions / halaman Persetujuan.
- Pembuatan cepat: wizard Buat project tiga langkah (data inti → sumber rencana: kosong, tempel daftar task, template, import AI → tinjau) dengan Owner = pembuat bila boleh, tanggal akhir otomatis dari panjang rencana. Jadwal kosong menawarkan Tempel daftar task, Mulai dari template (`apply-template/`), Import rencana AI, Tambah phase; `paste/` menjadi cadangan form untuk layar kecil. Checklist Siap berjalan di Ringkasan (Owner, PM, task, baseline satu klik, rencana disetujui bila aktif) dengan tombol Mulai project.
- U7: empty state dengan langkah berikutnya di Daftar task, Jadwal, Ringkasan, Catatan, Masalah, dashboard Member; Quick actions memuat aksi project (buat task cepat, tempel daftar, persetujuan, pengaturan).
- U8: disclosure seragam "Opsi lanjutan"; label form kini benar-benar tampil (BoundField dibuat ulang setelah label diubah, `FieldList` di `apps/form_widgets.py`); baseline dan pengajuan rencana kembali ke halaman asal.
- U9: tombol Ajukan perubahan hanya untuk yang berhak; Pengaturan project hanya untuk PM.
- U10: tangkapan layar sebelum/sesudah (desktop 1440, mobile 390, gelap) untuk Dashboard, Ringkasan, Jadwal, Buat project; pytest, ruff, makemigrations --check, dan lima skrip `tests/browser/*.mjs` lulus pada database sementara. Diperbaiki sekalian: Gantt mobile (kolom grafik lebar 0 dan teks "null"), menu Panduan mobile yang tidak tertutup.
- Ditunda: anggota dari template (template belum menyimpan anggota; perlu perubahan skema `ProjectTemplate`), uji kemudahan dengan pengguna (target 90%).

Urutan yang disarankan: U1, U2, U3, U4, U5 dapat dikerjakan sekarang karena tidak bergantung pada Fase 1. U6 setelah U2. U8 dan U9 mengikuti Fase 1–2.

## Jalur Gantt interaktif

Acuan interaksi: blok "Project Timeline" di https://reui.io/blocks/application/gantt (daftar task berbentuk pohon di kiri, bar yang bisa digeser dan diubah ukurannya di kanan, penolakan drop dengan pesan). Kita tidak memakai shadcn atau React; Gantt dibuat sendiri dengan JavaScript biasa di `static/js/`, tanpa dependensi baru, mengikuti token di `tokens.css`. Halaman acuan hanya dibaca teksnya, jadi detail visualnya mengikuti `DESIGN.md`, bukan meniru piksel.

Kondisi sekarang: `static/js/task-timeline.js` (44 baris) hanya mengatur zoom dua tingkat dan scroll. Endpoint `work:task_dates` sudah ada, tetapi belum ada drag, resize, atau garis dependency di UI. Ini memenuhi PRD 12.3 yang belum terpenuhi.

| ID | Item | Cakupan | Selesai bila |
|---|---|---|---|
| G1 | Layout dua panel | Pohon phase → task → subtask di kiri (bisa dilipat, lebar kolom bisa diubah), grid waktu di kanan, scroll vertikal tersinkron, header tanggal menempel. | Ratusan baris tetap lancar (baris virtual atau render bertahap). |
| G2 | Zoom dan navigasi | Hari, minggu, bulan (PRD 12.3), garis hari ini, tombol "ke hari ini", geser kanvas dengan scroll dan drag di area kosong. | Zoom mempertahankan titik tengah. |
| G3 | Bar | Warna menurut status, indikator progress di dalam bar, penanda milestone, ringkasan phase sebagai bar induk. Bar baseline tipis di bawah bar jadwal terkini (PRD 12.4). | Selisih terhadap baseline terlihat tanpa membuka detail. |
| G4 | Geser dan ubah ukuran | Drag bar untuk memindah, tarik tepi untuk mengubah durasi, snap ke hari, pratinjau tanggal saat menarik, Esc membatalkan, simpan lewat `task_dates`. Subtask tetap berada di dalam rentang induk. | Perubahan tersimpan, tercatat di activity log, dan dibatalkan bila server menolak. |
| G5 | Aturan penolakan | Drop ditolak dengan pesan jelas bila: task selesai, user bukan PM project, melanggar dependency, atau subtask keluar dari induk. Hanya jadwal terkini yang berubah; baseline tidak pernah. | Setiap aturan punya tes server dan tes browser. |
| G6 | Dependency | Garis penghubung antar bar, buat dan hapus dependency dengan menarik dari titik ujung bar, tolak circular (aturan yang sudah ada di `revisions.py`). | BR-TASK-014 teruji lewat UI. |
| G7 | Penyesuaian dependen | Saat task digeser dan mengenai task penerus, tawarkan geser penerus ikut (opt-in) dan tampilkan dampaknya sebelum disimpan. | Tidak ada perubahan beruntun tanpa konfirmasi. |
| G8 | Aksesibilitas dan mobile | Semua aksi punya jalur keyboard (panah geser tanggal, Shift+panah ubah durasi), `aria-live` untuk hasil, area scroll berlabel, di mobile mode baca saja dengan satu jari scroll. | Lolos `tests/test_accessibility.py` dan overflow 390 px. |
| G9 | Dipakai ulang | Komponen yang sama dipakai di Jadwal project, Jadwal semua project, dan versi baca-saja di halaman publik dan presentasi. | Tidak ada tiga implementasi terpisah. |

Urutan: G1 → G2 → G3 → G4 → G5 → G6 → G7; G8 berjalan bersamaan sejak G4; G9 setelah G3. Dependensi pada fase lain: G5 bergantung pada R3.4 dan R1.4 (permission), G3 pada R5.1 (baseline berversi). Sebelum R5, G3 memakai `baseline_start_date` dan `baseline_end_date` di task.

Keputusan: hanya PM yang boleh menggeser atau mengubah ukuran bar (sesuai PRD: Member mengubah progress, bukan jadwal). Member melihat Gantt dalam mode baca saja. Masih terbuka: apakah geser task penerus otomatis (G7) diinginkan atau cukup peringatan.

## Yang dipertahankan tanpa perubahan besar

Progress terbobot, planned vs actual, threshold, snapshot harian, Gantt dan dependency (termasuk deteksi circular), blocked task, issue, notes, decision log, komentar, mention, notifikasi, arsip, pencarian, histori revisi, dan export. Hanya disesuaikan lewat R3, R5 dan R8.

## Prinsip pengerjaan

- Tiap item punya migrasi yang bisa dibalik dan tes sebelum item berikutnya.
- Fase 1 dikerjakan berurutan; mulai Fase 3, R3 dan R7 dapat paralel selama tidak menyentuh berkas yang sama.
- Tandai status selesai di tabel ini setiap kali item masuk ke `main`, seperti pada roadmap lama.
