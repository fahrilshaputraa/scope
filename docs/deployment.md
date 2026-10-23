# Deployment

Dokumen ini menjelaskan cara menjaga snapshot progress harian tetap terisi
tanpa bergantung pada cron manual. Pilih **salah satu** opsi: scheduler internal
atau timer eksternal. Keduanya memanggil service yang sama dan idempoten per
project per hari, sehingga aman dijalankan berulang atau dari beberapa worker.

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

## Verifikasi

```bash
python manage.py snapshot_progress --due
```

Output `Captured N due project snapshots.` menunjukkan jumlah project yang
belum punya snapshot hari ini. Menjalankannya lagi segera setelah itu akan
menghasilkan `Captured 0 due project snapshots.`.
