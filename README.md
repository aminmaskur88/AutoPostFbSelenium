# 🚀 AutoPostFbSelenium (Termux & PC)

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Selenium](https://img.shields.io/badge/Selenium-Automation-green.svg)](https://www.selenium.dev/)
[![Termux](https://img.shields.io/badge/Platform-Termux%20%7C%20PC-orange.svg)](https://termux.dev/)

Aplikasi otomatisasi berbasis Python dan Selenium yang dirancang khusus untuk mengelola postingan Facebook secara massal dan cerdas. Mendukung penuh penggunaan di **Android (via Termux + VNC)** maupun **PC/Laptop**, dengan fitur optimasi profil agar ringan dijalankan di perangkat mobile.

Aplikasi ini memudahkan Anda mengunggah konten (video/gambar) dari folder terpisah ke banyak akun/profil Facebook dengan sistem penjadwalan (interval), dashboard web, dan deteksi anti-bot yang canggih.

---

## ✨ Fitur Utama

*   **🌐 Web Dashboard Management:** Kelola antrean postingan, ubah urutan (drag & drop), dan pantau status profil melalui antarmuka web yang modern.
*   **📱 Support Termux & PC:** Deteksi otomatis environment untuk konfigurasi driver yang tepat (Chromium di Termux atau Chrome di PC).
*   **👤 Multi-Profile Management:** Mengelola banyak akun Facebook dengan folder profil terpisah (`fb_profiles/`) agar sesi login tetap awet.
*   **🤖 Smart Automation:**
    *   **Interactive Web Preview:** Pratinjau postingan sebelum diunggah melalui browser lokal.
    *   **Sticky Footer Progress:** Tampilan progress bar yang tetap di bawah terminal saat proses berjalan.
    *   **Human-Like Interaction:** Simulasi scroll, jeda acak, dan simulasi pengetikan untuk meminimalisir deteksi bot.
    *   **Drag & Drop Media Injection:** Teknik suntik file media langsung untuk menghindari kendala UI dialog di Android.
*   **📂 Folder-Based Posting:** Postingan disusun per-folder yang berisi media dan metadata (`post_meta.json`).
*   **⏳ Advanced Scheduling:** Mendukung posting langsung ("Post Now") atau dijadwalkan ke masa depan ("Scheduled").
*   **🧹 Auto-Cleanup Profile:** Membersihkan cache, shader, dan log secara otomatis untuk menghemat ruang penyimpanan HP.

---

## 📂 Struktur Proyek & Panduan File

| File / Folder | Deskripsi |
| :--- | :--- |
| **`web_dashboard.py`** | 🖥️ **Web UI:** Dashboard berbasis Flask untuk mengelola antrean dan profil secara visual. |
| **`fb_uploader_scheduled.py`** | 📅 **Advanced Uploader:** Mesin utama dengan fitur penjadwalan, progress bar, dan pratinjau interaktif. |
| **`fb_uploader.py`** | ⚙️ **Standard Engine:** Skrip uploader versi standar untuk posting manual/auto. |
| **`fb_uploader_mobile.py`** | 📱 **Mobile Edition:** Menggunakan `m.facebook.com` dan injeksi cookies (Sangat ringan & bisa Headless). |
| **`fb_login.py`** | 🔑 **Login Helper:** Digunakan untuk login pertama kali dan mengelola profil browser. |
| **`utils.py`** | 🛠️ **Core Utils:** Konfigurasi driver, deteksi IP LAN, dan fungsi pembersihan. |
| **`config.json`** | 📋 **Configuration:** Menyimpan pemetaan path folder konten untuk setiap profil. |
| **`fb_profiles/`** | 👤 **User Data:** Penyimpanan sesi browser per akun (Jangan dihapus). |

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

### 1️⃣ Setup Profil (Login Pertama Kali)
Jalankan `fb_login.py` untuk mendaftarkan akun baru:
```bash
python fb_login.py
```
*   Masukkan nama akun (misal: `AkunUtama`).
*   Browser akan terbuka (di VNC), silakan login manual sampai masuk beranda. Sesi Anda akan tersimpan secara otomatis.

### 2️⃣ Menggunakan Web Dashboard (Opsional tapi Direkomendasikan)
Dashboard memudahkan Anda mengatur urutan postingan sebelum dijalankan:
```bash
python web_dashboard.py
```
*   Buka URL yang muncul di terminal (misal: `http://192.168.1.5:5000`).
*   Pilih profil dan folder konten. Anda bisa **Drag & Drop** kotak postingan untuk mengubah urutan.

### 3️⃣ Menjalankan Scheduled Uploader (Utama)
Ini adalah skrip paling canggih untuk proses posting otomatis:
```bash
python fb_uploader_scheduled.py
```
*   **Fitur:** Progress bar "Sticky Footer", pilihan penjadwalan, dan **Interactive Web Preview** (Anda bisa edit caption/waktu sebelum benar-benar di-upload).

### 4️⃣ Alternatif Mobile/Headless (Ringan)
Gunakan jika Anda ingin proses berjalan di latar belakang tanpa VNC:
```bash
python fb_uploader_mobile.py
```
*   Letakkan file cookie `.json` ke dalam folder `Cookies/`.
*   Skrip akan berjalan via tampilan mobile Facebook (`m.facebook.com`).

---

## 🎨 Panduan Grafis (VNC Server) di Termux

Jika menggunakan mode GUI (VNC), ikuti langkah ini:

1.  **Nyalakan VNC Server:** `vncserver -localhost :1 -geometry 1280x720`
2.  **Hubungkan VNC Viewer:** Buka aplikasi VNC Viewer di HP, arahkan ke `127.0.0.1:5901`.
3.  **Jalankan Skrip:** Kembali ke Termux dan jalankan uploader pilihan Anda.

---

## 🛠️ Command Line Arguments (Automasi)

`fb_uploader_scheduled.py` mendukung argumen untuk automasi script lain:
```bash
python fb_uploader_scheduled.py --profile "Akun1" --path "/sdcard/konten" --limit 5 --headless
```

---

## 🛠️ Developer & Debugging Tools

Beberapa skrip pembantu untuk kebutuhan pengembangan atau perbaikan:

| File | Fungsi |
| :--- | :--- |
| **`get_xpath.py`** | Membantu mencari XPath elemen secara interaktif jika struktur web Facebook berubah. |
| **`record_fb_coords.py`** | Mencatat koordinat klik untuk optimasi elemen yang sulit dijangkau Selenium standar. |
| **`open_browser.py`** | Membuka browser dengan profil tertentu tanpa menjalankan uploader (untuk cek manual). |

---

## 🤖 Kontribusi & Ucapan Terima Kasih
Dikembangkan dengan bantuan kecerdasan buatan:
*   **Gemini AI (Google)** - Arsitektur sistem, optimasi logika Selenium, dan penyusunan dokumentasi.

**License:** MIT | **Author:** Amin Maskur
