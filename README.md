# 🚀 AutoPostFbSelenium (Termux & PC)

Aplikasi otomatisasi berbasis Python dan Selenium yang dirancang khusus untuk mengelola postingan Facebook secara massal dan cerdas. Aplikasi ini mendukung penuh penggunaan di **Android (via Termux + VNC)** maupun **PC/Laptop**, dengan fitur optimasi profil agar ringan dijalankan di perangkat mobile.

Aplikasi ini memudahkan Anda mengunggah konten (video/gambar) dari folder terpisah ke banyak akun/profil Facebook dengan sistem penjadwalan (interval) dan deteksi anti-bot yang canggih.

---

## ✨ Fitur Utama

*   **📱 Support Termux & PC:** Deteksi otomatis environment untuk konfigurasi driver yang tepat (Chromium di Termux atau Chrome di PC).
*   **👤 Multi-Profile Management:** Mengelola banyak akun Facebook dengan folder profil terpisah (`fb_profiles/`) sehingga sesi login tetap awet dan tidak saling bentrok.
*   **🤖 Smart Automation:**
    *   **Auto-Login/Cookie Extractor:** Membantu mengambil session cookies agar script bisa berjalan tanpa perlu login ulang terus-menerus.
    *   **Human-Like Interaction:** Simulasi scroll, jeda acak (human delay), dan simulasi pengetikan untuk meminimalisir deteksi bot.
    *   **Drag & Drop Media Injection:** Teknik suntik file media langsung ke elemen input tersembunyi untuk menghindari kendala UI dialog di Android.
*   **📂 Folder-Based Posting:** Postingan disusun per-folder yang berisi media dan metadata (`post_meta.json`). Script akan membaca judul, deskripsi, dan hashtag secara otomatis.
*   **⏳ Interval & Countdown:** Fitur unggah otomatis semua konten dengan jeda waktu (interval) yang dilengkapi tampilan hitung mundur (countdown) di terminal.
*   **🧹 Auto-Cleanup Profile:** Secara otomatis membersihkan cache, shader, dan log Chrome yang tidak penting untuk menghemat ruang penyimpanan HP (sangat krusial untuk pengguna Termux).
*   **🔍 XPath Ultimate Helper:** Dilengkapi skrip pembantu untuk mengidentifikasi elemen web secara visual jika struktur Facebook berubah.

---

## 📂 Struktur Proyek & Panduan File

| File / Folder | Deskripsi |
| :--- | :--- |
| **`fb_uploader.py`** | ⚙️ **Main Engine:** Skrip utama untuk melakukan posting (Manual/Auto). |
| **`fb_uploader_mobile.py`** | 📱 **Mobile Edition:** Skrip tangguh via `m.facebook.com` menggunakan injeksi cookies JSON (Bisa jalan Headless/Tanpa VNC). |
| **`fb_login.py`** | 🔑 **Login Helper:** Digunakan untuk login pertama kali dan mengekstrak cookies/session. |
| **`utils.py`** | 🛠️ **Core Utils:** Berisi konfigurasi driver, anti-bot, dan fungsi pembersih profil. |
| **`get_xpath.py`** | 🔍 **Dev Tool:** Skrip bantuan untuk mencari XPath elemen secara interaktif. |
| **`config.json`** | 📋 **Configuration:** Menyimpan pemetaan path folder konten untuk setiap profil. |
| **`fb_profiles/`** | 👤 **User Data:** Tempat menyimpan data sesi/browser Chrome per akun (Jangan dihapus). |
| **`Cookies/`** | 🍪 **JSON Cookies:** Hasil ekstrak cookie dari `fb_login.py` (sebagai backup). |

---

## 🚀 Panduan Instalasi (Termux)

### 1. Persiapan Environment
Pastikan Anda sudah menginstal Python, Chromium, dan X11 di Termux:
```bash
pkg update && pkg upgrade
pkg install python chromium chromedriver x11-repo tur-repo
pkg install termux-x11-nightly # Jika menggunakan VNC/X11
```

### 2. Klon Repositori
```bash
git clone https://github.com/aminmaskur88/AutoPostFbSelenium.git
cd AutoPostFbSelenium
```

### 3. Instal Dependensi
```bash
pip install selenium
```

---

## 🎨 Panduan Grafis (VNC Server) di Termux

Karena Selenium membutuhkan tampilan browser untuk proses tertentu (seperti login), Anda harus menggunakan VNC Server:

### 🛠️ Persiapan Awal (Sekali Saja)
1.  **Instal Dependencies:**
    ```bash
    pkg update && pkg upgrade
    pkg install x11-repo
    pkg install chromium chromedriver tigervnc fluxbox
    ```
2.  **Instal Aplikasi Android:** Unduh dan instal **VNC Viewer** (oleh RealVNC) dari Play Store.

### 🚀 Alur Kerja Sehari-hari (Workflow)
Ikuti urutan ini setiap kali ingin menjalankan skrip:

1.  **Nyalakan VNC Server:**
    ```bash
    vncserver -localhost :1 -geometry 1280x720
    ```
    *(Jika baru pertama kali, Anda akan diminta membuat password VNC, bebas minimal 6 karakter).*
2.  **Hubungkan VNC Viewer:** Buka aplikasi VNC Viewer di HP, tambahkan koneksi baru ke alamat `127.0.0.1:5901`.
3.  **Jalankan Skrip:** Kembali ke Termux, jalankan:
    ```bash
    python fb_uploader.py
    ```
4.  **Lihat Browser:** Pindah ke aplikasi VNC Viewer. Browser Chromium akan muncul di sana (dalam lingkungan desktop Fluxbox).

---

## 💻 Cara Penggunaan

### 1️⃣ Setup Profil (Login Pertama Kali)
Jalankan `fb_login.py` untuk mendaftarkan akun baru:
```bash
python fb_login.py
```
*   Masukkan nama akun (misal: `AkunUtama`).
*   Browser akan terbuka (di VNC), silakan login manual sampai masuk beranda.
*   Tekan Enter di terminal jika sudah selesai. Sesi Anda akan tersimpan secara permanen.

### 2️⃣ Menyiapkan Konten
Buat folder konten di dalam direktori pilihan Anda. Setiap folder postingan harus berisi:
*   1 file media (Foto `.jpg`/`.png` atau Video `.mp4`).
*   1 file `post_meta.json` dengan format:
```json
{
    "post_title": "Judul Keren",
    "summary": "Deskripsi postingan di sini...",
    "cta": "Klik link di bio!",
    "hashtags": ["#viral", "#facebook", "#otomatis"]
}
```

### 3️⃣ Menjalankan Uploader (Desktop Version)
Jalankan skrip utama `fb_uploader.py` untuk mode desktop:
```bash
python fb_uploader.py
```
*   **Menu 2:** Atur folder sumber konten untuk profil Anda (Lakukan ini sekali saja).
*   **Menu 1:** Pilih profil, lalu pilih **Auto All** untuk mengunggah semua folder secara berurutan dengan interval.

### 4️⃣ Alternatif Mobile/Headless (Lebih Ringan)
Jika Anda tidak ingin repot menggunakan VNC atau sekadar ingin proses berjalan diam-diam (siluman) di latar belakang Termux, gunakan **`fb_uploader_mobile.py`**:
```bash
python fb_uploader_mobile.py
```
*   Letakkan file cookie `.json` dari ekstensi browser (seperti EditThisCookie) ke dalam folder `Cookies/`. Skrip akan **otomatis mendeteksi** akun Anda.
*   Gunakan **Menu 2** untuk memasukkan path lokasi folder konten Anda.
*   Pilih **Menu 1** untuk mulai mengunggah dengan simulasi tangguh (*brutal injection*) via tampilan mobile Facebook (`m.facebook.com`).

---

## 🤖 Special Thanks
Dikembangkan dengan bantuan kecerdasan buatan:
*   **Gemini AI (Google)** - Optimasi logika Selenium, sistem pembersihan profil, dan penyusunan dokumentasi profesional ini.

**License:** MIT | **Author:** Amin Maskur