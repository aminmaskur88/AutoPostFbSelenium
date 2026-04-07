# AutoPostFbSelenium (Manager Mode)

Alat manajemen otomatis untuk memposting konten (Foto/Video) ke Facebook menggunakan Selenium dengan dukungan profil Chrome terpisah untuk banyak akun.

## 🚀 Fitur Utama
- **Multi-Account Management:** Mendukung banyak akun dengan profil Chrome yang terpisah.
- **Dynamic Content Directory:** Mengatur folder konten yang berbeda untuk setiap akun secara manual dan menyimpannya.
- **Upload Tracker:** Secara otomatis menandai folder yang sudah diunggah (`uploadedfb.txt`) dan hanya menampilkan konten baru yang belum diposting.
- **Auto Upload Mode:** Mengunggah banyak konten secara berurutan dengan interval waktu yang dapat ditentukan.
- **Upload Filters & Sorting:**
  - Berurutan atau Acak (Random).
  - Hanya mengunggah Foto atau hanya mengunggah Video.
  - Sesuaikan urutan unggahan secara manual.
- **Interactive CLI:** Antarmuka menu yang bersih dan mudah digunakan di terminal/Termux.
- **Countdown Timer:** Hitung mundur waktu tunggu antar postingan secara real-time.

## 🛠️ Cara Penggunaan

### 1. Persiapan Awal
Pastikan Anda sudah menginstal dependencies (Selenium dan Driver Chrome). Di Termux, jalankan:
```bash
pkg install chromium
pkg install chromedriver
pip install selenium
```

### 2. Login Akun
Gunakan menu login untuk membuat profil dan masuk ke akun Facebook Anda:
```bash
python fb_login.py
```
*Ikuti petunjuk di terminal untuk login manual di browser Chrome yang terbuka.*

### 3. Menjalankan Manager
Gunakan program utama untuk mengelola konten dan mulai mengunggah:
```bash
python fb_uploader.py
```

#### Menu di dalam `fb_uploader.py`:
1. **Atur Folder Upload Akun (Menu 2):** Masukkan path direktori folder konten untuk setiap profil (Misal: `/storage/emulated/0/PostinganKu`).
2. **Upload Konten (Menu 1):**
   - Pilih Profil Akun.
   - Pilih Mode (Manual untuk satu folder atau Auto untuk banyak folder).
   - Tentukan filter (Foto/Video/Acak/Urutan) dan interval waktu (menit).
   - Biarkan script berjalan sampai selesai.

## 📂 Struktur Folder Konten

Setiap folder postingan harus memiliki struktur sebagai berikut:

```text

FolderPostingan/

├───post_meta.json      # File wajib: Berisi detail postingan (JSON)

├───video.mp4           # File media: Bisa berupa .mp4, .jpg, atau .png

└───uploadedfb.txt      # (Otomatis dibuat jika sudah berhasil diunggah)

```



### 📄 Contoh Isi `post_meta.json`

Pastikan file `post_meta.json` Anda memiliki format seperti di bawah ini agar script dapat membaca deskripsi dan judul dengan benar:



```json

{

    "post_title": "Judul Konten Anda",

    "summary": "Deskripsi atau cerita singkat mengenai isi video/foto ini.",

    "cta": "Klik link di bio untuk informasi lebih lanjut!",

    "hashtags": [

        "#facebook",

        "#viral",

        "#trending",

        "#autopost"

    ]

}

```



*Script akan otomatis menggabungkan `post_title`, `summary`, `cta`, dan `hashtags` menjadi satu caption yang rapi saat mengunggah.*



## ⚠️ Keamanan

Jangan membagikan folder `fb_profiles/` atau `Cookies/` kepada siapa pun, karena folder tersebut berisi sesi login aktif Anda.



## 📝 Lisensi

Bebas digunakan untuk penggunaan pribadi. Penulis tidak bertanggung jawab atas penyalahgunaan alat ini yang melanggar ketentuan layanan platform media sosial.
