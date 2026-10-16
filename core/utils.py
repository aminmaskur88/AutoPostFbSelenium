import os
import shutil
import socket
import subprocess
import time
import json
import sys
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# Deteksi Environment (Termux Android atau PC Desktop)
IS_TERMUX = "com.termux" in os.environ.get("PREFIX", "")
if IS_TERMUX:
    CHROME_PATH = "/data/data/com.termux/files/usr/bin/chromium-browser"
    CHROMEDRIVER_PATH = "/data/data/com.termux/files/usr/bin/chromedriver"
    # Gunakan DISPLAY :1 (Standar VNC Server)
    os.environ["DISPLAY"] = ":1"
else:
    CHROME_PATH = None
    CHROMEDRIVER_PATH = None

def get_lan_ip():
    """Mengambil alamat IP lokal (LAN) perangkat secara dinamis."""
    try:
        # Membuat socket dummy untuk mendapatkan IP routing lokal
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def ensure_vnc_running():
    """Memastikan VNC Server (:1) aktif di Termux."""
    if not IS_TERMUX:
        return

    # Cek apakah lock file X1 ada (indikasi display :1 dipakai)
    lock_file = "/data/data/com.termux/files/usr/tmp/.X1-lock"
    vnc_active = False
    
    if os.path.exists(lock_file):
        try:
            with open(lock_file, "r") as f:
                pid = int(f.read().strip())
            os.kill(pid, 0) # Cek apakah proses PID tersebut masih hidup
            vnc_active = True
        except (ProcessLookupError, ValueError, OverflowError):
            # Lock file basi (stale), bersihkan
            print("[!] Menemukan lock file VNC basi, membersihkan...")
            os.remove(lock_file)
            # Hapus juga socket file-nya jika ada
            socket_file = "/data/data/com.termux/files/usr/tmp/.X11-unix/X1"
            if os.path.exists(socket_file):
                os.remove(socket_file)

    if not vnc_active:
        print("[*] VNC Server (:1) tidak aktif. Mencoba menyalakan...")
        try:
            # Jalankan vncserver di display :1
            # Kita gunakan geometry standar dan localhost saja untuk keamanan
            subprocess.run(["vncserver", "-localhost", ":1", "-geometry", "1600x2560"], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2) # Beri jeda agar server siap
            print("[+] VNC Server berhasil dinyalakan.")
        except Exception as e:
            print(f"[!] Gagal menyalakan VNC Server: {e}")

def cleanup_profile(profile_path):
    """Menghapus folder cache dan file tidak penting agar ukuran profil tetap kecil."""
    if not os.path.exists(profile_path):
        return

    folders_to_remove = [
        "Default/Cache", "Default/Code Cache", "Default/GPUCache",
        "Default/Service Worker/CacheStorage", "Default/Service Worker/ScriptCache",
        "Default/DawnWebGPUCache", "Default/DawnGraphiteCache", "Default/IndexedDB", 
        "Default/Media Cache", "Default/Network/Reporting and NEL",
        "Default/VideoDecodeStats", "Default/Site Characteristics Database",
        "Default/optimization_guide_hint_cache_store",
        "Default/optimization_guide_model_metadata_store",
        "Default/AutofillStrikeDatabase", "Crashpad", "component_crx_cache",
        "TranslateKit", "WasmTtsEngine", "OnDeviceHeadSuggestModel",
        "OptimizationHints", "GraphiteDawnCache", "GrShaderCache",
        "ShaderCache", "BrowserMetrics", "BrowserMetrics-spare.pma",
        "Safe Browsing", "pnacl"
    ]

    print(f"[*] Membersihkan profil: {os.path.basename(profile_path)}...")
    for folder in folders_to_remove:
        full_path = os.path.join(profile_path, folder)
        if os.path.exists(full_path):
            try:
                if os.path.isdir(full_path):
                    shutil.rmtree(full_path)
                else:
                    os.remove(full_path)
            except Exception:
                pass

def kill_profile_lock_and_processes(profile_path):
    """Membunuh proses Chrome/Chromedriver yang masih mengunci profil ini dan membersihkan SingletonLock."""
    profile_path = os.path.abspath(profile_path)
    
    # 1. Hentikan proses Chrome yang masih memakai profile_path ini jika di Termux/Linux
    if IS_TERMUX:
        try:
            res = subprocess.run(["pgrep", "-f", profile_path], stdout=subprocess.PIPE, text=True)
            if res.stdout.strip():
                pids = res.stdout.strip().split()
                current_pid = str(os.getpid())
                for pid in pids:
                    if pid != current_pid:
                        try:
                            os.kill(int(pid), 9)
                        except Exception:
                            pass
                time.sleep(0.5)
        except Exception:
            pass
            
    # 2. Hapus file lock Singleton jika masih tersisa
    for lock_name in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
        lock_file = os.path.join(profile_path, lock_name)
        if os.path.exists(lock_file) or os.path.islink(lock_file):
            try:
                os.remove(lock_file)
            except Exception:
                pass

def setup_driver(profile_path, headless=False):
    """Konfigurasi Selenium Driver yang dioptimalkan."""
    # Pastikan VNC nyala jika tidak headless di Termux
    if not headless:
        ensure_vnc_running()
        
    profile_path = os.path.abspath(profile_path)
    kill_profile_lock_and_processes(profile_path)
    
    chrome_options = Options()
    if CHROME_PATH:
        chrome_options.binary_location = CHROME_PATH
    
    chrome_options.add_argument(f"--user-data-dir={profile_path}")
    chrome_options.add_argument("--profile-directory=Default")
    
    if headless:
        chrome_options.add_argument("--headless=new")

    # Optimasi & Anti-bot
    chrome_options.add_argument("--start-maximized")
    
    # Set default page zoom to ~50% (tanpa mengecilkan UI Chrome)
    prefs = {
        "partition.default_zoom_level": {
            "x": -3.8017840169239308
        }
    }
    chrome_options.add_experimental_option("prefs", prefs)

    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # Minimize Disk Usage
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-component-update")
    chrome_options.add_argument("--disk-cache-size=1")
    chrome_options.add_argument("--media-cache-size=1")
    
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")

    try:
        if IS_TERMUX and CHROMEDRIVER_PATH:
            service = Service(CHROMEDRIVER_PATH)
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            driver = webdriver.Chrome(options=chrome_options)
    except Exception as e:
        print(f"[!] Gagal memulai Chrome ({e}), mencoba membersihkan proses zombie dan mengulang...")
        if IS_TERMUX:
            try:
                subprocess.run(["pkill", "-9", "-f", "chromium|chrome"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(1)
            except Exception:
                pass
        kill_profile_lock_and_processes(profile_path)
        if IS_TERMUX and CHROMEDRIVER_PATH:
            service = Service(CHROMEDRIVER_PATH)
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            driver = webdriver.Chrome(options=chrome_options)
    
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    # Wrap driver.quit to allow manual ENTER skip or wait 1 minute before VNC window closes in Termux
    original_quit = driver.quit
    def custom_quit():
        if not headless and IS_TERMUX:
            import sys
            print("\n⏳ Jendela browser siap ditutup.")
            print("➜ Tekan ENTER di sini untuk PAKSA MENUTUP browser sekarang (atau tunggu 1 menit)...")
            try:
                import select
                rlist, _, _ = select.select([sys.stdin], [], [], 60)
                if rlist:
                    sys.stdin.readline()
                    print("[✓] Menutup browser sekarang...")
                else:
                    print("\n[i] Waktu tunggu 1 menit habis. Menutup browser...")
            except Exception:
                try:
                    input()
                except Exception:
                    time.sleep(5)
        original_quit()
    driver.quit = custom_quit
    
    return driver


def update_post_status(post_path, status, progress=0):
    """Memperbarui file upload_status.json untuk dibaca oleh Web Dashboard."""
    if not post_path:
        return
    if os.path.isfile(post_path):
        status_file = os.path.join(os.path.dirname(post_path), "upload_status.json")
    else:
        status_file = os.path.join(post_path, "upload_status.json")
        
    try:
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump({"status": status, "progress": int(progress), "timestamp": time.time()}, f)
    except Exception:
        pass


def detect_media_upload_progress(
    driver,
    media_files,
    post_path=None,
    dashboard=None,
    log_func=None,
    max_wait_sec=600,
    progress_range=(40, 75)
):
    """
    Mendeteksi proses upload media Facebook (Foto & Video) secara real-time.
    Bekerja di Tampilan Baru (post/create) maupun Dialog Klasik.
    
    Mendeteksi:
    1. Persentase numerik (teks, aria-label, aria-valuenow dari role='progressbar')
    2. Status 'Memuat...' / 'Loading...' atau spinner animasi
    3. Kemunculan elemen thumbnail gambar (img blob / alt nama file) atau bagian 'Media yang diunggah'
    4. Kesiapan tombol aksi ('Posting', 'Jadwalkan', 'Berikutnya', dll yang tidak lagi disabled)
    5. Pesan error / format tidak didukung dari Facebook
    """
    if isinstance(media_files, str):
        media_files = [media_files]
    
    media_basenames = [os.path.basename(f) for f in media_files if f]
    is_video = any(f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm', '.3gp')) for f in media_files)
    
    # Hitung estimasi ukuran file untuk batas waktu timeout cerdas
    total_size_mb = 0
    for f in media_files:
        if os.path.exists(f):
            try:
                total_size_mb += os.path.getsize(f) / (1024 * 1024)
            except Exception:
                pass
                
    if is_video:
        # Video: Beri waktu minimal 180 detik atau 5 detik per MB jika file besar
        effective_timeout = max(180, int(total_size_mb * 5), max_wait_sec)
    else:
        # Foto: Minimal 90 detik atau 30 detik per foto
        effective_timeout = max(90, int(len(media_files) * 30), max_wait_sec)

    js_detector = """
        const mediaNames = arguments[0] || [];

        function isVisible(el) {
            if (!el) return false;
            if (el.offsetParent === null && el.tagName !== 'BODY') return false;
            const r = el.getBoundingClientRect();
            if (r.width <= 0 || r.height <= 0) return false;
            try {
                const style = window.getComputedStyle(el);
                if (style.visibility === 'hidden' || style.display === 'none' || parseFloat(style.opacity) === 0) {
                    return false;
                }
            } catch(e) {}
            return true;
        }

        // 0. Temukan Container Komposer yang Aktif (Dialog Modal atau Area Main Baru)
        let container = null;
        const dialogs = Array.from(document.querySelectorAll('div[role="dialog"]'));
        for (let i = dialogs.length - 1; i >= 0; i--) {
            const d = dialogs[i];
            const txt = (d.innerText || '');
            if (txt.includes('Buat postingan') || txt.includes('Create post') || txt.includes('Media yang diunggah') || d.querySelector('input[type="file"]') || d.querySelector('div[role="textbox"]')) {
                container = d;
                break;
            }
        }
        if (!container) {
            const main = document.querySelector('div[role="main"]');
            if (main && (main.querySelector('input[type="file"]') || main.querySelector('div[role="textbox"]'))) {
                container = main;
            }
        }
        if (!container) {
            container = document.querySelector('form') || document.body;
        }

        // 1. Deteksi Animasi Muter / Spinner di dalam CONTAINER KOMPOSER
        let isSpinning = false;
        let spinnerReason = null;

        // A. Role progressbar yang terlihat
        const progressBars = Array.from(container.querySelectorAll('[role="progressbar"]'));
        for (const pb of progressBars) {
            if (isVisible(pb)) {
                isSpinning = true;
                spinnerReason = "progressbar-visible";
                break;
            }
        }

        // B. Role status / aria-live bertuliskan 'Memuat...' atau 'Loading...' yang terlihat di dalam container
        if (!isSpinning) {
            const statuses = Array.from(container.querySelectorAll('[role="status"], [aria-live="polite"], [aria-live="assertive"]'));
            for (const st of statuses) {
                if (isVisible(st)) {
                    const txt = ((st.getAttribute('aria-label') || '') + ' ' + (st.innerText || '')).toLowerCase();
                    if (txt.includes('memuat') || txt.includes('loading') || txt.includes('mengunggah') || txt.includes('uploading')) {
                        isSpinning = true;
                        spinnerReason = "status-loading";
                        break;
                    }
                }
            }
        }

        // C. Atribut aria-busy="true" yang terlihat di dalam container
        if (!isSpinning) {
            const busyEls = Array.from(container.querySelectorAll('[aria-busy="true"]'));
            for (const b of busyEls) {
                if (isVisible(b)) {
                    isSpinning = true;
                    spinnerReason = "aria-busy";
                    break;
                }
            }
        }

        // D. data-visualcompletion="loading-state" di dalam container
        if (!isSpinning) {
            const vcEls = Array.from(container.querySelectorAll('[data-visualcompletion="loading-state"]'));
            for (const vc of vcEls) {
                if (isVisible(vc)) {
                    isSpinning = true;
                    spinnerReason = "loading-state";
                    break;
                }
            }
        }

        // E. Elemen dengan animasi CSS rotasi / putaran di dalam container
        if (!isSpinning) {
            const animEls = Array.from(container.querySelectorAll('form svg, [role="progressbar"] div, [role="progressbar"] svg, svg.spinning'));
            for (const el of animEls) {
                if (el.children.length <= 1 && isVisible(el)) {
                    try {
                        const style = window.getComputedStyle(el);
                        const anim = (style.animationName || '').toLowerCase();
                        if (anim && anim !== 'none' && (anim.includes('spin') || anim.includes('rotate') || anim.includes('circle') || anim.includes('loading'))) {
                            isSpinning = true;
                            spinnerReason = "css-animation:" + anim;
                            break;
                        }
                    } catch(e) {}
                }
            }
        }

        // 2. Ekstrak persentase dari teks dan progressbar width/transform di dalam container
        const percentMatches = [];
        const allEls = Array.from(container.querySelectorAll("*"));
        for (const el of allEls) {
            if (el.children.length === 0 || el.getAttribute('role') === 'progressbar') {
                const txt = (el.innerText || '') + ' ' + (el.getAttribute('aria-label') || '');
                const m = txt.match(/(\\d+)\\s*%/);
                if (m) {
                    const val = parseInt(m[1], 10);
                    if (val >= 0 && val <= 100) percentMatches.push(val);
                }
                const valNow = el.getAttribute('aria-valuenow');
                if (valNow) {
                    const maxVal = parseFloat(el.getAttribute('aria-valuemax') || '100');
                    const nowVal = parseFloat(valNow);
                    if (maxVal > 0) percentMatches.push(Math.round((nowVal / maxVal) * 100));
                }
            }
        }
        for (const pb of progressBars) {
            const pbEls = [pb, ...Array.from(pb.querySelectorAll('*'))];
            for (const el of pbEls) {
                const w = el.style.width || '';
                const mW = w.match(/(\\d+(?:\\.\\d+)?)\\s*%/);
                if (mW) {
                    const val = Math.round(parseFloat(mW[1]));
                    if (val >= 0 && val <= 100) percentMatches.push(val);
                }
                const tf = el.style.transform || '';
                const mScale = tf.match(/scaleX\\(([\\d.]+)\\)/);
                if (mScale) {
                    const val = Math.round(parseFloat(mScale[1]) * 100);
                    if (val >= 0 && val <= 100) percentMatches.push(val);
                }
            }
        }
        let detectedPercent = -1;
        if (percentMatches.length > 0) {
            detectedPercent = Math.max(...percentMatches);
        }

        // Deteksi apakah ada teks atau atribut yang menyatakan sedang mengunggah
        const containerText = (container.innerText || '').toLowerCase();
        let isUploading = /mengunggah|uploading|sedang memproses|masih mengunggah/i.test(containerText);
        if (!isUploading) {
            for (const el of allEls) {
                const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                if (aria.includes('mengunggah') || aria.includes('uploading')) {
                    isUploading = true;
                    break;
                }
            }
        }

        // 3. Deteksi media terkonfirmasi (Video atau Foto) di dalam container
        const hasVideo = !!container.querySelector("video") || !!Array.from(container.querySelectorAll("div[role='button'], button, span, div")).find(el => {
            const t = ((el.innerText || '') + ' ' + (el.getAttribute('aria-label') || '')).toLowerCase();
            return t.includes('edit video') || t.includes('hapus video') || t.includes('opsi video') || t.includes('video options') || t.includes('gambar mini') || t.includes('pilih gambar mini') || t.includes('deskripsikan reel');
        });

        const allImgs = Array.from(container.querySelectorAll("img"));
        const blobImgs = allImgs.filter(img => {
            const src = img.src || '';
            const alt = (img.alt || '').toLowerCase();
            if (src.startsWith('blob:') || src.startsWith('data:')) return true;
            if (mediaNames.some(name => alt.includes(name.toLowerCase()))) return true;
            return false;
        }).map(img => img.alt || 'blob');

        const hasPhoto = blobImgs.length > 0 || !!Array.from(container.querySelectorAll("div[role='button'], button, span, div")).find(el => {
            const t = ((el.innerText || '') + ' ' + (el.getAttribute('aria-label') || '')).toLowerCase();
            return t.includes('edit foto') || t.includes('hapus foto') || t.includes('media yang diunggah') || t.includes('uploaded media') || t.includes('hapus lampiran');
        });

        const mediaConfirmed = hasVideo || hasPhoto || containerText.includes('media yang diunggah') || containerText.includes('reel anda aman');

        // 4. Deteksi tombol 'Edit' di bagian media
        let hasEditBtn = false;
        const editCandidates = Array.from(container.querySelectorAll('div[role="button"], button, [aria-label]'));
        for (const b of editCandidates) {
            const txt = (b.innerText || '').trim().toLowerCase();
            const aria = (b.getAttribute('aria-label') || '').trim().toLowerCase();
            if (txt === 'edit' || txt === 'edit video' || txt === 'edit foto' ||
                aria === 'edit' || aria.includes('edit video') || aria.includes('edit foto') ||
                aria.includes('opsi video') || aria.includes('video options') || aria.includes('pilih gambar mini') ||
                txt === 'sunting' || txt === 'sunting foto' || txt === 'sunting video' || aria.includes('sunting')) {
                if (isVisible(b)) {
                    hasEditBtn = true;
                    break;
                }
            }
        }
        if (!hasEditBtn) {
            if ((containerText.includes('media yang diunggah') || containerText.includes('tambahkan lainnya')) &&
                (/\bedit\b/i.test(containerText) || containerText.includes('edit video') || containerText.includes('edit foto') || containerText.includes('pilih gambar mini'))) {
                hasEditBtn = true;
            }
        }

        // 5. Deteksi kesiapan tombol aksi utama di dalam container (Posting / Jadwalkan / Berikutnya)
        const targetLabels = ['posting', 'post', 'jadwalkan', 'schedule', 'berikutnya', 'next', 'selesai', 'done', 'simpan sebagai draf'];
        const actionBtns = Array.from(container.querySelectorAll("div[role='button'], button")).filter(b => {
            const t = (b.innerText || '').trim().toLowerCase();
            const aria = (b.getAttribute('aria-label') || '').trim().toLowerCase();
            return targetLabels.some(lbl => t === lbl || aria === lbl || t.startsWith(lbl) || aria.startsWith(lbl));
        }).map(b => ({
            text: (b.innerText || '').trim() || b.getAttribute('aria-label'),
            disabled: b.getAttribute('aria-disabled') === 'true' || b.disabled === true,
            visible: isVisible(b)
        }));

        const hasReadyActionBtn = actionBtns.some(b => b.visible && !b.disabled);

        // 6. Deteksi pesan error penolakan format atau kegagalan
        const errorKeywords = ['tidak kami dukung', 'format file yang anda pilih', 'gagal mengunggah', 'something went wrong', 'could not upload'];
        const foundError = errorKeywords.find(kw => containerText.includes(kw));

        return {
            isSpinning: isSpinning,
            spinnerReason: spinnerReason,
            isUploading: isUploading,
            detectedPercent: detectedPercent,
            mediaConfirmed: mediaConfirmed,
            hasEditBtn: hasEditBtn,
            hasVideo: hasVideo,
            hasPhoto: hasPhoto,
            hasReadyActionBtn: hasReadyActionBtn,
            errorMessage: foundError || null
        };
    """

    start_time = time.time()
    last_percent = -1
    last_ui_percent = -1
    consecutive_done = 0
    spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    frame_idx = 0
    has_detected_upload_activity = False

    msg_init = f"Mendeteksi proses upload {len(media_files)} media ({'Video' if is_video else 'Foto'})..."
    if log_func:
        log_func(msg_init)
    elif dashboard:
        dashboard.current_job["upload"] = "Mengunggah media..."
        dashboard.current_job["activity"] = msg_init
        dashboard.render()
    else:
        print(f"    \033[96m[i]\033[0m {msg_init}")

    while time.time() - start_time < effective_timeout:
        elapsed = time.time() - start_time
        res = None
        try:
            res = driver.execute_script(js_detector, media_basenames)
        except Exception:
            pass

        if res:
            # 1. Cek Pesan Error Facebook
            if res.get("errorMessage"):
                err_text = f"Facebook menolak media: {res['errorMessage']}"
                if log_func:
                    log_func(err_text, is_success=False)
                elif dashboard:
                    dashboard.current_job["upload"] = "Failed"
                    dashboard.current_job["activity"] = err_text
                    dashboard.render()
                else:
                    print(f"\n    \033[91m[✗]\033[0m {err_text}")
                if post_path:
                    update_post_status(post_path, err_text, 0)
                return False, err_text

            is_spinning = res.get("isSpinning", False)
            is_uploading = res.get("isUploading", False)
            p = res.get("detectedPercent", -1)
            media_confirmed = res.get("mediaConfirmed", False)
            has_edit_btn = res.get("hasEditBtn", False)
            has_ready_btn = res.get("hasReadyActionBtn", False)

            if is_spinning or is_uploading or p >= 0 or media_confirmed:
                has_detected_upload_activity = True

            # 2. Pengamatan Progres Upload
            if p >= 0:
                raw_pct = max(p, last_percent)
            else:
                expected_time = 15 if not is_video else max(40, int(total_size_mb * 1.5))
                raw_pct = min(92, int((elapsed / expected_time) * 85) + 5)

            # Batasi progres selama tombol aksi belum aktif
            curr_upload_pct = min(95, max(raw_pct, last_percent if last_percent >= 0 else 5))
            last_percent = curr_upload_pct

            # Karakter animasi spinner untuk terminal
            frame_char = spinner_chars[frame_idx % len(spinner_chars)]
            frame_idx += 1

            # 3. Laporkan progres
            if curr_upload_pct != last_ui_percent or is_spinning or is_uploading:
                last_ui_percent = curr_upload_pct
                disp_pct = curr_upload_pct
                ui_prog = progress_range[0] + int((disp_pct / 100.0) * (progress_range[1] - progress_range[0]))
                status_msg = f"Mengunggah media: {disp_pct}% {frame_char}"

                if post_path:
                    update_post_status(post_path, status_msg, ui_prog)

                if dashboard:
                    dashboard.current_job["upload"] = f"Mengunggah: {disp_pct}% {frame_char}"
                    dashboard.current_job["activity"] = status_msg
                    dashboard.render()
                elif log_func:
                    log_func(status_msg)
                else:
                    sys.stdout.write(f"\r    \033[92m⚡ [UPLOAD MEDIA]\033[0m : \033[1m{disp_pct}%\033[0m [\033[93m{frame_char} Mengunggah\033[0m] ")
                    sys.stdout.flush()

            # 4. KONDISI SELESAI:
            # UNTUK VIDEO: Selesai HANYA JIKA tombol aksi ('Jadwalkan'/'Posting'/'Berikutnya') sudah AKTIF (tidak disabled),
            # media terkonfirmasi, tidak ada spinner aktif, tidak ada teks 'mengunggah', dan jika persentase terbaca harus >= 100%
            if is_video:
                is_finished = (
                    has_ready_btn and
                    media_confirmed and
                    (not is_spinning) and
                    (not is_uploading) and
                    (p == -1 or p >= 100) and
                    elapsed >= 5
                )
            else:
                is_finished = (
                    (has_ready_btn or has_edit_btn) and
                    media_confirmed and
                    (not is_spinning) and
                    (not is_uploading) and
                    (p == -1 or p >= 100) and
                    elapsed >= 2
                )

            if is_finished:
                consecutive_done += 1
                if consecutive_done >= 2:
                    complete_msg = "Upload media 100% selesai (Tombol jadwal/posting aktif & media siap)."
                    if post_path:
                        update_post_status(post_path, complete_msg, progress_range[1])

                    if dashboard:
                        dashboard.current_job["upload"] = "Completed"
                        dashboard.current_job["activity"] = complete_msg
                        dashboard.render()
                    elif log_func:
                        log_func(complete_msg, is_success=True)
                    else:
                        sys.stdout.write(f"\r    \033[92m⚡ [UPLOAD MEDIA]\033[0m : \033[1m100%\033[0m [\033[92m✓ Selesai\033[0m]\n")
                        sys.stdout.flush()

                    # Delay 10 detik saat upload untuk stabilisasi media di Facebook
                    delay_sec = 10
                    msg_delay = f"Jeda {delay_sec} detik untuk stabilisasi media sebelum jadwal..."
                    if log_func:
                        log_func(msg_delay)
                    elif dashboard:
                        dashboard.current_job["activity"] = msg_delay
                        dashboard.render()
                    else:
                        print(f"    ⏳ {msg_delay}")

                    for remaining in range(delay_sec, 0, -1):
                        tick_msg = f"Menunggu stabilisasi: {remaining} detik tersisa..."
                        if dashboard:
                            dashboard.current_job["activity"] = tick_msg
                            dashboard.render()
                        elif not log_func:
                            sys.stdout.write(f"\r    ⏳ Menunggu stabilisasi: {remaining}s tersisa... ")
                            sys.stdout.flush()
                        time.sleep(1)

                    if not log_func and not dashboard:
                        sys.stdout.write(f"\r    ⏳ Menunggu stabilisasi: Selesai!              \n")
                        sys.stdout.flush()

                    return True, "Upload selesai (terkonfirmasi penuh, tombol aksi aktif)"
            else:
                consecutive_done = 0

        time.sleep(1.0)

    # Fallback jika timeout tercapai
    timeout_msg = "Waktu tunggu upload tercapai, memeriksa kesiapan halaman..."
    if log_func:
        log_func(timeout_msg)
    elif dashboard:
        dashboard.current_job["activity"] = timeout_msg
        dashboard.render()
    else:
        print(f"\n    \033[93m[!]\033[0m {timeout_msg}")

    return has_detected_upload_activity, "Timeout tercapai"


