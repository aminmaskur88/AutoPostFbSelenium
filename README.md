# 🚀 AutoPostFbSelenium (Termux & PC)

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Selenium](https://img.shields.io/badge/Selenium-Automation-green.svg)](https://www.selenium.dev/)
[![Termux](https://img.shields.io/badge/Platform-Termux%20%7C%20PC-orange.svg)](https://termux.dev/)

Aplikasi otomatisasi berbasis Python dan Selenium yang dirancang khusus untuk mengelola postingan **Facebook Album & Facebook Story** secara massal dan cerdas. Mendukung penuh penggunaan di **Android (via Termux + VNC)** maupun **PC/Laptop**, dengan optimasi khusus agar sangat ringan dijalankan di perangkat mobile.

Aplikasi ini memudahkan Anda mengunggah konten (video/gambar) dari folder terpisah ke banyak akun/profil Facebook dengan sistem penjadwalan fleksibel, perekam tombol interaktif, web dashboard, dan deteksi anti-bot yang canggih.

---

## ✨ Fitur Utama

*   **📖 Facebook Story Auto-Uploader:** Fitur khusus unggah Story Facebook dengan pilihan interval fleksibel (menit, jam, atau jam target harian) dan perekam tombol otomatis.
*   **📚 Facebook Album Auto-Uploader:** Penjadwalan postingan album komik/seri secara otomatis dan cerdas.
*   **⌨️ Navigasi Keyboard Interaktif:** Pilihan menu mendukung tombol panah `[↑/↓]` dan `[Enter]` untuk kemudahan akses di Termux/Terminal.
*   **🌐 Web Dashboard Management:** Kelola antrean postingan, ubah urutan (drag & drop), dan pantau status profil melalui antarmuka web modern.
*   **👤 Multi-Profile Management:** Kelola profil browser (Buka, Ganti Nama, Hapus, atau Tambah Baru) dengan mudah di folder `fb_profiles/`.
*   **⏹️ Interactive Window Control:** Kemudahan paksa tutup browser VNC instan hanya dengan menekan `[ENTER]`.
*   **📱 Support Termux & PC:** Deteksi otomatis environment untuk konfigurasi driver yang tepat (Chromium di Termux atau Chrome di PC).
*   **🤖 Smart Automation:**
    *   **Interactive Web Preview:** Pratinjau postingan sebelum diunggah melalui browser lokal.
    *   **Sticky Footer Progress:** Tampilan progress bar yang tetap di bawah terminal saat proses berjalan.
    *   **Human-Like Interaction:** Simulasi scroll, jeda acak, dan simulasi pengetikan untuk meminimalisir deteksi bot.
    *   **Drag & Drop Media Injection:** Injeksi file media langsung untuk menghindari kendala UI dialog di Android.

---

## 📂 Struktur Proyek & Panduan Direktori

```text
AutoPostFbSelenium/
│
├── 🚀 main.py                     # Entrypoint Utama (Cukup jalankan ini)
│
├── 📂 core/                       # Folder Logika & Modul Utama Bot
│   ├── utils.py                   # Setup driver, anti-bot, & VNC helper
│   ├── fb_uploader_scheduled.py   # Mesin utama postingan Album & Jadwal
│   ├── fb_story_scheduled.py     # Mesin utama postingan Facebook Story
│   ├── fb_uploader.py             # Engine standar upload
│   ├── fb_uploader_mobile.py      # Engine mobile edition (m.facebook.com)
│   ├── fb_login.py                # Helper pembuat profil & login baru
│   └── web_dashboard.py           # Web UI Dashboard Flask
│
├── 📂 tools/                      # Script Pembantu / Developer Tools
│   ├── get_xpath.py               # Inspektor XPath elemen interaktif
│   ├── record_fb_coords.py        # Perekam koordinat klik VNC
│   ├── open_browser.py            # Pembuka profil browser visual
│   └── open_chromium.py           # Browser launcher dasar
│
├── 📂 archive/                    # Script Referensi & Backup
│   └── reference_auto_poster.py
│
├── 📄 fb_coords.json             # File konfigurasi koordinat klik
├── 📄 fb_story_button.json        # Rekaman elemen tombol Story FB
├── 📄 README.md                   # Dokumentasi proyek
└── 📄 GEMINI.md                   # Petunjuk tanggal penting & aturan proyek
```

---

## 🚀 Panduan Instalasi (Termux)

### 1. Persiapan Environment
Pastikan Anda sudah menginstal Python, Chromium, dan X11 di Termux:
```bash
pkg update && pkg upgrade
pkg install python chromium chromedriver x11-repo tur-repo
pkg install termux-x11-nightly # Jika menggunakan VNC/X11
```

### 2. Klon Repositori & Install Dependensi
```bash
git clone https://github.com/aminmaskur88/AutoPostFbSelenium.git
cd AutoPostFbSelenium
pip install selenium flask pillow
```

---

## 💻 Cara Penggunaan

### 1️⃣ Menjalankan Aplikasi Utama (Rekomendasi)
Jalankan satu perintah ini untuk mengakses semua fitur melalui menu terpadu:
```bash
python main.py
```
* Navigasi menu menggunakan **tombol panah `[↑/↓]`** dan tekan **`[Enter]`** untuk memilih.

### 2️⃣ Fitur Story Facebook Auto-Uploader
Pilih menu **📖 Mode Upload Story Facebook** di `main.py`:
* Pilih akun profil target.
* Masukkan path folder/file gambar atau video (`.mp4`, `.jpg`, `.png`, `.webp`).
* Pilih strategi interval:
  1. *Jeda Menit* (cth: setiap 2 menit sekali).
  2. *Jeda Jam* (cth: setiap 2 jam sekali).
  3. *Jam Spesifik Harian* (cth: `08:00, 12:00, 17:00, 20:00`).

### 3️⃣ Kelola Profil Browser
Pilih menu **🔄 Kelola Profil Browser** di `main.py`:
* **Buka Browser**: Membuka browser visual di VNC Viewer.
* **Ganti Nama Profil**: Mengubah nama folder profil secara aman.
* **Hapus Profil**: Menghapus data akun & profil browser.
* **Tambah / Login Profil Baru**: Secara otomatis menjalankan `fb_login.py` untuk pendaftaran akun baru.

---

## 🎨 Panduan Grafis (VNC Server) di Termux

Jika menggunakan mode GUI (VNC), ikuti langkah ini:

1. **Nyalakan VNC Server:** `vncserver -localhost :1 -geometry 1280x720`
2. **Hubungkan VNC Viewer:** Buka aplikasi VNC Viewer di HP, arahkan ke `127.0.0.1:5901`.
3. **Jalankan Skrip:** Kembali ke Termux dan jalankan `python main.py`.

---

## 🤖 Kontribusi & Ucapan Terima Kasih
Dikembangkan dengan bantuan kecerdasan buatan:
* **Gemini AI (Google)** - Arsitektur sistem, optimasi logika Selenium, dan penyusunan dokumentasi.

**License:** MIT | **Author:** Amin Maskur
