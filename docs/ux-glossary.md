# Kosakata antarmuka Scope

Satu bahasa antarmuka: Indonesia. Istilah serapan yang sudah umum di tim dipertahankan dan dipakai seragam.

| Konsep | Istilah di UI | Jangan dipakai |
|---|---|---|
| Project | Project | Projects, Proyek |
| Task | Task | Tugas, Board task |
| Papan kanban | Papan task | Board task |
| Milestone | Milestone | Tonggak |
| Issue | Masalah (nav, judul, tombol) | Issue, Blocker |
| Risk | Risiko | Risk |
| Planned progress | Rencana | Planned |
| Actual progress | Aktual | Actual |
| Variance | Selisih / Deviasi | Variance |
| Baseline | Baseline | — |
| Presentasi | Presentasi | Presentasikan |
| Dashboard | Dashboard | — |
| Progress Task (menu) | Progress task | Progress Task |
| Project Control | Kontrol project | Project Control |
| Audit trail | Jejak audit | Audit trail |
| Docs | Panduan | Docs |
| Kanban board | Board (tampilan), Papan task (judul) | Kanban Board |
| Due date | Target | Due, overdue |
| Field opsional | Opsi lanjutan | Detail tambahan, Pengaturan tambahan |
| Baseline capture | Buat baseline dari jadwal | Simpan baseline jadwal |

## Navigasi

- Sidebar: grup **Kerja** dan **Pantau**; administrasi di **Pengaturan**.
- Tab project (maksimal tujuh): Ringkasan, Pekerjaan, Progress, Masalah & risiko,
  Milestone & deliverable, Catatan & keputusan, Aktivitas. Tampilan di dalam tab
  (mis. Daftar, Board, Jadwal, Struktur) memakai pilihan tampilan di atas isi.
- Header project: satu tombol utama + menu **Lainnya** (Buat, Lihat, Pengaturan).
- Tombol simpan form: "Simpan" atau nama objeknya ("Simpan task"), Batal di kirinya.
- Empty state: jelaskan keadaan lalu tawarkan langkah berikutnya sebagai tombol.

Aturan: satu konsep, satu istilah, di semua halaman. Nama internal (kode, URL, atribut `data-*` yang dipakai tes) tidak ikut berubah.
Halaman publik (`templates/public/`) belum diseragamkan karena tes masih mengacu ke teks "Actual".
