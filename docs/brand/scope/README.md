# Scope — logo B / Seimbang

Identitas disetujui pada 9 Oktober 2026. Dua jalur naik mewakili **rencana dan progres aktual**: dua jalur progres, satu pandangan. Gunakan B untuk seluruh branding Scope.

## Pilih file

| Kebutuhan | File |
|---|---|
| Header, laporan, dokumen berlatar terang | `scope-horizontal.svg` |
| Header atau dokumen berlatar gelap | `scope-horizontal-dark.svg` |
| Susunan vertikal | `scope-stacked.svg` / `scope-stacked-dark.svg` |
| Simbol saja, minimum 32 px | `scope-symbol-violet.svg` |
| Simbol putih di latar gelap, minimum 32 px | `scope-symbol-white.svg` |
| Simbol 16–24 px | `scope-symbol-small.svg` atau `assets/favicon-light.svg` / `assets/favicon-dark.svg` |
| Tulisan Scope saja | `scope-wordmark.svg` |
| PNG transparan | `renders/` atau `assets/` |
| Browser tab | `assets/favicon.svg` / `assets/favicon.ico` |
| App icon / avatar | `assets/scope-app-icon.svg` / `assets/scope-app-icon-1024.png` |
| Web icon, Apple touch, manifest | `assets/icon-*.png`, `assets/apple-touch-icon.png`, `assets/site.webmanifest` |

Semua master SVG memakai bentuk fill dan huruf outlined: tidak membutuhkan font, bitmap, atau filter. Versi hitam, putih, dan satu warna violet untuk setiap lockup tersedia di `assets/`. Favicon SVG menyesuaikan tema browser; favicon ICO memakai violet. Manifest memakai alamat ikon relatif dan perlu dipasang sesuai hosting aplikasi.

## Ruang dan ukuran

Jaga ruang kosong minimal **satu tebal jalur** di sekeliling batas gambar: 32 unit dari master simbol 256 unit. Pada simbol 32 px, ruang kosong minimum 4 px. Padding artboard boleh dihitung sebagai ruang kosong tersebut; jangan dipotong lalu menempelkan logo pada teks atau tepi.

Logo horizontal minimum **120 px** lebar; stacked minimum **80 px** lebar; simbol biasa minimum **32 px**. Untuk 16–24 px, gunakan versi kecil dengan celah 32 unit dan grid yang disesuaikan. Versi putih biasa memakai jalur 30 unit agar terasa sama beratnya pada latar gelap; versi kecil tetap 32 unit supaya stabil pada pixel grid.

## Warna

| Warna | HEX | RGB | CMYK perkiraan | Pemakaian |
|---|---|---|---|---|
| Violet | `#5B5BD6` | 91, 91, 214 | 57, 57, 0, 16 | Simbol utama, tile app icon |
| Violet terang | `#7C7CF0` | 124, 124, 240 | 48, 48, 0, 6 | Simbol pada latar gelap |
| Ink | `#111111` | 17, 17, 17 | 0, 0, 0, 93 | Wordmark / monokrom |
| Putih | `#FFFFFF` | 255, 255, 255 | 0, 0, 0, 0 | Logo reversed |
| Canvas | `#FBFBFA` | 251, 251, 250 | 0, 0, 0, 2 | Latar terang |

Pasangan utama: violet + ink di putih/canvas; violet terang + putih di ink/dark; putih di violet. CMYK adalah konversi numerik awal, bukan hasil profil cetak. Tentukan spot/Pantone lewat proof dan swatch fisik bila diperlukan.

## Tipografi dan pemakaian

Wordmark memakai **Roboto Medium**, sudah diubah menjadi path. Lisensi Apache 2.0 dan notice tersedia di `FONT-LICENSE.txt` dan `FONT-NOTICE.txt`. Interface tetap memakai **Inter** sesuai `DESIGN.md`. Gunakan file wordmark, jangan mengetik ulang tulisan Scope untuk mengganti logo.

Pertahankan proporsi dan susunan resmi; gunakan warna yang tercantum. Hindari meregangkan, memutar, memisahkan kedua jalur, menambah outline/gradient/bayangan, atau menaruh logo pada latar yang ramai. Tile app icon boleh mengikuti bentuk mask sistem operasi; gunakan `maskable-512.png` untuk crop maskable.

## Handover

`overview.png` merangkum identitas. `presentation.html` dan `board/` menunjukkan konteks aplikasi dan branding; domain dan kontak pada mockup adalah ilustrasi. `tests.html`, `tests.png`, dan `verification.md` mencatat pemeriksaan. Aset aplikasi tersedia di `static/brand/`; logo PDF memakai proporsi horizontal B. Konsep lain telah dibersihkan atas permintaan pengguna.

Paket ini tidak menyatakan clearance merek. Jika identitas akan didaftarkan, lakukan pencarian nama dan kemiripan melalui layanan merek profesional.
