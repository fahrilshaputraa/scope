# Halaman Docs Scope

## Brief dan target desain

Dokumentasi dalam bahasa Indonesia untuk PM, anggota tim, manajemen, dan administrator. Masuk melalui Pengaturan → Docs. Menjelaskan fungsi Scope, alur penggunaan lengkap, aturan akses, dan batas perilaku aplikasi dengan contoh visual. Target langsung mengikuti shell dan token Scope dalam DESIGN.md; tidak membuat bahasa visual baru.

## Referensi dan keputusan sebelum implementasi

Refero search_styles (tiga arah: dokumentasi editorial, basis pengetahuan produktivitas, Linear) dan search_screens (artikel dengan daftar isi) pada 9 Oktober 2026 mengembalikan NO_SUBSCRIPTION. Tidak ada klaim inspeksi screenshot Refero. Referensi yang dipakai: DESIGN.md dan template aplikasi aktif sebagai sumber utama; craft typography.md dan craft-details.md dari refero-design sebagai pelengkap.

| Keputusan | Sumber | Aturan yang dipertahankan |
|---|---|---|
| Artikel dengan daftar topik, daftar isi, dan URL per topik | Permintaan lengkap + craft-details navigation | Dapat ditandai, dibagikan, dan digunakan dengan tombol Kembali |
| Submenu Akun / Docs di Pengaturan | Revisi pengguna: seperti menu Project | Menggunakan kembali project-sidebar dan project-nav-item; topik bersarang di bawah Docs; form akun tetap berfungsi |
| Inter, kanvas netral, hairline, aksen violet | DESIGN.md | Aksen hanya untuk tautan, navigasi aktif, fokus, dan data aktual |
| Teks utama maksimal sekitar 65–75 karakter per baris | Refero typography §line length | Artikel nyaman dibaca; tabel/visual boleh lebih lebar |
| Langkah bernomor, aturan, hasil, masalah umum | Alur aplikasi dan bahasa-indonesia/core.md | Bahasa Indonesia lugas; label tombol asli dipertahankan saat perlu dicari |
| Contoh HTML dan kalkulator progres berbobot | Permintaan visual + projects/services.py | Contoh diberi label, tanpa data pribadi, tanpa menyimpan perubahan |
| Pencarian seluruh isi di server | Isi panduan + craft-details navigation | Berfungsi tanpa JavaScript; URL merekam kueri |
| Responsif, tema gelap, cetak | DESIGN.md + craft-details focus/touch/anchors | Tabel bergulir lokal; navigasi dapat dibuka di ponsel; fokus terlihat |

## Cakupan yang ditelusuri

identity/views.py, urls.py, models.py, permissions.py: login, peran, cakupan membaca, pengaturan dan pembuatan akun. projects/views.py, services.py, forms.py, models.py serta template aktif: membuat proyek, anggota, tahap, milestone, baseline, snapshot, catatan, keputusan, aktivitas, portofolio. work/views.py, forms.py, models.py: task, dua penanggung jawab, dependensi, pembaruan harian, masalah, komentar dan lampiran. planning_views.py/planning_io.py: impor atomik, batas dan pencegahan impor identik. presentation_views.py, template setup dan docs/project-presentation.md: konfigurasi dan sesi presentasi.

Panduan pengguna tidak menjelaskan arsitektur kode atau perintah deployment. Perilaku belum tersedia, seperti ekspor PPT/PPTX dan proyeksi aktual masa depan, dijelaskan batasnya agar tidak menyesatkan.

## Implementasi dan pemeliharaan

Rute utama: `/auth/settings/docs/`. Artikel mempunyai URL `/auth/settings/docs/<slug>/` dan pencarian menggunakan `?q=...`. Semua halaman memerlukan login. Isi terstruktur berada di `apps/identity/documentation.py`; sesuaikan teks dan contoh ketika perilaku aplikasi berubah. Tidak ada migrasi maupun data proyek yang disalin ke panduan.

18 artikel mencakup pengenalan, panduan cepat, akses, proyek, anggota, task/Kanban/dependensi, pembaruan harian, baseline/jadwal, progres, masalah/risiko, tahap/milestone, catatan/keputusan/aktivitas, lampiran/komentar, impor AI, portofolio/laporan, presentasi, pengaturan, serta bantuan/istilah. Contoh HTML mengikuti token tema Scope; simulasi berbobot menunjukkan kontribusi bobot 1 dan 3, aktual 35%, rencana 60%, dan deviasi −25 poin.

Validasi: 128 tes pytest lulus, termasuk 28 tes Docs. Chrome memeriksa submenu Akun → Docs, 18 artikel pada lebar 390 px, pencarian termasuk keadaan kosong, slider melalui keyboard, pengaturan ulang, tema gelap, cetak, serta pencarian di server tanpa JavaScript. Pemeriksaan Django dan Ruff serta pembangunan CSS lulus. Pratinjau memakai database sementara yang terpisah dari data aplikasi.

QA visual: sumber utama DESIGN.md dan sidebar Project aktif; bukti tangkapan layar Chrome pada desktop 1440 × 1000 dan ponsel 390 × 844, tema terang/gelap, pencarian dan simulasi. Tipografi, jarak, token warna, fokus keyboard, navigasi aktif, keadaan kosong, serta cetak diperiksa. Pencarian angka/singkatan diperbaiki agar “10 MB” hanya menghasilkan panduan lampiran dan bantuan. Hasil akhir lulus tanpa temuan P0/P1/P2 yang tersisa.
