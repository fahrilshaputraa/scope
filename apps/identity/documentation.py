"""Panduan pengguna Scope, berdasarkan alur aplikasi yang tersedia."""

import re


def section(key, title, *paragraphs, **content):
    return {"id": key, "title": title, "paragraphs": paragraphs, **content}


def article(slug, title, group, summary, sections, **content):
    return {
        "slug": slug,
        "title": title,
        "group": group,
        "summary": summary,
        "sections": sections,
        "audience": "Semua pengguna",
        **content,
    }


ARTICLES = (
    article(
        "mengenal-scope",
        "Mengenal Scope",
        "Mulai di sini",
        "Satu tempat untuk memahami kondisi proyek, pekerjaan tim, dan selisih rencana "
        "dengan hasil nyata.",
        [
            section(
                "apa-itu-scope",
                "Apa itu Scope?",
                "Scope adalah aplikasi internal untuk merencanakan dan memantau proyek. "
                "Manajer proyek menyusun pekerjaan, anggota tim memperbarui pelaksanaannya, "
                "dan manajemen membaca kondisi keseluruhan melalui ringkasan dan laporan.",
                "Gunakan Scope untuk menjawab: sudah sampai mana, apakah sesuai rencana, "
                "apa hambatannya, siapa yang mengerjakan, dan apa yang perlu dilakukan berikutnya.",
                visual="workspace",
                caption="Contoh ringkasan proyek. Angka dan nama di seluruh panduan adalah "
                "ilustrasi.",
            ),
            section(
                "cara-kerja",
                "Bagaimana informasi saling terhubung?",
                "Proyek menjadi wadah utama. Di dalamnya ada anggota, tahap, task, jadwal, "
                "milestone, masalah, risiko, catatan, dan keputusan. Task menyimpan pekerjaan "
                "beserta penanggung jawab, status, bobot, dan persentase kemajuannya.",
                "Jadwal yang disimpan sebagai baseline menjadi rencana pembanding. Pembaruan "
                "task membentuk progres aktual; ringkasan, grafik, dan laporan membaca "
                "data yang sama.",
                bullets=[
                    "Rencanakan: buat proyek, pilih anggota, susun task dan tanggalnya.",
                    "Tetapkan pembanding: simpan baseline setelah rencana siap.",
                    "Kerjakan: perbarui status, progres, hambatan, dan bukti pekerjaan.",
                    "Tinjau: bandingkan rencana dengan aktual, lalu tentukan tindak lanjut.",
                ],
                visual="workflow",
                caption="Alur utama dari perencanaan sampai peninjauan.",
            ),
            section(
                "peta-menu",
                "Temukan informasi melalui menu",
                table={
                    "headers": ["Menu aplikasi", "Kegunaan"],
                    "rows": [
                        [
                            "Dashboard",
                            "Ringkasan proyek yang dapat Anda akses dan kondisi portofolio.",
                        ],
                        ["Projects", "Cari proyek berdasarkan nama/kode dan buka ruang kerjanya."],
                        ["Laporan", "Bandingkan proyek dan unduh data laporan."],
                        [
                            "Pekerjaan saya",
                            "Task yang ditugaskan kepada Anda sebagai orang pertama atau rekan.",
                        ],
                        ["Masalah", "Telusuri masalah pada proyek yang dapat Anda akses."],
                        ["Jadwal", "Lihat rentang waktu beberapa proyek."],
                        ["Catatan", "Cari informasi tertulis lintas proyek yang dapat diakses."],
                        ["Pengaturan", "Perbarui akun dan buka dokumentasi ini."],
                    ],
                },
            ),
            section(
                "cara-membaca",
                "Cara memakai panduan ini",
                "Mulai dari Panduan cepat jika baru pertama kali menggunakan Scope. "
                "Untuk pekerjaan tertentu, pilih topik di daftar isi atau cari kata seperti "
                "anggota, baseline, lampiran, atau presentasi.",
                "Setiap panduan menjelaskan siapa yang boleh melakukan tindakan, langkahnya, "
                "hasil yang diharapkan, serta penyebab umum ketika sesuatu tidak berjalan. "
                "Contoh visual tidak menyimpan atau mengubah data proyek Anda.",
            ),
        ],
        related=["mulai-cepat", "akun-dan-akses", "progress-proyek"],
        action=("projects:dashboard", "Buka Dashboard"),
    ),
    article(
        "mulai-cepat",
        "Panduan cepat",
        "Mulai di sini",
        "Ikuti satu alur sederhana dari proyek baru sampai pembaruan dan laporan pertama.",
        [
            section(
                "alur-pertama",
                "Untuk manajer proyek",
                steps=[
                    "Buka Projects, pilih Buat project, lalu isi nama, target selesai, "
                    "dan anggota tim.",
                    "Buka proyek yang dibuat. Pilih Tambah task untuk membagi "
                    "pekerjaan menjadi hasil yang jelas.",
                    "Tetapkan penanggung jawab, tanggal mulai, tanggal selesai, dan "
                    "bobot task utama.",
                    "Buka Jadwal → Phase project → Simpan baseline jadwal setelah "
                    "tanggal semua task utama terisi.",
                    "Minta tim memperbarui pekerjaannya. Tinjau Ringkasan, Progress, "
                    "dan Masalah secara berkala.",
                    "Gunakan Presentasi untuk rapat atau Laporan untuk mengunduh data.",
                ],
                visual="workflow",
                caption="Urutan yang disarankan untuk proyek pertama.",
            ),
            section(
                "rutinitas-anggota",
                "Untuk anggota tim",
                steps=[
                    "Buka Pekerjaan saya dan cari task yang sedang dikerjakan atau perlu dimulai.",
                    "Pilih Update pada task yang menjadi tanggung jawab Anda.",
                    "Perbarui status dan progres. Jika terhambat, pilih Terhambat lalu "
                    "jelaskan alasannya.",
                    "Simpan pembaruan. Tambahkan komentar atau lampiran melalui detail "
                    "task jika perlu.",
                    "Laporkan masalah jika ada kendala yang memerlukan tindak lanjut tim.",
                ],
                callout=(
                    "Tidak menemukan task?",
                    "Minta PM menugaskan Anda sebagai penanggung jawab atau rekan. "
                    "Menjadi anggota proyek saja tidak membuat semua task muncul di "
                    "Pekerjaan saya.",
                ),
            ),
            section(
                "rutinitas-manajemen",
                "Untuk manajemen",
                steps=[
                    "Buka Dashboard atau Laporan untuk melihat proyek yang membutuhkan perhatian.",
                    "Bandingkan rencana, aktual, deviasi, serta tanggal target.",
                    "Buka proyek untuk memahami pekerjaan aktif, hambatan, dan "
                    "milestone berikutnya.",
                    "Baca catatan/keputusan atau jalankan presentasi yang telah disusun PM.",
                ],
                callout=(
                    "Mulai dari pertanyaan, bukan angka saja",
                    "Progres 60% belum menjelaskan apakah proyek sehat. "
                    "Bandingkan dengan rencana hari ini dan periksa hambatan serta tanggal target.",
                ),
            ),
        ],
        related=["membuat-proyek", "pembaruan-harian", "laporan-portofolio"],
    ),
    article(
        "akun-dan-akses",
        "Peran dan hak akses",
        "Mulai di sini",
        "Pahami perbedaan manajer proyek, anggota tim, manajemen, dan administrator.",
        [
            section(
                "masuk",
                "Masuk ke Scope",
                "Gunakan nama pengguna dan kata sandi akun lokal yang diberikan administrator. "
                "Jika tombol Masuk dengan Microsoft tersedia, organisasi juga "
                "mengaktifkan akses melalui Microsoft.",
                "Tidak ada kata sandi bawaan. Hubungi administrator jika belum punya "
                "akun atau lupa kata sandi.",
            ),
            section(
                "peran",
                "Apa yang boleh dilakukan setiap peran?",
                table={
                    "headers": ["Peran", "Akses utama"],
                    "rows": [
                        [
                            "Project Manager (PM)",
                            "Membuat proyek; mengelola proyek yang dipimpin, task, "
                            "jadwal, anggota, dan konfigurasi presentasi.",
                        ],
                        [
                            "Project Member",
                            "Membaca proyek yang terkait; memperbarui task "
                            "sendiri/sebagai rekan; melaporkan masalah dan menulis "
                            "komentar.",
                        ],
                        [
                            "Management",
                            "Membaca seluruh proyek, laporan, dan presentasi; tidak "
                            "mengubah pekerjaan atau memberi komentar.",
                        ],
                        [
                            "Administrator (staff)",
                            "Mengelola semua proyek dan membuat akun lokal melalui Pengaturan.",
                        ],
                    ],
                },
                callout=(
                    "Peran PM bukan akses edit ke semua proyek",
                    "PM mengelola proyek yang dipimpinnya. "
                    "Akses membaca proyek lain melalui keanggotaan atau penugasan "
                    "tidak otomatis memberikan hak mengelola.",
                ),
            ),
            section(
                "cakupan",
                "Mengapa proyek atau tombol tidak terlihat?",
                "Anggota dan PM dapat membaca proyek ketika menjadi manajer, anggota, "
                "orang yang ditugaskan "
                "pada task, atau rekan pengerjaan. Manajemen dan administrator dapat "
                "membaca seluruh proyek.",
                "Tombol perubahan mengikuti izin. Anggota yang ditugaskan pada task "
                "dapat memperbarui "
                "status dan progresnya, tetapi tidak mengubah bobot, penanggung jawab, "
                "atau jadwalnya.",
                bullets=[
                    "Jika proyek tidak ditemukan, minta PM memeriksa keanggotaan atau "
                    "penugasan Anda.",
                    "Jika tombol Tambah task tidak tersedia, pastikan Anda PM proyek "
                    "tersebut atau administrator.",
                    "Dokumentasi boleh dibaca semua pengguna yang sudah masuk; membaca "
                    "panduan tidak menambah hak akses.",
                ],
                visual="roles",
                caption="Izin membaca proyek berbeda dengan izin mengelola rencana dan "
                "memperbarui pekerjaan.",
            ),
        ],
        related=["anggota-tim", "pengaturan-akun", "pembaruan-harian"],
    ),
    article(
        "membuat-proyek",
        "Membuat dan mengelola proyek",
        "Rencanakan proyek",
        "Tambahkan proyek, isi informasi dasarnya, lalu susun pekerjaan dan tim yang "
        "akan menjalankannya.",
        [
            section(
                "buat",
                "Buat proyek pertama",
                steps=[
                    "Buka menu Projects. Pilih Buat project; tombol ini juga tersedia "
                    "dari Dashboard untuk PM.",
                    "Isi nama proyek dengan hasil yang ingin dicapai, misalnya "
                    "Peluncuran portal pelanggan.",
                    "Periksa target selesai dan pilih anggota tim yang akan mengerjakan proyek.",
                    "Buka Detail tambahan untuk informasi seperti kode, deskripsi, PM, "
                    "tim, tanggal mulai, dan status.",
                    "Pilih Simpan. Proyek akan terbuka dan siap diisi task, tahap, "
                    "milestone, serta catatan.",
                ],
                visual="project-form",
                caption="Contoh informasi awal proyek. Kode dibuat otomatis jika dikosongkan.",
            ),
            section(
                "isian",
                "Informasi yang perlu diperhatikan",
                table={
                    "headers": ["Informasi", "Cara mengisinya"],
                    "rows": [
                        ["Nama", "Gunakan nama yang membedakan hasil atau ruang lingkup proyek."],
                        [
                            "Kode",
                            "Boleh dikosongkan untuk kode otomatis; kode yang dipakai harus unik.",
                        ],
                        [
                            "Target selesai",
                            "Periksa tanggal yang disediakan otomatis dan sesuaikan "
                            "dengan komitmen proyek.",
                        ],
                        [
                            "Anggota",
                            "Pilih akun aktif. Anggota dapat ditambah atau diubah "
                            "setelah proyek dibuat.",
                        ],
                        [
                            "PM",
                            "PM biasa ditetapkan sebagai pengelola proyeknya; "
                            "administrator dapat memilih pengelola lain.",
                        ],
                        [
                            "Deskripsi dan tim",
                            "Tuliskan tujuan, batas pekerjaan, dan tim yang terlibat "
                            "agar konteks mudah dipahami.",
                        ],
                    ],
                },
            ),
            section(
                "ubah",
                "Ubah informasi proyek",
                "Buka proyek → Lainnya → Edit informasi project. Perbarui isian, lalu simpan. "
                "Tanggal target tidak boleh lebih awal daripada tanggal mulai.",
                "Status proyek dipilih PM untuk menggambarkan kondisi keseluruhan. Status tersebut "
                "berbeda dari label deviasi yang dihitung dari rencana dan aktual.",
                callout=(
                    "Persentase manual adalah pengecualian",
                    "Jika PM mengisi Penyesuaian progress PM (%), "
                    "angka itu dipakai sebagai aktual proyek, "
                    "menggantikan perhitungan task. "
                    "Kosongkan kembali untuk memakai progres berbobot task.",
                ),
            ),
            section(
                "setelah-dibuat",
                "Apa yang dilakukan setelah proyek dibuat?",
                bullets=[
                    "Tambahkan task dan tetapkan penanggung jawabnya.",
                    "Lengkapi tanggal task utama sebelum menyimpan baseline.",
                    "Gunakan tahap untuk mengelompokkan pekerjaan dan milestone untuk "
                    "menandai hasil penting.",
                    "Jadwalkan peninjauan rutin terhadap ringkasan, masalah, dan "
                    "pekerjaan berikutnya.",
                ],
            ),
        ],
        audience="PM proyek dan administrator",
        keywords="menambah project membuat project baru edit proyek",
        related=["anggota-tim", "task-kanban", "jadwal-baseline"],
        action=("projects:project_create", "Buat project"),
        manage_action=True,
    ),
    article(
        "anggota-tim",
        "Anggota dan penanggung jawab",
        "Rencanakan proyek",
        "Berikan akses proyek kepada tim dan tetapkan maksimal dua orang pada satu task.",
        [
            section(
                "anggota",
                "Tambahkan anggota proyek",
                steps=[
                    "Buka proyek yang Anda kelola.",
                    "Pilih Lainnya → Atur anggota tim.",
                    "Cari nama atau nama pengguna, lalu centang anggota yang diperlukan.",
                    "Periksa jumlah dan daftar pilihan sebelum menyimpan.",
                ],
                paragraphs=[
                    "Anggota yang dipilih memperoleh akses membaca proyek. Penugasan task tetap "
                    "ditetapkan secara terpisah; keanggotaan tidak berarti semua orang "
                    "boleh mengedit setiap task."
                ],
                visual="members",
                caption="Contoh pemilihan anggota dengan pencarian dan kotak centang.",
            ),
            section(
                "dua-orang",
                "Tetapkan orang pertama dan rekan",
                "Saat membuat atau mengedit task, isi Dikerjakan oleh untuk orang pertama. "
                "Tambahkan satu orang berbeda pada Rekan pengerjaan jika pekerjaan "
                "dilakukan berdua.",
                bullets=[
                    "Maksimal satu rekan: total dua orang per task.",
                    "Pilih orang pertama sebelum memilih rekan.",
                    "Orang pertama dan rekan harus berbeda.",
                    "Keduanya dapat memperbarui task sesuai hak aksesnya; bobot task "
                    "tetap dihitung sekali.",
                    "Jika nama tidak tersedia, periksa apakah akun aktif dan terkait "
                    "dengan proyek.",
                ],
                callout=(
                    "Nama tidak muncul?",
                    "Tambahkan orang tersebut ke anggota proyek dahulu, "
                    "lalu buka kembali form task. Penanggung jawab dapat dipilih dari "
                    "pengguna yang terkait dengan proyek.",
                ),
            ),
            section(
                "ubah-anggota",
                "Ketika tim berubah",
                "Perbarui keanggotaan dan penugasan secara terpisah. Menghapus seseorang dari "
                "daftar anggota tidak otomatis menghapusnya dari task; penugasan yang masih ada "
                "juga dapat memberikan akses membaca proyek. Periksa keduanya sebelum "
                "menganggap akses telah berakhir.",
            ),
        ],
        audience="PM proyek dan administrator",
        related=["akun-dan-akses", "task-kanban"],
    ),
    article(
        "task-kanban",
        "Task, Kanban, dan dependensi",
        "Rencanakan proyek",
        "Uraikan proyek menjadi pekerjaan, susun alurnya, dan bedakan task dari kartu umpan balik.",
        [
            section(
                "buat-task",
                "Tambahkan task",
                steps=[
                    "Buka proyek → Tambah task.",
                    "Isi judul yang menyebut pekerjaan atau hasil, misalnya Siapkan "
                    "rancangan halaman masuk.",
                    "Pilih orang pertama, rekan jika perlu, dan tanggal selesai. Task "
                    "juga boleh dibuat tanpa penanggung jawab.",
                    "Buka Detail tambahan untuk tanggal mulai, tahap, milestone, "
                    "prioritas, bobot, label, dan dependensi.",
                    "Simpan. Task muncul pada alur kerja proyek sesuai statusnya.",
                ],
                visual="kanban",
                caption="Contoh sebagian kolom Kanban. Status lengkap juga mencakup belum "
                "dijadwalkan, terhambat, dan menunggu pemeriksaan.",
            ),
            section(
                "status",
                "Baca dan pindahkan status pekerjaan",
                table={
                    "headers": ["Status", "Kapan digunakan"],
                    "rows": [
                        [
                            "Belum dijadwalkan",
                            "Pekerjaan sudah diketahui, tetapi belum siap dijadwalkan.",
                        ],
                        ["Siap dikerjakan", "Pekerjaan siap dimulai setelah prasyarat terpenuhi."],
                        ["Sedang dikerjakan", "Pekerjaan sedang berlangsung."],
                        ["Terhambat", "Pekerjaan tertahan; alasan hambatan wajib diisi."],
                        [
                            "Menunggu pemeriksaan",
                            "Hasil perlu diperiksa sebelum dinyatakan selesai.",
                        ],
                        ["Selesai", "Pekerjaan selesai; progres otomatis menjadi 100%."],
                    ],
                },
                paragraphs=[
                    "Gunakan seret kartu atau pembaruan status melalui task. Jika "
                    "berpindah ke Terhambat, "
                    "isi alasan melalui pembaruan pekerjaan. Pengguna hanya dapat "
                    "memindahkan task yang boleh dieditnya."
                ],
            ),
            section(
                "dependensi",
                "Hubungkan pekerjaan yang saling bergantung",
                "PM dapat memilih task lain dalam proyek yang sama sebagai dependensi. "
                "Misalnya, pengujian baru dimulai setelah pembangunan fitur selesai.",
                bullets=[
                    "Task tidak dapat menjadi Sedang dikerjakan atau Selesai jika ada "
                    "dependensi yang belum Selesai.",
                    "Dependensi dan induk task tidak boleh membentuk lingkaran.",
                    "Subtask membantu merinci pekerjaan, tetapi tidak ditambahkan lagi "
                    "dalam progres total proyek.",
                    "Perbarui progres task induk secara langsung; progres subtask "
                    "tidak otomatis menaikkan induknya.",
                ],
            ),
            section(
                "kolom-tambahan",
                "Kolom tambahan dan umpan balik",
                "PM dapat membuat kolom tambahan, misalnya untuk Feedback. Task yang dipindahkan "
                "ke kolom tambahan mempertahankan status, bobot, dan progresnya; "
                "penempatan kolom hanya mengelompokkan pekerjaan.",
                "Kartu umpan balik merupakan catatan tindak lanjut tanpa bobot progres. "
                "Hubungkan kartu itu ke task jika tindak lanjutnya sudah menjadi pekerjaan nyata. "
                "Mengembalikan task ke kolom status melepaskan pengelompokan tambahannya.",
            ),
        ],
        related=["pembaruan-harian", "progress-proyek", "presentasi-proyek"],
    ),
    article(
        "pembaruan-harian",
        "Memperbarui pekerjaan harian",
        "Kerjakan bersama",
        "Perbarui status, progres, dan hambatan tanpa mengubah rencana kerja.",
        [
            section(
                "update",
                "Kirim pembaruan pekerjaan",
                steps=[
                    "Buka Pekerjaan saya dan pilih Update pada task yang ingin diperbarui. "
                    "Pembaruan juga dapat dibuka dari task atau batang pada jadwal proyek.",
                    "Pilih status yang sesuai dengan kondisi terbaru.",
                    "Isi progres 0–100 berdasarkan hasil yang sudah selesai.",
                    "Jika terhambat, jelaskan alasan dan pihak atau pekerjaan yang masih ditunggu.",
                    "Simpan pembaruan. Panel ditutup dan Anda tetap berada pada halaman pekerjaan.",
                ],
                visual="daily-update",
                caption="Contoh panel pembaruan. Perubahan pada ilustrasi tidak memengaruhi "
                "task nyata.",
            ),
            section(
                "yang-berubah",
                "Apa yang ikut berubah?",
                "Status dan progres task disimpan. Progres proyek dihitung ulang berdasarkan bobot "
                "task utama, kecuali PM menggunakan pengganti progres manual. Pembaruan task juga "
                "memperbarui catatan progres untuk hari itu.",
                "Panel pembaruan harian berfokus pada status, progres, dan hambatan. PM memakai "
                "form edit lengkap ketika perlu mengubah jadwal, penanggung jawab, atau bobot.",
            ),
            section(
                "aturan",
                "Hal yang perlu diingat",
                bullets=[
                    "Status Selesai selalu bernilai 100%. Ubah statusnya terlebih "
                    "dahulu jika pekerjaan perlu dibuka kembali.",
                    "Mengembalikan status dari Selesai tidak otomatis menurunkan angka "
                    "100%; sesuaikan progresnya juga.",
                    "Angka 100% tidak otomatis mengubah status menjadi Selesai; periksa keduanya.",
                    "Progres tidak boleh di luar rentang 0–100.",
                    "Alasan hambatan wajib terisi untuk status Terhambat.",
                    "Jika dependensi belum selesai, selesaikan prasyarat sebelum "
                    "memulai atau menyelesaikan task.",
                ],
                callout=(
                    "Buat pembaruan yang bisa ditindaklanjuti",
                    "Daripada menulis ‘menunggu’, "
                    "tulis apa yang ditunggu, siapa yang bisa membantu, dan tindakan berikutnya. "
                    "Catat masalah terpisah jika hambatan perlu dikelola bersama.",
                ),
            ),
        ],
        audience="Penanggung jawab task, rekan, PM proyek, dan administrator",
        related=["masalah-risiko", "komentar-lampiran", "progress-proyek"],
        action=("work:my_tasks", "Buka Pekerjaan saya"),
    ),
    article(
        "jadwal-baseline",
        "Jadwal dan baseline",
        "Rencanakan proyek",
        "Bandingkan jadwal kerja saat ini dengan rencana awal yang telah disepakati.",
        [
            section(
                "jadwal",
                "Baca jadwal proyek",
                "Buka proyek → Jadwal. Setiap bar menunjukkan rentang task; penanda hari ini "
                "membantu melihat pekerjaan aktif. Gunakan Seluruh project, Lebih "
                "dekat, atau Hari ini "
                "untuk mengatur tampilan. Tombol layar penuh memberi ruang lebih besar.",
                "Klik task atau bar untuk memperbarui pekerjaan. Perubahan tanggal dilakukan PM "
                "melalui pengaturan rencana, bukan oleh anggota saat mengirim pembaruan harian.",
                visual="timeline",
                caption="Ilustrasi: tanggal akhir task bergeser dari 12 ke 15 Oktober, selisih "
                "tiga hari dari baseline.",
            ),
            section(
                "simpan-baseline",
                "Simpan baseline jadwal",
                steps=[
                    "Isi tanggal mulai dan selesai semua task utama. Total bobotnya "
                    "harus lebih besar dari nol.",
                    "Buka Jadwal → Phase project.",
                    "Pilih Simpan baseline jadwal, lalu baca konfirmasi sebelum menyetujui.",
                    "Scope menyimpan tanggal pembanding dan menyusun kurva progres "
                    "rencana berbobot.",
                    "Buka Progress untuk melihat perbandingan rencana dan aktual.",
                ],
                callout=(
                    "Baseline lama diganti",
                    "Menyimpan baseline lagi mengganti tanggal baseline "
                    "task dan kurva rencana sebelumnya. Lakukan hanya ketika rencana "
                    "baru telah disepakati, "
                    "bukan untuk menyembunyikan keterlambatan.",
                ),
            ),
            section(
                "perbandingan",
                "Bedakan jadwal dan tanggal aktual",
                "Jadwal saat ini adalah tanggal pekerjaan yang direncanakan sekarang. Baseline "
                "adalah tanggal pembanding yang dibekukan sebelumnya. Buka Perubahan "
                "tanggal dari baseline "
                "untuk melihat pergeserannya.",
                "Lapisan aktual pada bar menunjukkan persentase kemajuan pekerjaan. "
                "Bar tersebut tidak mengklaim waktu aktual mulai bekerja atau total "
                "jam yang dihabiskan.",
            ),
            section(
                "baseline-manual",
                "Alternatif: titik baseline manual",
                "Di tab Progress, PM dapat menambahkan titik rencana berdasarkan "
                "tanggal dan persentase. "
                "Tanggal harus unik, angka berada dalam rentang 0–100, dan persentase "
                "tidak menurun "
                "dibanding titik sebelum/sesudahnya. Scope menghitung nilai di antara "
                "titik secara bertahap.",
                "Titik kurva manual tidak membekukan tanggal setiap task. Untuk "
                "membandingkan tanggal "
                "task, gunakan Simpan baseline jadwal.",
            ),
        ],
        related=["task-kanban", "progress-proyek", "tahap-milestone"],
    ),
    article(
        "progress-proyek",
        "Rencana, aktual, dan deviasi",
        "Pantau dan laporkan",
        "Pahami asal persentase proyek dan cara membaca selisihnya dengan rencana.",
        [
            section(
                "angka",
                "Tiga angka yang perlu dibaca bersama",
                table={
                    "headers": ["Angka", "Makna"],
                    "rows": [
                        [
                            "Rencana",
                            "Persentase yang seharusnya dicapai hari ini menurut kurva baseline.",
                        ],
                        [
                            "Aktual (Actual)",
                            "Kemajuan nyata dari task utama berbobot, atau nilai "
                            "manual yang ditetapkan PM.",
                        ],
                        [
                            "Deviasi",
                            "Aktual dikurangi rencana, dalam poin persentase. Nilai "
                            "negatif berarti tertinggal.",
                        ],
                    ],
                },
                paragraphs=[
                    "Contoh: rencana 60% dan aktual 40% berarti deviasi −20 poin persentase. "
                    "Itu bukan persentase keterlambatan hari atau prediksi tanggal selesai."
                ],
            ),
            section(
                "bobot",
                "Mengapa progres bukan rata-rata biasa?",
                "Task utama dengan bobot lebih besar memberi pengaruh lebih besar. "
                "Rumusnya: jumlah (progres task × bobot task) dibagi total bobot. "
                "Jika semua bobot sama, hasilnya sama dengan rata-rata progres.",
                "Subtask tidak dihitung lagi. Task berbobot nol tidak menambah hasil perhitungan; "
                "jika total bobot nol atau belum ada task, hasilnya 0%. Task Selesai "
                "menyumbang 100%.",
                visual="progress",
                caption="Simulasi interaktif dua task. Geser progres untuk melihat perubahan "
                "aktual dan deviasi.",
                callout=(
                    "Tidak berubah setelah task diperbarui?",
                    "Periksa apakah task merupakan "
                    "subtask, bobotnya nol, atau proyek memakai pengganti progres manual. "
                    "Dua orang pada satu task tidak menggandakan bobotnya.",
                ),
            ),
            section(
                "grafik",
                "Membaca grafik rencana vs aktual",
                "Garis rencana memakai garis putus-putus dengan titik kosong; aktual memakai "
                "garis solid berwarna aksen. Perhatikan posisi kedua garis pada tanggal yang sama. "
                "Gunakan kontrol rentang, pembesaran, atau layar penuh untuk meninjau detail.",
                "Tanpa baseline, rencana dan deviasi belum dapat dihitung. Itu bukan deviasi nol. "
                "Aktual masa depan tidak diproyeksikan: grafik menggunakan pembaruan "
                "dan data progres yang tercatat.",
                "Label kondisi deviasi mengikuti ambang yang ditetapkan aplikasi. "
                "Status proyek tetap pilihan PM; proyek berstatus Selesai tidak "
                "otomatis membuat setiap task selesai.",
            ),
            section(
                "snapshot",
                "Riwayat progres dan snapshot",
                "Perubahan task atau proyek memperbarui snapshot hari itu. Beberapa perubahan "
                "pada hari yang sama memperbarui satu baris, bukan membuat baris baru "
                "untuk setiap perubahan.",
                "PM dapat memilih Snapshot hari ini pada tab Progress. Tanggal tanpa pembaruan "
                "belum tentu memiliki snapshot, kecuali pencatatan harian telah "
                "diaktifkan administrator. "
                "Jangan menganggap garis penghubung antar titik sebagai bukti "
                "pembaruan setiap hari.",
            ),
        ],
        related=["jadwal-baseline", "pembaruan-harian", "laporan-portofolio"],
    ),
    article(
        "masalah-risiko",
        "Masalah, hambatan, dan risiko",
        "Kerjakan bersama",
        "Catat kendala yang sudah terjadi dan siapkan mitigasi untuk hal yang mungkin terjadi.",
        [
            section(
                "bedakan",
                "Pilih tempat mencatat yang tepat",
                table={
                    "headers": ["Jenis", "Contoh", "Tempat mencatat"],
                    "rows": [
                        [
                            "Hambatan task",
                            "Pengujian tertahan karena lingkungan uji belum siap.",
                            "Status Terhambat dan alasan pada task.",
                        ],
                        [
                            "Masalah (issue)",
                            "Akses ke lingkungan uji gagal dan perlu diperbaiki.",
                            "Masalah proyek, bisa dikaitkan dengan task.",
                        ],
                        [
                            "Risiko",
                            "Jadwal pemasok mungkin mundur minggu depan.",
                            "Risiko proyek beserta mitigasinya.",
                        ],
                    ],
                },
                paragraphs=[
                    "Mengubah task menjadi Terhambat tidak otomatis membuat masalah baru. "
                    "Catat masalah ketika kendala memerlukan pemilik, prioritas, dan "
                    "penyelesaian yang dipantau."
                ],
            ),
            section(
                "laporkan",
                "Laporkan masalah",
                steps=[
                    "Buka menu Masalah → Laporkan masalah, atau pilih tindakan yang "
                    "tersedia pada proyek.",
                    "Pilih proyek yang dapat diakses, lalu tulis judul dan penjelasan masalah.",
                    "Tentukan tingkat keparahan dan hubungkan task jika masalah "
                    "terkait pekerjaan tertentu.",
                    "Simpan. PM dapat menetapkan pemilik, target, status, dan penyelesaian.",
                ],
                visual="issue",
                caption="Contoh masalah dengan pemilik, tingkat keparahan, dan tindakan "
                "penyelesaian.",
            ),
            section(
                "tangani",
                "Tindak lanjuti sampai selesai",
                "Gunakan status Terbuka, Sedang dikerjakan, Terhambat, Diselesaikan, atau Ditutup "
                "sesuai kondisi. PM proyek atau administrator dapat memperbarui penanganannya; "
                "anggota melaporkan masalah tanpa menetapkan penyelesaian dan pemilik.",
                "Tulis penyelesaian yang menjelaskan tindakan dan hasilnya. Menyelesaikan masalah "
                "tidak otomatis membuka task yang berstatus Terhambat; perbarui task terkait juga.",
                "Masalah kritis dan tinggi ditampilkan lebih dahulu pada proyek. Filter keparahan "
                "membantu memusatkan perhatian pada masalah yang perlu segera ditangani.",
            ),
            section(
                "risiko",
                "Kelola risiko sebelum menjadi masalah",
                "Buka Masalah proyek → Risiko project → Tambah risiko. PM mencatat judul, "
                "tingkat keparahan, pemilik, target, dan mitigasi. Perbarui status "
                "ketika risiko ditangani "
                "atau ditutup. Risiko dan masalah merupakan catatan terpisah.",
            ),
        ],
        related=["pembaruan-harian", "catatan-keputusan"],
        action=("work:issue_list", "Buka Masalah"),
    ),
    article(
        "tahap-milestone",
        "Tahap dan milestone",
        "Rencanakan proyek",
        "Kelompokkan pekerjaan menjadi tahap dan tandai hasil penting yang harus dicapai.",
        [
            section(
                "tahap",
                "Susun tahap proyek",
                "Tahap (phase) mengelompokkan task, misalnya Persiapan, Pengembangan, "
                "dan Pengujian. "
                "PM membuka proyek → Lainnya → Tambah tahap project, kemudian mengisi "
                "nama, urutan, "
                "rentang tanggal, dan status. Tahap juga dapat dikelola dari Jadwal → "
                "Phase project.",
                "Urutan tahap harus unik dalam proyek. Pilih tahap pada form task "
                "untuk menghubungkan "
                "pekerjaan dengannya. PM dapat memilih tahap aktif melalui informasi proyek; "
                "jika belum ditetapkan, aplikasi memakai tahap belum selesai dengan "
                "urutan terkecil. "
                "Jika semua tahap selesai, tahap terakhir yang ditampilkan.",
                visual="milestones",
                caption="Contoh tahap pekerjaan dan hasil penting pada akhir tahap.",
            ),
            section(
                "milestone",
                "Tambahkan milestone",
                steps=[
                    "Buka proyek → Lainnya → Tambah milestone, atau buka bagian Milestones.",
                    "Tulis nama hasil penting, tanggal target, pemilik, status, dan "
                    "penjelasan jika perlu.",
                    "Simpan, lalu hubungkan task melalui pilihan milestone di form "
                    "task jika relevan.",
                    "Perbarui status milestone ketika hasilnya tercapai atau targetnya "
                    "perlu ditinjau.",
                ],
                paragraphs=[
                    "Milestone menandai hasil penting; ia tidak menambah bobot progres. "
                    "Task terkait yang selesai juga tidak otomatis mengubah status milestone."
                ],
            ),
            section(
                "beda",
                "Tahap, milestone, dan task memiliki fungsi berbeda",
                bullets=[
                    "Tahap: kelompok pekerjaan dalam satu bagian proyek.",
                    "Milestone: hasil atau titik penting dengan tanggal target.",
                    "Task: pekerjaan yang dikerjakan orang dan memiliki progres.",
                    "Perbarui status masing-masing sesuai kondisi; perubahan satu "
                    "jenis tidak otomatis menuntaskan yang lain.",
                ],
                callout=(
                    "Sebelum menghapus milestone",
                    "Pastikan keterkaitan task sudah dipahami. "
                    "Penghapusan menghilangkan milestone dari proyek; task yang "
                    "terhubung tetap ada.",
                ),
            ),
        ],
        audience="PM proyek dan administrator",
        related=["task-kanban", "jadwal-baseline"],
    ),
    article(
        "catatan-keputusan",
        "Catatan, keputusan, dan aktivitas",
        "Kerjakan bersama",
        "Simpan konteks pekerjaan, alasan keputusan, dan jejak perubahan yang mudah ditelusuri.",
        [
            section(
                "catatan",
                "Tulis catatan proyek",
                steps=[
                    "Buka proyek → Catatan → Tulis catatan, atau pilih Lainnya → Tulis catatan.",
                    "Isi judul, isi catatan, dan tag jika diperlukan.",
                    "Gunakan pemformatan teks untuk memisahkan konteks, temuan, dan "
                    "tindakan berikutnya.",
                    "Simpan. Catatan muncul dalam daftar bertanggal bersama keputusan.",
                ],
                paragraphs=[
                    "Catatan cocok untuk hasil diskusi, informasi teknis, atau konteks yang perlu "
                    "dibaca kembali. PM proyek dan administrator dapat membuat, "
                    "mengedit, dan menghapus catatan."
                ],
                visual="notes",
                caption="Contoh catatan dan keputusan yang tampil dalam urutan waktu.",
            ),
            section(
                "keputusan",
                "Catat keputusan beserta alasannya",
                "Pada bagian Catatan, pilih Catat keputusan. Isi judul, pilihan yang disepakati, "
                "pengambil keputusan, serta konteks, alasan, dan dampak bila diperlukan.",
                "Tuliskan keputusan secara eksplisit, misalnya ‘Rilis pertama mencakup "
                "login lokal; "
                "integrasi tambahan dijadwalkan setelah pengujian’. Simpan alasannya "
                "agar tim tidak "
                "mengulang pembahasan yang sama.",
            ),
            section(
                "temukan",
                "Cari konteks dan telusuri perubahan",
                "Gunakan filter Semua, Catatan, atau Keputusan pada proyek. Menu Catatan global "
                "membantu mencari judul, isi, atau tag pada proyek yang dapat Anda akses.",
                "Bagian Aktivitas menunjukkan peristiwa perubahan seperti pembuatan task, "
                "perubahan status, dan pembaruan rencana. Aktivitas adalah jejak peristiwa; "
                "catatan dan keputusan tetap tempat untuk penjelasan yang ingin "
                "disampaikan kepada tim.",
            ),
        ],
        related=["komentar-lampiran", "masalah-risiko"],
        action=("projects:note_list", "Buka Catatan"),
    ),
    article(
        "komentar-lampiran",
        "Komentar dan lampiran",
        "Kerjakan bersama",
        "Tambahkan percakapan dan bukti pekerjaan pada task yang tepat.",
        [
            section(
                "komentar",
                "Tambahkan komentar",
                steps=[
                    "Buka detail task dari judul pekerjaan.",
                    "Temukan bagian Comments, tulis informasi yang relevan, lalu kirim.",
                    "Gunakan komentar untuk perkembangan singkat, pertanyaan, atau "
                    "penjelasan hasil.",
                ],
                paragraphs=[
                    "Pengguna non-manajemen yang dapat membaca proyek boleh menulis komentar. "
                    "Komentar tidak mengubah progres; kirim pembaruan status/progres "
                    "secara terpisah."
                ],
            ),
            section(
                "lampiran",
                "Unggah dan unduh lampiran",
                steps=[
                    "Buka detail task → Lampiran → Tambah lampiran.",
                    "Pilih berkas dengan ukuran maksimal 10 MB per berkas, lalu pilih Unggah.",
                    "Klik nama lampiran untuk mengunduhnya. Periksa hasil pekerjaan "
                    "sebelum menandai task selesai.",
                ],
                paragraphs=[
                    "Mengunggah atau menghapus lampiran memerlukan hak mengedit task. "
                    "Mengunduh memerlukan akses membaca proyek. Pengguna yang tidak memiliki akses "
                    "proyek tidak dapat mengambil lampiran hanya dengan mengetahui tautannya."
                ],
                visual="attachment",
                caption="Contoh bukti pekerjaan yang dilampirkan pada satu task.",
            ),
            section(
                "praktik",
                "Jaga konteks dan versi berkas",
                bullets=[
                    "Pakai nama berkas yang menyebut isi dan versi, misalnya hasil-uji-v2.pdf.",
                    "Sertakan komentar singkat yang menjelaskan apa yang berubah atau "
                    "perlu diperiksa.",
                    "Jika berkas terlalu besar, kompres atau bagi menjadi beberapa "
                    "berkas yang tetap mudah dipahami.",
                    "Menghapus lampiran menghilangkannya dari task; pastikan berkas "
                    "memang tidak diperlukan lagi.",
                ],
            ),
        ],
        related=["pembaruan-harian", "catatan-keputusan"],
    ),
    article(
        "impor-rencana-ai",
        "Mengimpor rencana dari AI",
        "Rencanakan proyek",
        "Gunakan templat JSON untuk membuat proyek beserta rencananya atau menambahkan "
        "pekerjaan baru.",
        [
            section(
                "mulai",
                "Pilih tujuan impor",
                "Untuk proyek baru, pilih Import dari AI pada Dashboard atau Projects. "
                "Untuk proyek yang sudah ada, buka proyek → Lainnya → Import rencana dari AI. "
                "PM hanya dapat mengimpor ke proyek yang dikelolanya.",
                visual="import",
                caption="Templat → rencana dari AI → berkas JSON → validasi → data proyek.",
            ),
            section(
                "langkah",
                "Siapkan dan unggah rencana",
                steps=[
                    "Pilih Unduh template JSON. Templat menyertakan petunjuk dan nama "
                    "pengguna yang tersedia.",
                    "Kirim templat ke AI bersama tujuan, ruang lingkup, tanggal, dan "
                    "pembagian tugas yang diinginkan.",
                    "Minta AI mempertahankan version 1, nama isian, serta kunci "
                    "penghubung tahap, milestone, dan task.",
                    "Tinjau judul, tanggal, bobot, penanggung jawab, dependensi, dan "
                    "batas pekerjaan sebelum menyimpan JSON.",
                    "Pilih berkas pada File JSON dari AI. Jika ingin menjadikannya "
                    "baseline, buka Pengaturan tambahan dan centang opsinya.",
                    "Pilih Import rencana. Jika berhasil, proyek dan isi rencana "
                    "ditampilkan; jika gagal, perbaiki sesuai pesan.",
                ],
                callout=(
                    "AI membantu menyusun, Anda tetap meninjau",
                    "Scope membaca berkas yang Anda unggah. "
                    "Rencana tidak dikirim ke AI secara otomatis oleh halaman impor.",
                ),
            ),
            section(
                "aturan",
                "Aturan berkas dan perilaku penyimpanan",
                bullets=[
                    "Maksimal 2 MB, 100 tahap, 100 milestone, dan 500 task per impor.",
                    "Gunakan tanggal YYYY-MM-DD dan nama pengguna akun yang tersedia.",
                    "Minimal ada satu tahap, milestone, atau task; rencana tidak boleh kosong.",
                    "Anggota dan penanggung jawab menggunakan akun yang ada; impor "
                    "tidak membuat akun baru.",
                    "Data baru ditambahkan. Impor tidak mengedit atau menghapus "
                    "rencana yang sudah ada.",
                    "Berkas identik tidak menambahkan task ganda pada proyek yang sama.",
                    "Jika ada isian atau hubungan yang tidak valid, seluruh perubahan "
                    "impor dibatalkan.",
                    "Opsi baseline memerlukan tanggal lengkap pada seluruh task utama; "
                    "baseline lama dapat diganti.",
                ],
                callout=(
                    "Mengimpor ulang berkas yang berbeda",
                    "Berkas yang diubah dianggap impor baru "
                    "dan bisa menambahkan pekerjaan baru. Jangan memakai impor sebagai "
                    "cara mengedit task yang sudah ada.",
                ),
            ),
            section(
                "lanjut",
                "Lanjutkan perencanaan yang sudah ada",
                "Pada panel impor proyek, pilih Export rencana saat ini untuk mengunduh JSON. "
                "Gunakan sebagai konteks diskusi lanjutan dengan AI. Terapkan perbaikan task lama "
                "melalui form edit; unggah rencana baru hanya ketika memang ingin "
                "menambahkan data.",
            ),
        ],
        audience="PM proyek dan administrator",
        keywords="import json AI template export rencana",
        related=["membuat-proyek", "jadwal-baseline", "task-kanban"],
        action=("projects:plan_import_new", "Import dari AI"),
        manage_action=True,
    ),
    article(
        "laporan-portofolio",
        "Laporan dan portofolio",
        "Pantau dan laporkan",
        "Lihat gambaran lintas proyek, temukan pengecualian, dan unduh laporan yang dibutuhkan.",
        [
            section(
                "tinjau",
                "Tinjau beberapa proyek sekaligus",
                "Buka Laporan. Peta waktu membandingkan rentang proyek; tabel merangkum "
                "rencana, aktual, deviasi, kondisi, dan target. Data selalu dibatasi oleh proyek "
                "yang dapat Anda akses. Manajemen dapat membaca seluruh portofolio.",
                "Mulai dari proyek dengan target yang lewat, deviasi negatif, atau masalah "
                "yang belum selesai. Buka proyek untuk memeriksa penyebabnya.",
                visual="report",
                caption="Contoh dua proyek dalam satu tampilan perbandingan.",
            ),
            section(
                "cari",
                "Cari dan saring proyek",
                "Di Projects, cari nama atau kode. Gunakan filter status, PM, tim, tahap, "
                "rentang tanggal, dan rentang progres sesuai kebutuhan. Pilih tampilan daftar "
                "atau kartu jika tersedia. Tanggal dan persentase minimum/maksimum "
                "harus berurutan.",
                "Menu Jadwal global menunjukkan rentang beberapa proyek. Gunakan untuk melihat "
                "proyek yang berjalan bersamaan sebelum membuka jadwal task di "
                "masing-masing proyek.",
            ),
            section(
                "unduh",
                "Unduh laporan",
                steps=[
                    "Buka Laporan dan temukan pilihan unduh/ekspor.",
                    "Pilih jenis data: ringkasan, progres, jadwal, task, masalah, atau milestone.",
                    "Pilih proyek bila hanya ingin laporan satu proyek, atau seluruh "
                    "proyek yang dapat diakses.",
                    "Pilih CSV, XLSX, atau PDF, lalu unduh dan periksa hasilnya.",
                ],
                paragraphs=[
                    "CSV cocok untuk olah data sederhana, XLSX untuk lembar kerja, dan PDF untuk "
                    "dokumen yang siap dibaca. Pilihan proyek, jenis data, dan format "
                    "ekspor menentukan "
                    "isi berkas; jangan menganggap filter halaman lain otomatis ikut diterapkan."
                ],
                callout=(
                    "Laporan adalah data saat diunduh",
                    "Laporan tidak memperbarui dirinya "
                    "setelah berkas disimpan. Unduh lagi jika data proyek telah berubah.",
                ),
            ),
        ],
        related=["progress-proyek", "presentasi-proyek", "akun-dan-akses"],
        action=("projects:reports", "Buka Laporan"),
    ),
    article(
        "presentasi-proyek",
        "Mempresentasikan proyek",
        "Pantau dan laporkan",
        "Susun slide dari data proyek untuk menjelaskan progres, pekerjaan berikutnya, "
        "dan hambatan.",
        [
            section(
                "susun",
                "Susun isi presentasi",
                steps=[
                    "Buka proyek → Presentasi. Pengaturan tampil pada panel di sisi halaman.",
                    "PM memilih rentang Periode berikutnya untuk pekerjaan yang ingin dibahas.",
                    "Aktifkan atau nonaktifkan sumber slide, ubah judul, dan tentukan "
                    "apakah PIC, jadwal, serta keterangan ditampilkan.",
                    "Seret urutan atau gunakan tombol naik/turun. Kolom Kanban "
                    "tambahan dapat dijadikan sumber slide.",
                    "Pilih Simpan susunan untuk menyimpan saja, atau Mulai presentasi "
                    "untuk menyimpan sekaligus membuka tayangan.",
                ],
                visual="presentation",
                caption="Contoh urutan sumber slide. Susunan disimpan untuk proyek, bukan "
                "untuk setiap pengguna.",
            ),
            section(
                "isi",
                "Dari mana isi slide berasal?",
                bullets=[
                    "Ringkasan mengambil grafik dan angka rencana, aktual, serta deviasi proyek.",
                    "Pekerjaan aktif mencakup task yang sedang dikerjakan, terhambat, "
                    "atau menunggu pemeriksaan.",
                    "Periode berikutnya mengambil pekerjaan belum selesai yang "
                    "jadwalnya beririsan dengan tanggal pilihan, termasuk pekerjaan "
                    "aktif.",
                    "Pekerjaan belum dijadwalkan tanpa tanggal tidak masuk daftar "
                    "periode berikutnya.",
                    "Masalah terbuka mengutamakan tingkat kritis dan tinggi.",
                    "Task dan kartu umpan balik dari kolom tambahan muncul jika "
                    "sumbernya diaktifkan.",
                    "Isi panjang dan daftar besar dilanjutkan ke slide berikutnya, bukan dipotong.",
                ],
                callout=(
                    "Data diambil saat tayangan dibuka",
                    "Presentasi memakai satu kumpulan "
                    "data untuk sesi tersebut. Jika task berubah selama rapat, keluar "
                    "lalu mulai lagi "
                    "untuk mengambil data terbaru. Sesi ini bukan arsip historis laporan.",
                ),
            ),
            section(
                "kendali",
                "Navigasi dan layar penuh",
                table={
                    "headers": ["Kendali", "Tindakan"],
                    "rows": [
                        ["Tombol sebelumnya/berikutnya atau pemilih slide", "Berpindah slide."],
                        ["Panah kiri/kanan, Page Up/Page Down", "Mundur atau maju."],
                        ["Home / End", "Ke slide awal / akhir."],
                        ["Spasi", "Maju ketika tidak sedang berfokus pada tombol atau isian."],
                        ["Escape", "Keluar dari layar penuh; tekan lagi untuk kembali ke proyek."],
                        ["Geser di perangkat sentuh", "Berpindah pada area yang bukan tabel."],
                    ],
                },
                paragraphs=[
                    "Semua pengguna yang dapat membaca proyek boleh menjalankan susunan yang "
                    "disimpan PM. Tema mengikuti Scope. Tabel di layar kecil dapat "
                    "digeser mendatar "
                    "dan isi panjang dapat digulir. Fitur ini tidak menyediakan ekspor PPT/PPTX."
                ],
            ),
        ],
        related=["task-kanban", "laporan-portofolio", "progress-proyek"],
    ),
    article(
        "pengaturan-akun",
        "Akun, tema, dan tampilan",
        "Bantuan",
        "Perbarui identitas, ganti kata sandi, dan sesuaikan tampilan Scope dengan perangkat Anda.",
        [
            section(
                "profil",
                "Perbarui profil dan kata sandi",
                steps=[
                    "Buka Pengaturan → Akun.",
                    "Pada Profil, perbarui nama depan, nama belakang, atau surel, lalu "
                    "pilih Simpan profil.",
                    "Pada Ubah password, isi kata sandi lama dan konfirmasi kata sandi "
                    "baru, lalu pilih Perbarui password.",
                ],
                paragraphs=[
                    "Penggantian kata sandi lokal mempertahankan sesi saat ini. Jika "
                    "lupa kata sandi, "
                    "hubungi administrator. Kata sandi Microsoft dikelola melalui akun "
                    "Microsoft, bukan melalui form lokal Scope."
                ],
            ),
            section(
                "tema",
                "Pilih tema dan ukuran navigasi",
                "Buka menu akun pada bilah atas → Tema → Terang, Gelap, atau Sistem. "
                "Pilihan disimpan pada peramban yang digunakan. Sistem mengikuti tema perangkat; "
                "tema di peramban atau perangkat lain tidak otomatis ikut berubah.",
                "Tombol sidebar pada bilah atas memperbesar atau memperkecil navigasi. "
                "Di perangkat kecil, gunakan tombol menu untuk membuka navigasi, lalu "
                "pilih halaman. "
                "Gunakan layar penuh pada grafik atau jadwal ketika memerlukan ruang lebih luas.",
                visual="settings",
                caption="Contoh pilihan tema. Gunakan menu akun di aplikasi untuk menerapkannya.",
            ),
            section(
                "akun-baru",
                "Buat akun lokal untuk anggota baru",
                "Administrator melihat tombol Buat akun lokal di Pengaturan → Akun. "
                "Isi nama pengguna, identitas, kata sandi, dan peran, lalu simpan. "
                "Sesudah akun tersedia, PM dapat menambahkannya ke anggota proyek dan "
                "penugasan task.",
                "Pengguna biasa tidak dapat menaikkan perannya sendiri melalui profil. "
                "Hubungi administrator untuk koreksi hak akses.",
            ),
            section(
                "docs",
                "Buka panduan kembali",
                "Dokumentasi ini tersedia melalui Pengaturan → Docs. Pencarian hanya mencari "
                "isi panduan, bukan data proyek. Tautan artikel dan bagian dapat disalin untuk "
                "dibagikan kepada pengguna Scope yang sudah masuk.",
            ),
        ],
        related=["akun-dan-akses", "anggota-tim", "bantuan-istilah"],
        action=("identity:settings", "Buka pengaturan akun"),
    ),
    article(
        "bantuan-istilah",
        "Pertanyaan umum dan istilah",
        "Bantuan",
        "Temukan jawaban ketika angka, akses, atau alur pekerjaan terasa membingungkan.",
        [
            section(
                "akses",
                "Proyek atau task tidak terlihat",
                "Periksa akun yang digunakan. Minta PM memastikan Anda anggota proyek, "
                "penanggung jawab, atau rekan pengerjaan. Untuk Pekerjaan saya, task harus "
                "ditugaskan kepada Anda; keanggotaan proyek saja belum cukup.",
                "Tautan yang pernah dapat dibuka bisa tidak tersedia setelah akses berubah. "
                "Membuka tautan langsung tidak melewati pemeriksaan akses.",
            ),
            section(
                "angka",
                "Progres tidak sesuai perkiraan",
                "Periksa bobot dan apakah task merupakan subtask. Lihat juga apakah PM "
                "mengisi pengganti progres manual. Menyelesaikan subtask tidak otomatis "
                "menyelesaikan induknya, milestone, atau status proyek.",
                "Rencana/deviasi kosong berarti baseline belum tersedia, bukan berarti "
                "proyek berada tepat pada rencana. Jadwal lengkap belum menjadi "
                "baseline sampai disimpan.",
                "Riwayat kosong pada tanggal tertentu dapat berarti belum ada snapshot "
                "yang tercatat pada hari itu.",
            ),
            section(
                "simpan",
                "Perubahan atau impor tidak dapat disimpan",
                bullets=[
                    "Terhambat: isi alasan hambatan yang jelas.",
                    "Task tidak bisa dimulai/diselesaikan: periksa dependensi yang belum Selesai.",
                    "Tanggal: tanggal selesai tidak boleh sebelum tanggal mulai.",
                    "Rekan: pilih orang pertama dahulu, lalu satu orang berbeda sebagai rekan.",
                    "Baseline: isi tanggal semua task utama dan pastikan total bobot "
                    "lebih besar dari nol.",
                    "Lampiran: batas ukuran 10 MB per berkas.",
                    "Impor: gunakan templat version 1, akun yang tersedia, dan JSON "
                    "valid berukuran maksimal 2 MB.",
                    "Jika pesan kesalahan menyebut satu isian, perbaiki isian tersebut "
                    "sebelum mencoba lagi.",
                ],
            ),
            section(
                "istilah",
                "Istilah yang digunakan Scope",
                table={
                    "headers": ["Istilah", "Arti"],
                    "rows": [
                        ["Project / proyek", "Wadah tujuan, tim, rencana, dan pekerjaan."],
                        ["Task", "Satu pekerjaan dengan status, penanggung jawab, dan progres."],
                        ["PM", "Manajer proyek yang mengatur dan meninjau pekerjaan."],
                        [
                            "PIC / penanggung jawab",
                            "Orang yang bertanggung jawab pada pekerjaan atau tindak lanjut.",
                        ],
                        ["Phase / tahap", "Kelompok pekerjaan dalam satu bagian proyek."],
                        ["Milestone", "Hasil atau titik penting dengan tanggal target."],
                        ["Baseline", "Rencana pembanding yang disimpan untuk menilai perubahan."],
                        [
                            "Actual / aktual",
                            "Kemajuan yang dihitung dari pekerjaan atau ditetapkan manual oleh PM.",
                        ],
                        ["Deviasi", "Selisih aktual dikurangi rencana dalam poin persentase."],
                        ["Bobot", "Besarnya pengaruh task utama pada progres proyek."],
                        [
                            "Dependency / dependensi",
                            "Pekerjaan prasyarat yang harus diselesaikan lebih dahulu.",
                        ],
                        ["Snapshot", "Catatan kondisi progres untuk satu tanggal."],
                        ["Issue / masalah", "Kendala yang sudah terjadi dan perlu ditangani."],
                        ["Risiko", "Kemungkinan kendala yang perlu dimitigasi."],
                        ["Feedback / umpan balik", "Catatan tindak lanjut tanpa bobot progres."],
                    ],
                },
            ),
        ],
        keywords="faq error gagal bantuan troubleshooting istilah",
        related=["akun-dan-akses", "progress-proyek", "impor-rencana-ai"],
    ),
)


def article_text(item):
    """Teks biasa untuk pencarian seluruh isi, termasuk langkah dan tabel."""
    parts = [
        item["title"],
        item["summary"],
        item["group"],
        item["audience"],
        item.get("keywords", ""),
    ]
    for block in item["sections"]:
        parts.extend([block["title"], *block["paragraphs"]])
        parts.extend(block.get("steps", []))
        parts.extend(block.get("bullets", []))
        parts.extend(block.get("callout", []))
        parts.append(block.get("caption", ""))
        parts.extend(block.get("table", {}).get("headers", []))
        for row in block.get("table", {}).get("rows", []):
            parts.extend(row)
    return " ".join(parts)


def search_articles(query):
    terms = re.findall(r"\w+", query.casefold())
    if not terms:
        return []
    # Kata dapat diketik sebagian; angka dan singkatan pendek harus utuh.
    patterns = [
        re.compile(r"\b" + re.escape(term) + (r"\b" if term.isdigit() or len(term) < 3 else ""))
        for term in terms
    ]
    matches = []
    for item in ARTICLES:
        text = article_text(item)
        folded = text.casefold()
        positions = [pattern.search(folded) for pattern in patterns]
        if all(positions):
            start = max(0, min(match.start() for match in positions) - 70)
            snippet = text[start : start + 240]
            score = sum(
                3 if pattern.search(item["title"].casefold()) else 1 for pattern in patterns
            )
            matches.append({"article": item, "snippet": snippet, "score": score})
    return sorted(matches, key=lambda match: -match["score"])
