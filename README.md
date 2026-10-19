# Scope (Scope)

Internal project management & progress monitoring system — a centralized
**Scope** for Project Managers, Project Leads, and Management.

Bukan sekadar task management: Scope memberikan visibility terhadap progress
project, planned vs actual, timeline pekerjaan, milestone, issues,
notes, dan reporting management — semua dari satu aplikasi.

## Stack

- **Django** + **HTMX** (server-rendered), CSS native + Tailwind CLI
- **Chart.js** — Plan vs Actual progress chart
- **Timeline CSS** — rentang pekerjaan, rencana/actual dan update lewat drawer
- **Local username/password** default; **Authlib** untuk Microsoft Entra ID SSO opsional
- **PostgreSQL** di produksi, **SQLite** untuk development lokal
- **Whitenoise** — static file serving

## Development

```bash
uv sync
uv run manage.py migrate
uv run manage.py create_local_user admin --role pm --staff
npm ci
npm run css:build
# uv run manage.py seed_demo      # opsional, hanya database demo
uv run manage.py runserver
```

Testing:

```bash
uv run pytest
uv run ruff check .
```

## Environment

Lihat `.env.example`.

Variabel utama:

| Var | Keterangan |
|---|---|
| `DJANGO_SECRET_KEY` | Secret key Django |
| `DJANGO_DEBUG` | `true` untuk development |
| `DATABASE_URL` | `postgres://user:pass@host:5432/db` (kosong = SQLite) |
| `AZURE_TENANT_ID` | Entra ID tenant (atau `common`) |
| `AZURE_CLIENT_ID` | Client id app registration |
| `AZURE_CLIENT_SECRET` | Client secret app registration |

Login default di `/auth/login/` menggunakan username dan password lokal. Perintah
`create_local_user` meminta password tanpa menampilkannya. Role tersedia: `pm`,
`member`, dan `management`; `--staff` memberi akses administrasi akun. Staff juga
bisa membuat akun melalui Settings. Tidak ada password bawaan.

Untuk akun lama/data demo yang belum memiliki password:

```bash
uv run manage.py changepassword USERNAME
```

SSO Microsoft muncul jika konfigurasi Entra ID tersedia.

## Progress dan laporan

Done selalu bernilai 100%; actual dihitung dari bobot task utama atau manual
override. Baseline dapat diambil dari jadwal task. Dependency harus selesai
sebelum task mulai; Blocked wajib memiliki alasan. Akses data, komentar,
attachment, dan ekspor mengikuti keanggotaan project dan role.

Snapshot hari ini diperbarui ketika task atau project berubah. Agar hari tanpa
perubahan tetap tersimpan, jalankan perintah berikut sekali setiap hari dari
scheduler deployment (misalnya cron). Scheduler belum dipasang oleh aplikasi.

```bash
uv run manage.py snapshot_progress
```

Reports menyediakan CSV, XLSX, dan PDF untuk summary, progress, timeline,
task, issue, dan milestone. UI mengikuti DESIGN.md (Precision): kanvas netral terang, panel putih dengan hairline,
satu aksen violet untuk aksi dan state aktif, font Inter lokal, dan komponen native,
serta tabel dan board dengan scroll lokal; tidak menggunakan shadcn/Cotton.
Lihat [DESIGN.md](DESIGN.md) untuk aturan visual.

## Struktur

Panduan penggunaan tersedia di **Pengaturan → Docs** (`/auth/settings/docs/`).
Dokumentasi berbahasa Indonesia mencakup alur proyek dan pekerjaan tim dengan
contoh visual, pencarian topik, serta simulasi progres berbobot. Isi panduan
berada di `apps/identity/documentation.py`; catatan implementasinya tersedia
di [docs/documentation-page.md](docs/documentation-page.md).

```
config/          # settings, urls, wsgi/asgi
apps/
  identity/      # auth (Entra ID SSO), roles
  projects/      # project, phase, milestone, progress, notes, decisions, activity
  work/          # task, issue, comments
templates/       # base + partials/, projects/{portfolio,project,forms,presentation,partials}/, work/, identity/
static/          # css, js, vendor libs
tests/           # pytest
```

## Rencana dari AI

Di halaman project, pilih **Lainnya → Import rencana dari AI**. Unduh template
JSON, kirim ke AI bersama brief project, lalu unggah file hasilnya. Template
memuat nama anggota yang tersedia dan contoh tahap, milestone, task, serta
dependency. File valid langsung menghasilkan rencana di project.

Untuk membuat project baru sekaligus rencananya, gunakan **Import dari AI**
di dashboard atau daftar project. Import bersifat atomik: file yang salah
tidak menyimpan sebagian data. File identik tidak membuat task ganda. Import
menambahkan data, bukan mengedit atau menghapus rencana yang sudah ada.

Export JSON tersedia di panel import untuk melanjutkan diskusi dengan AI.
Nama anggota menggunakan username akun lokal; import tidak membuat akun baru.
Batas file 2 MB, 100 tahap, 100 milestone, dan 500 task per import.

## Tampilan dan pengerjaan bersama

Pilih **Light**, **Dark**, atau **System** melalui kontrol tema di header. Pilihan tersimpan di browser dan berlaku juga pada halaman login. PM dapat memilih **Dikerjakan oleh** dan satu **Rekan pengerjaan** pada form task. Kedua orang dapat memperbarui task yang sama. JSON menggunakan `assignee` dan daftar `collaborators` berisi maksimal satu username.

Setelah mengambil perubahan, jalankan `python manage.py migrate` dan `npm run css:build`. Migrasi `work.0004_task_collaborators` menambahkan relasi rekan tanpa mengubah assignee yang sudah ada.
