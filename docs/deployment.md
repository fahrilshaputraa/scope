# Deployment

Dokumen ini menjelaskan cara menjaga snapshot progress harian tetap terisi
tanpa bergantung pada cron manual. Pilih **salah satu** opsi: scheduler internal
atau timer eksternal. Keduanya memanggil service yang sama dan idempoten per
project per hari, sehingga aman dijalankan berulang atau dari beberapa worker.

## Produksi dengan Docker

`Dockerfile` membangun CSS, menjalankan `collectstatic`, dan menjalankan gunicorn
sebagai user non-root dengan `config.settings.production`.
`docker-compose.yml` berisi tiga service: `db` (PostgreSQL), `web` (migrate +
gunicorn), dan `scheduler` (`manage.py run_scheduler`, tiap 5 menit menjalankan
snapshot `--due`, email notifikasi, dan digest).

```bash
cp .env.example .env     # isi DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS, SITE_URL, dst.
docker compose up -d --build
docker compose exec web python manage.py create_local_user admin --role admin --staff
```

Saat memakai service `scheduler`, biarkan `SCOPE_SCHEDULER_ENABLED=false`
agar tidak ada dua pemicu.

## Pengaturan produksi

- `config.settings.production` mengaktifkan `SECURE_SSL_REDIRECT`, cookie sesi dan
  CSRF `Secure`, HSTS, nosniff, dan log ke console. Semuanya bisa diubah lewat
  env `DJANGO_SECURE_*` (lihat `.env.example`).
- Di belakang reverse proxy TLS, set
  `DJANGO_SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https` dan pastikan proxy
  meneruskan header tersebut.
- `DJANGO_SECRET_KEY` wajib: aplikasi menolak start bila `DJANGO_DEBUG=false`
  dan nilainya kosong.
- Login dikunci 10 menit setelah 5 kegagalan per username+IP (cache Django;
  default per proses. Untuk banyak worker, konfigurasikan cache bersama seperti
  Redis/Memcached). `PCC_LOGIN_MAX_FAILURES` dan `PCC_LOGIN_LOCKOUT_SECONDS`
  mengatur batasnya.
- Tautan publik project punya opsi masa berlaku, kata sandi, dan sembunyikan
  judul task (tab Bagikan).
- CI (`.github/workflows/ci.yml`) menjalankan ruff, pytest, `makemigrations --check`,
  dan `check --deploy`.
- Volume `media` menyimpan lampiran; sertakan dalam backup bersama database.

## Cara kerja snapshot

- `record_snapshot(project)` melakukan upsert pada `(project, date)`, sehingga
  satu project hanya punya satu snapshot per tanggal.
- `snapshot_due_projects()` hanya memproses project aktif (bukan archived,
  completed, atau cancelled) yang belum punya snapshot untuk hari ini.
- Perintah `python manage.py snapshot_progress --due` memakai service tersebut.
  Tanpa `--due`, perilaku lama tetap: semua project aktif di-upsert ulang.

## Opsi 1 — Scheduler internal

Aktifkan lewat environment variable:

```bash
SCOPE_SCHEDULER_ENABLED=true
SCOPE_SCHEDULER_INTERVAL_MINUTES=60
```

Saat Django start, `ProjectsConfig.ready()` menyalakan satu daemon thread per
proses. Thread menunggu satu interval sebelum tick pertama, jadi inisialisasi
aplikasi tidak menyentuh database. Tick berikutnya berjalan setiap interval;
error database dicatat di log dan tidak mematikan thread.

Catatan:

- Cocok untuk deployment satu host. Dengan beberapa worker (mis. gunicorn),
  setiap proses punya thread sendiri; hasilnya tetap satu snapshot per hari
  karena pengecekan dan upsert bersifat idempoten.
- Pastikan hanya satu opsi aktif. Jangan menyalakan scheduler internal sekaligus
  systemd timer — tidak berbahaya, tetapi redundan.
- Default mati, termasuk saat test.
- Sejak B2, tick yang sama juga mengirim email notifikasi yang antre dan
  digest yang sudah jatuh tempo (harian sekali per hari, mingguan sekali per
  7 hari). Jadi menyalakan scheduler internal sudah mencakup delivery email;
  timer eksternal hanya perlu memanggil perintah email bila scheduler mati.

## Notifikasi email dan digest

Pengiriman email tidak pernah berjalan di dalam request web. Notifikasi masuk
antrean lewat kolom `Notification.emailed_at`; perintah berikut mengambil
antrean, mengirim, lalu menandainya sehingga aman dijalankan berulang:

```bash
python manage.py send_notification_emails
python manage.py send_notification_digest --frequency daily
python manage.py send_notification_digest --frequency weekly
```

- `send_notification_emails` hanya memproses user dengan preferensi in-app/email
  yang memilih **Mati** untuk digest. Satu email per notifikasi.
- `send_notification_digest --frequency daily|weekly` mengirim satu ringkasan
  per user, dikelompokkan per project, dan menghormati preferensi digest serta
  jendela waktunya. Notifikasi yang sudah pernah dikirim tidak dikirim ulang.
- `SITE_URL` dipakai untuk deep link absolut karena command tidak punya request.

Environment email:

```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL="Scope <no-reply@example.com>"
SITE_URL=https://scope.example.com
```

Default lokal memakai console backend sehingga email tercetak di stdout dan
tidak keluar dari host. Test memakai locmem backend.

## Opsi 2 — systemd timer

Contoh untuk deployment di `/opt/scope` dengan virtualenv `/opt/scope/.venv`.

`/etc/systemd/system/scope-snapshot.service`:

```ini
[Unit]
Description=Scope daily project snapshots
After=network.target postgresql.service

[Service]
Type=oneshot
User=scope
WorkingDirectory=/opt/scope
EnvironmentFile=/opt/scope/.env
ExecStart=/opt/scope/.venv/bin/python manage.py snapshot_progress --due
```

`/etc/systemd/system/scope-snapshot.timer`:

```ini
[Unit]
Description=Run Scope snapshot capture daily

[Timer]
OnCalendar=*-*-* 00:05:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
```

Aktifkan:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now scope-snapshot.timer
sudo systemctl list-timers scope-snapshot.timer
```

`Persistent=true` menjalankan tick yang terlewat setelah host hidup kembali.
`RandomizedDelaySec` menyebarkan beban antar deployment.

Bila scheduler internal dimatikan, tambahkan timer email berikut agar antrean
tetap terkirim:

`/etc/systemd/system/scope-notifications.service`:

```ini
[Unit]
Description=Scope notification email and digest delivery
After=network.target postgresql.service

[Service]
Type=oneshot
User=scope
WorkingDirectory=/opt/scope
EnvironmentFile=/opt/scope/.env
ExecStart=/opt/scope/.venv/bin/python manage.py send_notification_emails
ExecStart=/opt/scope/.venv/bin/python manage.py send_notification_digest --frequency daily
ExecStart=/opt/scope/.venv/bin/python manage.py send_notification_digest --frequency weekly
```

`/etc/systemd/system/scope-notifications.timer`:

```ini
[Unit]
Description=Run Scope notification delivery hourly

[Timer]
OnCalendar=hourly
Persistent=true
RandomizedDelaySec=120

[Install]
WantedBy=timers.target
```

Jalankan `sudo systemctl enable --now scope-notifications.timer`. Perintahnya
idempoten: digest harian hanya terkirim sekali per tanggal dan digest mingguan
sekali per 7 hari, meskipun timer berjalan setiap jam.

## Verifikasi

```bash
python manage.py snapshot_progress --due
```

Output `Captured N due project snapshots.` menunjukkan jumlah project yang
belum punya snapshot hari ini. Menjalankannya lagi segera setelah itu akan
menghasilkan `Captured 0 due project snapshots.`.
