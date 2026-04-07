import os
import time
import shutil
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# Deteksi Environment (Termux Android atau PC Desktop)
IS_TERMUX = "com.termux" in os.environ.get("PREFIX", "")
if IS_TERMUX:
    CHROME_PATH = "/data/data/com.termux/files/usr/bin/chromium-browser"
    CHROMEDRIVER_PATH = "/data/data/com.termux/files/usr/bin/chromedriver"
else:
    CHROME_PATH = None
    CHROMEDRIVER_PATH = None

def cleanup_profile(profile_path):
    """Menghapus folder cache dan file tidak penting agar ukuran profil tetap kecil."""
    if not os.path.exists(profile_path):
        return

    # Daftar folder agresif yang aman dihapus untuk meminimalkan ukuran profil Chrome
    folders_to_remove = [
        "Default/Cache",
        "Default/Code Cache",
        "Default/GPUCache",
        "Default/Service Worker/CacheStorage",
        "Default/Service Worker/ScriptCache",
        "Default/DawnWebGPUCache",
        "Default/DawnGraphiteCache",
        "Default/IndexedDB", 
        "Default/Media Cache",
        "Default/Network/Reporting and NEL",
        "Default/VideoDecodeStats",
        "Default/Site Characteristics Database",
        "Default/optimization_guide_hint_cache_store",
        "Default/optimization_guide_model_metadata_store",
        "Default/AutofillStrikeDatabase",
        "Crashpad",
        "component_crx_cache",
        "TranslateKit",
        "WasmTtsEngine",
        "OnDeviceHeadSuggestModel",
        "OptimizationHints",
        "GraphiteDawnCache",
        "GrShaderCache",
        "ShaderCache",
        "BrowserMetrics",
        "BrowserMetrics-spare.pma",
        "Safe Browsing",
        "pnacl"
    ]

    print(f"[*] Melakukan pembersihan profil di: {profile_path}...")
    for folder in folders_to_remove:
        full_path = os.path.join(profile_path, folder)
        if os.path.exists(full_path):
            try:
                if os.path.isdir(full_path):
                    shutil.rmtree(full_path)
                else:
                    os.remove(full_path)
            except Exception as e:
                pass
    print("[+] Pembersihan selesai.")

def setup_driver(profile_path):
    chrome_options = Options()
    if CHROME_PATH:
        chrome_options.binary_location = CHROME_PATH
    
    # Gunakan direktori profil untuk menyimpan sesi login
    chrome_options.add_argument(f"--user-data-dir={profile_path}")
    chrome_options.add_argument("--profile-directory=Default")
    
    # Argumen tambahan agar berjalan lebih lancar di Termux/Linux
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # Optimasi ukuran profil (Disable features yang tidak perlu & batasi cache sekecil mungkin)
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-component-update")
    chrome_options.add_argument("--disable-features=Translate,OptimizationHints")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--no-default-browser-check")
    chrome_options.add_argument("--disk-cache-size=1")        # Set cache disk ke 1 byte
    chrome_options.add_argument("--media-cache-size=1")       # Set cache media ke 1 byte
    chrome_options.add_argument("--disable-gpu-shader-disk-cache") # Matikan cache GPU
    chrome_options.add_argument("--disable-offline-load-stale-cache")
    chrome_options.add_argument("--disable-application-cache")
    
    # Ubah User-Agent agar tidak terdeteksi bot
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")

    if IS_TERMUX and CHROMEDRIVER_PATH:
        service = Service(CHROMEDRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=chrome_options)
    else:
        # Biarkan Selenium di PC mengunduh/mencari driver otomatis
        driver = webdriver.Chrome(options=chrome_options)
    
    # Script untuk menghilangkan deteksi selenium
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def main():
    print("=== Facebook Login & Cookie Extractor ===")
    account_name = input("Masukkan nama akun/profil (misal: akun1): ").strip()
    
    if not account_name:
        print("Nama akun tidak boleh kosong!")
        return

    # Direktori untuk menyimpan profil (cookies, session, dll) terpisah per akun
    profile_path = os.path.join(os.getcwd(), "fb_profiles", account_name)

    if not os.path.exists(profile_path):
        os.makedirs(profile_path)
        print(f"Membuat folder profil baru di: {profile_path}")

    # Bersihkan sebelum buka
    cleanup_profile(profile_path)

    print("\nMembuka Facebook... Silakan login secara MANUAL.")
    print("Script akan otomatis mendeteksi jika Anda sudah berhasil login.")
    
    driver = setup_driver(profile_path)
    try:
        driver.get("https://www.facebook.com/")
        
        # Biarkan browser tetap terbuka agar user bisa login manual
        login_success = False
        while not login_success:
            time.sleep(2)
            # Cek cookie 'c_user' yang menandakan user sudah login di Facebook
            cookies = driver.get_cookies()
            for cookie in cookies:
                if cookie['name'] == 'c_user':
                    login_success = True
                    break
            
        if login_success:
            print("\n[!] Terdeteksi sudah berhasil login ke akun utama Facebook!")
            print("[!] Jika Anda ingin menggunakan PROFIL LAIN (misal: Profil Halaman), silakan ganti profil di browser sekarang.")
            input("\n[>] TEKAN ENTER DI TERMINAL INI JIKA SUDAH BERADA DI PROFIL YANG TEPAT... ")
            
            # Pastikan folder Cookies ada
            cookie_dir = os.path.join(os.getcwd(), "Cookies")
            if not os.path.exists(cookie_dir):
                os.makedirs(cookie_dir)

            # Ekstrak dan simpan cookies ke file JSON di dalam folder Cookies
            cookie_file = os.path.join(cookie_dir, f"{account_name}_cookies.json")
            with open(cookie_file, "w") as f:
                json.dump(driver.get_cookies(), f, indent=4)
                
            print(f"[+] Cookies berhasil diekstrak dan disimpan di: {cookie_file}")
            print(f"[+] Sesi login utuh Anda tersimpan di folder: {profile_path}")
            print("Anda bisa menutup terminal ini atau script akan keluar dalam 5 detik.")
            time.sleep(5)
                
    except KeyboardInterrupt:
        print("\nMenutup browser...")
    finally:
        driver.quit()
        # Bersihkan setelah tutup
        cleanup_profile(profile_path)

if __name__ == "__main__":
    main()
