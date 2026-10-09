# Verification — Scope B

- Dua refinement awal dibandingkan sebelum B disetujui. Jalur utama 32 unit, radius 4 unit, celah tengah 16 unit, geometri simetris rotasi 180 derajat.
- Master kecil memakai koordinat pada grid 16 unit dan celah tengah 32 unit. Raster 16 px menunjukkan dua komponen terpisah dan celah transparan yang jelas.
- Versi putih utama ditipiskan 1 unit per sisi untuk mengurangi kesan terlalu berat pada latar gelap; versi kecil mempertahankan pixel grid.
- SVG audit: simbol utama/putih/kecil dan wordmark tanpa masalah. Lockup mengandung 166 anchor termasuk huruf outlined; hanya catatan kompleksitas, tidak ada error atau warning.
- Inspeksi render meliputi 16/24/32/64 px, black/white, primary/dark, blur, mirror, dan rotasi. Logo horizontal dicek pada 120 px; stacked pada preview branding.
- PNG dirender dengan latar transparan dan ukuran pasti. App icon square/Apple touch memakai latar opaque; maskable menempatkan seluruh tanda di lingkaran safe zone pusat 80%.
- Warna mengikuti DESIGN.md: violet #5b5bd6 dan violet terang #7c7cf0. Contrast numerik dan dimensi/alpha PNG dicatat di `validation.json`.
- Semua file hanya berisi arah B. Eksplorasi dan kit sebelumnya dihapus setelah paket ini selesai dan diverifikasi.

Hasil pemeriksaan aplikasi/PDF tersedia di `validation.json` setelah pemasangan.

## Pemeriksaan aplikasi

Enam tes ekspor PDF lulus; Django system check tanpa masalah; Ruff untuk modul ekspor lulus; CSS build lulus. Halaman login terang/gelap dirender dari template Django dan diinspeksi. Filter invert lama menghasilkan kuning pada logo violet; diperbaiki menjadi putih pada tema gelap.
