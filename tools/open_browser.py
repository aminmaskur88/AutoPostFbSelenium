import os
import json
import time
import sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# Import helper dari utils
from utils import ensure_vnc_running, get_lan_ip, cleanup_profile

# Pastikan DISPLAY teratur untuk VNC di Termux
if "com.termux" in os.environ.get("PREFIX", ""):
    os.environ["DISPLAY"] = ":1"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def setup_visible_browser(profile_path=None):
    # Pastikan VNC Server aktif di Termux
    ensure_vnc_running()
    options = Options()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--remote-debugging-pipe')
    
    # Gunakan resolusi desktop agar sesuai dengan fb_uploader_scheduled.py
    options.add_argument('--window-size=1280,800')
    options.add_argument('--start-maximized')
    options.add_argument('--remote-allow-origins=*')
    
    # Gunakan User Agent desktop
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    if profile_path:
        options.add_argument(f"--user-data-dir={profile_path}")
        options.add_argument("--profile-directory=Default")
    
    if os.path.exists('/data/data/com.termux/files/usr/bin/chromium-browser'):
        options.binary_location = '/data/data/com.termux/files/usr/bin/chromium-browser'
    elif os.path.exists('/data/data/com.termux/files/usr/bin/chromium'):
        options.binary_location = '/data/data/com.termux/files/usr/bin/chromium'
    
    service_path = '/data/data/com.termux/files/usr/bin/chromedriver'
    service = Service(service_path) if os.path.exists(service_path) else None
    
    driver = webdriver.Chrome(service=service, options=options) if service else webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    driver.set_window_size(1280, 800)
    return driver

def main():
    cookies_dir = os.path.join(BASE_DIR, "Cookies")
    if not os.path.exists(cookies_dir):
        print("[-] Folder Cookies tidak ditemukan.")
        return

    cookie_files = [f for f in os.listdir(cookies_dir) if f.endswith('.json')]
    if not cookie_files:
        print("[-] Tidak ada file cookie (.json) di folder Cookies/.")
        return

    print("\n=== BUKA BROWSER DENGAN COOKIES & PROFIL ===")
    for i, f in enumerate(cookie_files):
        print(f"{i+1}. {f}")
    print("0. Keluar")
    
    profile_path = None
    try:
        raw_input = input("\nPilih nomor cookie yang ingin dibuka: ")
        if not raw_input or raw_input == '0':
            sys.exit()
            
        choice = int(raw_input)
        if 1 <= choice <= len(cookie_files):
            cookie_file = cookie_files[choice-1]
            cookie_path = os.path.join(cookies_dir, cookie_file)
            
            # Tentukan nama akun dan path profil
            account_name = cookie_file.replace("_cookies.json", "")
            profile_path = os.path.join(BASE_DIR, "fb_profiles", account_name)
            
            # Bersihkan profil sebelum digunakan untuk mencegah lock
            cleanup_profile(profile_path)
            
            print(f"\n[*] Membuka Chromium di VNC Viewer...")
            if "com.termux" in os.environ.get("PREFIX", ""):
                lan_ip = get_lan_ip()
                print(f">>> [!] BUKA VNC VIEWER SEKARANG! Sambungkan ke alamat:")
                print(f"        (Dari HP yang sama): 127.0.0.1:5901")
                print(f"        (Dari PC/HP Lain)  : {lan_ip}:5901")
                
            driver = setup_visible_browser(profile_path)
            
            print(f"[*] Memuat halaman utama www.facebook.com...")
            driver.get('https://www.facebook.com/')
            time.sleep(3)
            
            # Cek apakah sesi login sudah aktif dari profil. Jika belum, baru suntik cookie.
            is_logged_in = False
            try:
                cookies = driver.get_cookies()
                for cookie in cookies:
                    if cookie['name'] == 'c_user':
                        is_logged_in = True
                        break
            except Exception:
                pass
                
            if not is_logged_in:
                print(f"[*] Sesi belum aktif di profil. Menyuntikkan cookies dari {cookie_file}...")
                try:
                    with open(cookie_path, 'r') as f:
                        cookies = json.load(f)
                        
                    for cookie in cookies:
                        if 'sameSite' in cookie and cookie['sameSite'] not in ['Strict', 'Lax', 'None']:
                            del cookie['sameSite']
                        try: driver.add_cookie(cookie)
                        except: pass
                        
                    print(f"[*] Merefresh halaman untuk mengaplikasikan sesi login...")
                    driver.refresh()
                except Exception as e:
                    print(f"[!] Gagal menyuntikkan cookie: {e}")
            else:
                print("[+] Sesi login terdeteksi sudah aktif dari profil folder!")
            
            print("\n[+] Selesai! Browser sekarang memuat sesi akun Anda.")
            print("[!] Buka VNC Viewer untuk melihat hasilnya.")
            print("[!] Tekan CTRL+C di terminal ini untuk MENYIMPAN COOKIES dan menutup browser.")
            print("[!] (Cookies juga akan otomatis disimpan setiap 5 detik saat browser terbuka)")
            
            try:
                while True:
                    try:
                        # Cek apakah window masih terbuka
                        _ = driver.window_handles
                        # Simpan cookies terbaru
                        new_cookies = driver.get_cookies()
                        with open(cookie_path, 'w') as f:
                            json.dump(new_cookies, f, indent=4)
                    except Exception:
                        print("\n[!] Browser ditutup secara manual.")
                        break
                    time.sleep(5)
            except KeyboardInterrupt:
                print("\n[!] Menyimpan cookies terakhir sebelum keluar...")
                try:
                    new_cookies = driver.get_cookies()
                    with open(cookie_path, 'w') as f:
                        json.dump(new_cookies, f, indent=4)
                    print(f"[+] Cookies berhasil diperbarui di {cookie_file}")
                except Exception:
                    pass
                raise
        else:
            print("[-] Pilihan tidak valid.")
            
    except KeyboardInterrupt:
        print("\n[!] Menutup browser...")
        try: driver.quit()
        except: pass
    except Exception as e:
        print(f"\n[-] Error: {e}")
        try: driver.quit()
        except: pass
    finally:
        if profile_path:
            cleanup_profile(profile_path)

if __name__ == '__main__':
    main()