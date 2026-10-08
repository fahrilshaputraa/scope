# Presentasi project

Buka project → **Presentasi** → susun slide di drawer → **Mulai presentasi**. PM bisa mengubah judul, menyalakan/mematikan sumber, memilih detail PIC/jadwal/keterangan, mengurutkan melalui drag atau tombol naik/turun, dan menentukan rentang periode berikutnya. Mulai presentasi juga menyimpan perubahan susunan. Pengguna yang dapat melihat project bisa menjalankan susunan yang disimpan PM.

Slide awal: rencana vs progress, pekerjaan aktif, periode berikutnya, masalah terbuka, dan penutup. Kolom tambahan Kanban muncul sebagai sumber opsional. Setelah diaktifkan, kolom bisa diletakkan di posisi mana pun. Urutan disimpan per project; halaman lanjutan mengikuti posisi sumbernya.

## Sumber data

- Overview menggunakan kalkulasi project dan grafik baseline/snapshot yang sama dengan tab Progress. Actual berhenti pada data yang tercatat, tanpa mengarang proyeksi masa depan.
- Pekerjaan aktif: in progress, blocked, review. Status tetap ditulis dengan jelas.
- Periode berikutnya: pekerjaan belum selesai yang jadwalnya beririsan dengan tanggal pilihan, serta pekerjaan aktif yang masih perlu dilanjutkan. Backlog tanpa tanggal tidak ditampilkan.
- Rencana per task dihitung sampai hari ini, dari tanggal baseline jika tersedia, atau jadwal saat ini. Label jadwal/baseline tidak mengklaim tanggal actual yang belum disimpan aplikasi.
- Masalah terbuka menggunakan issue yang ada, critical/high lebih dahulu.
- Feedback merupakan kartu tersendiri, tanpa bobot progress. PM dapat menghubungkannya ke task yang menjadi tindak lanjut. Task yang ditempatkan pada kolom tambahan mempertahankan status, bobot, dan progress. Kembali ke kolom status menghapus pengelompokan tambahannya.

Slide mengambil data saat halaman presentasi dibuka. Seluruh sesi memakai HTML/data yang sama, tanpa polling. Untuk data baru, keluar dan mulai sesi baru. Ini snapshot sesi di browser, bukan arsip historis laporan. Timestamp ditampilkan di footer desktop.

## Navigasi & keterbacaan

Tombol sebelumnya/berikutnya, pemilih slide, panah keyboard, Page Up/Down, Home/End, dan swipe pada area non-tabel. Space maju jika tidak sedang fokus pada tombol/input. Escape keluar dari fullscreen; Escape berikutnya kembali ke halaman project. Native fullscreen memiliki fallback viewport. Mode Light/Dark/System menggunakan tema Scope yang tersimpan.

Maksimal enam task, tiga issue, atau empat item kolom per halaman. Keterangan panjang dipisah menjadi lanjutan tanpa menghilangkan teks; banyaknya teks juga mengurangi jumlah item per halaman. Pada layar pendek, isi slide dapat di-scroll. Tabel di mobile dapat di-scroll horizontal, tanpa memperlebar halaman.

## Referensi dan keputusan visual

Otoritas visual tetap DESIGN.md dan tema Scope, mengikuti keputusan Refero Ramp/Linear yang tercatat di `design-ramp-implementation.md` dan `ux-simplification.md`. Enam gambar presentasi dari pengguna dipakai untuk hierarki informasi: grafik sebagai overview besar, tabel pekerjaan, feedback, daftar issue, dan penutup. Warna beige, logo pihak lain, dan dekorasi gambar tersebut tidak diadopsi. Struktur tabel dan slide penutup mengadaptasi template HTML PPT `single-page/table.html` dan `single-page/thanks.html`; navigasi tetap komponen aplikasi.

Pengaturan membuka drawer dari halaman project. Urutan, pilihan isi, periode, dan tombol mulai berada dalam satu panel; validasi tetap di drawer. Simpan susunan mengembalikan pengguna ke project, sedangkan Mulai presentasi menyimpan lalu membuka player. Panel memakai permukaan dan tombol aplikasi. Player melepas sidebar untuk memberikan ruang penuh pada isi. Tipografi Inter 400, Ink/Paper/Bone/Ash, garis Hairline, dan kontrol eksplisit dipertahankan di kedua tema. Grafik presentasi tidak menganimasikan angka dari nol agar nilai langsung bisa dijelaskan.

## Verifikasi

100 tes backend lolos, termasuk izin akses, konfigurasi PM, isolasi project, perubahan kolom tanpa perubahan progress, feedback tanpa bobot, periode berikutnya, pagination, snapshot sesi, teks panjang, dan input rusak. Pemeriksaan CDP browser mencakup penyimpanan urutan, keyboard, native/fallback fullscreen, tema, mobile, dan drop task/feedback. Regresi browser timeline/fullscreen/drawer dan daily work juga lolos. Tampilan overview, ongoing, next period, feedback, penutup, dan mobile diperiksa melalui screenshot.

Tidak ada export PPT/PPTX pada fitur ini.
