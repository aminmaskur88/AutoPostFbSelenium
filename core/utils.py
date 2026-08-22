import os
import shutil
import socket
import subprocess
import time
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

def setup_driver(profile_path, headless=False):
    """Konfigurasi Selenium Driver yang dioptimalkan."""
    # Pastikan VNC nyala jika tidak headless di Termux
    if not headless:
        ensure_vnc_running()
        
    chrome_options = Options()
    if CHROME_PATH:
        chrome_options.binary_location = CHROME_PATH
    
    chrome_options.add_argument(f"--user-data-dir={profile_path}")
    chrome_options.add_argument("--profile-directory=Default")
    
    if headless:
        chrome_options.add_argument("--headless=new")

    # Optimasi & Anti-bot
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--remote-debugging-pipe")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # Minimize Disk Usage
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-component-update")
    chrome_options.add_argument("--disk-cache-size=1")
    chrome_options.add_argument("--media-cache-size=1")
    
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")

    if IS_TERMUX and CHROMEDRIVER_PATH:
        service = Service(CHROMEDRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=chrome_options)
    else:
        driver = webdriver.Chrome(options=chrome_options)
    
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    # Wrap driver.quit to allow manual ENTER skip or wait 1 minute before VNC window closes
    original_quit = driver.quit
    def custom_quit():
        if not headless:
            import select
            print("\n⏳ Jendela browser siap ditutup.")
            print("➜ Tekan ENTER di sini untuk PAKSA MENUTUP browser sekarang (atau tunggu 1 menit)...")
            try:
                # Menggunakan select untuk memantau input ENTER non-blocking selama 60 detik
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

