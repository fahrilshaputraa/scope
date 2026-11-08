# Integrasi Microsoft Teams dan Outlook

Halaman: **Pengaturan → Integrasi** (`/integrations/`). App: `apps/integrations`.

## 1. Microsoft Teams (webhook)

### Setup di Teams

1. Buka channel tujuan → **⋯ → Workflows**.
2. Pilih templat **Post to a channel when a webhook request is received**, selesaikan wizard.
3. Salin URL webhook (`*.logic.azure.com` atau `*.powerplatform.com`).
   Incoming Webhook lama (`*.webhook.office.com`) juga diterima selama masih aktif di tenant.
4. Di Scope: **Tambah webhook** → pilih cakupan, event, simpan → **Kirim tes**.

### Cakupan dan permission

| Cakupan | Siapa yang boleh mengatur |
|---|---|
| Project | `project.update` dan PM project tersebut (`can_manage_project`); Admin untuk semua project |
| Global (semua project aktif) | `user.manage` |

### Event

| Kode | Sumber | Kunci dedupe |
|---|---|---|
| `task_overdue` | scan terjadwal, due date lewat ≤ 7 hari | `task_overdue:<task>:<due>` |
| `task_blocked` | sinyal dari `Notification` `task.status` (fan-out yang sudah ada) | `task_blocked:<task>:<kunci notifikasi tanpa penerima>` |
| `milestone_due` | scan, ≤ `TEAMS_MILESTONE_DUE_DAYS` hari lagi | `milestone_due:<id>:<tanggal>` |
| `milestone_missed` | scan, lewat ≤ 7 hari dan belum selesai | `milestone_missed:<id>:<tanggal>` |
| `issue_critical` | sinyal `Notification` `issue.created` + scan (7 hari) | `issue_critical:<issue>` |
| `health_changed` | scan, dibanding `ProjectHealthMark` (observasi pertama = baseline) | `health_changed:<project>:<lama>:<baru>:<jam>` |
| `mention` | `post_save` `Mention` / `CommentMention` | `mention:<jenis>:<comment>:<user>` |
| `daily_summary` | scan, sekali per hari setelah `TEAMS_DAILY_SUMMARY_HOUR` | `daily_summary:<tanggal>` |

Beberapa notifikasi in-app untuk satu perubahan (satu per penerima) memetakan ke
satu kunci, jadi channel menerima satu pesan. Sinyal dan scan memakai kunci yang sama,
sehingga tidak ada duplikat. `(webhook, dedupe_key)` unik di `DeliveryLog`.

### Antrean dan pengiriman

- Web request **tidak pernah** mengirim HTTP ke Teams. Receiver hanya menulis baris
  `DeliveryLog` (status `pending`) setelah transaksi commit. Tombol **Kirim tes** juga
  hanya mengantrekan.
- `uv run manage.py send_teams_notifications` mendeteksi event terjadwal lalu mengirim
  antrean (`--send-only` melewati deteksi). Idempoten; aman dijalankan via cron/systemd.
- Scheduler internal (`SCOPE_SCHEDULER_ENABLED=true`) memanggil hal yang sama di
  setiap tick (`apps/projects/scheduler.py` → `apps.integrations.tick.run_teams_tick`).
- Pengiriman: `requests.post` dengan timeout `TEAMS_REQUEST_TIMEOUT`, satu retry inline
  untuk timeout/5xx/429, lalu retry antar-tick (backoff 5 menit × percobaan) hingga
  3 percobaan. 4xx lain langsung `failed`. Baris di-*claim* atomik sehingga beberapa
  worker tidak mengirim ganda. `sent_at` adalah penanda antrean (seperti `emailed_at`).
- Hasil terakhir tersimpan di `TeamsWebhook.last_status/last_error/last_delivery_at`
  dan tampil di halaman Integrasi.

### Keamanan URL

- Hanya `https`, port 443, tanpa kredensial, bukan IP, host berakhiran
  `.webhook.office.com`, `.logic.azure.com`, atau `.powerplatform.com`. Host divalidasi
  ulang sebelum setiap pengiriman.
- URL disimpan terenkripsi (Fernet, `INTEGRATIONS_ENCRYPTION_KEY`; tanpa key diturunkan
  dari `SECRET_KEY`, sehingga mengganti `SECRET_KEY` membuat URL tersimpan tidak terbaca
  dan harus diisi ulang). UI dan admin hanya menampilkan petunjuk `host/…abcd`.

### Format kartu

Envelope `{"type": "message", "attachments": [{"contentType":
"application/vnd.microsoft.card.adaptive", "content": <AdaptiveCard 1.4>}]}` dengan
konteks project, judul berwarna, FactSet, dan aksi **Buka di Scope** (`SITE_URL`).

## 2. Kalender (.ics) tanpa OAuth

- Langganan per pengguna: `/integrations/calendar/<token>.ics` (tanpa login, token
  rahasia 32 byte). Isi: task yang ditugaskan (assignee atau rekan) dengan due date,
  milestone semua project yang terlihat (`visible_projects`), dan issue terbuka milik
  pengguna (hanya bila punya `project.view_internal`). Rentang: 60 hari ke belakang
  hingga masa depan. Event all-day, UID stabil (`scope-task-<id>@host`).
- Token salah atau pengguna nonaktif → 404. **Reset tautan** membuat token baru; tautan
  lama langsung 404.
- Unduh per project: `/integrations/projects/<id>/calendar.ics` (login, harus bisa
  melihat project; selain itu 404).
- Outlook: *Tambahkan kalender → Berlangganan dari web*. Google: *Kalender lain → Dari URL*.
  Keduanya menyegarkan berkala (beberapa jam hingga 24 jam).

## 3. Microsoft Graph (opsional)

Aktif hanya bila `AZURE_ENABLED` (client id + secret terisi) **dan**
`OUTLOOK_GRAPH_ENABLED=true`. Tanpa itu, tombol menampilkan pesan yang menjelaskan apa
yang perlu dikonfigurasi.

Alur consent terpisah dari login SSO (scope SSO tetap minimal):
`/integrations/outlook/connect/` → Microsoft → `/integrations/outlook/callback/`.
Token disimpan terenkripsi di `OutlookConnection` dan di-refresh otomatis.
**Tambahkan ke kalender Outlook** membuat event all-day lewat `POST /me/events`; klik
berikutnya memperbarui event yang sama (`PATCH`, tercatat di `OutlookEvent`).

### Permission Azure (App registration)

1. **Authentication** → tambahkan redirect URI (Web):
   `https://<SITE_URL>/integrations/outlook/callback/` (selain `/auth/callback/` untuk SSO).
2. **API permissions → Microsoft Graph → Delegated**: `openid`, `profile`, `email`,
   `offline_access`, `Calendars.ReadWrite`.
3. **Grant admin consent** bila kebijakan tenant melarang user consent.
4. Set `OUTLOOK_GRAPH_ENABLED=true`.

Callback menolak token yang tidak memuat `Calendars.ReadWrite`.

## Environment

| Var | Default | Keterangan |
|---|---|---|
| `INTEGRATIONS_ENCRYPTION_KEY` | kosong | Kunci Fernet; isi di produksi |
| `TEAMS_NOTIFICATIONS_ENABLED` | `true` | `false` menghentikan antrean dan deteksi |
| `TEAMS_REQUEST_TIMEOUT` | `10` | Detik per request ke webhook |
| `TEAMS_DAILY_SUMMARY_HOUR` | `8` | Jam lokal paling awal ringkasan harian |
| `TEAMS_MILESTONE_DUE_DAYS` | `3` | Jendela "milestone mendekati tanggal" |
| `OUTLOOK_GRAPH_ENABLED` | `false` | Aktifkan Microsoft Graph Calendars |

## Batasan

- Pengiriman nyata ke Teams, consent Entra ID, dan pembuatan event Graph tidak bisa
  diuji tanpa tenant Microsoft; tes memakai mock `requests`/session.
- Kartu Teams tidak bisa me-*mention* pengguna Teams (butuh ID AAD); mention ditulis
  sebagai nama.
- Event "task blocked" bergantung pada notifikasi `task.status`; bila perubahan tidak
  menghasilkan penerima notifikasi (mis. hanya aktor sendiri), Teams tidak dikirimi.
- Tombol "Tambahkan ke kalender Outlook" ada di halaman Integrasi (task dan milestone
  30 hari ke depan), belum di halaman detail task/milestone.
