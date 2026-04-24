import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# Pastikan DISPLAY teratur untuk VNC di Termux
if "com.termux" in os.environ.get("PREFIX", ""):
    os.environ["DISPLAY"] = ":1"

def main():
    print("=== BUKA CHROMIUM KOSONG (TANPA SESI) ===")
    
    options = Options()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--remote-debugging-pipe')
    options.add_argument('--window-size=1280,800')
    options.add_argument('--start-maximized')
    
    # Deteksi lokasi binary Chromium di Termux
    if os.path.exists('/data/data/com.termux/files/usr/bin/chromium-browser'):
        options.binary_location = '/data/data/com.termux/files/usr/bin/chromium-browser'
    elif os.path.exists('/data/data/com.termux/files/usr/bin/chromium'):
        options.binary_location = '/data/data/com.termux/files/usr/bin/chromium'
    
    # Deteksi lokasi ChromeDriver
    service_path = '/data/data/com.termux/files/usr/bin/chromedriver'
    service = Service(service_path) if os.path.exists(service_path) else None
    
    print("[*] Menyiapkan browser...")
    if "com.termux" in os.environ.get("PREFIX", ""):
        print("[!] BUKA VNC VIEWER SEKARANG! (Biasanya 127.0.0.1:5901 atau IP_LAN:5901)")
    print("[!] Tekan CTRL+C di terminal ini untuk menutup browser.")
    
    # Menjalankan Chrome tanpa user-data-dir sehingga benar-benar kosong (Incognito-like behavior)
    driver = webdriver.Chrome(service=service, options=options) if service else webdriver.Chrome(options=options)
    driver.set_window_size(1280, 800)
    
    try:
        print(f"[*] Membuka Chromium dengan resolusi skala Xiaomi Pad 5 (1280x800)...")
        # Buka Google sebagai halaman awal
        driver.get('https://www.google.com')
        
        # Loop ini menahan agar script (dan browser) tidak langsung tertutup
        while True:
            time.sleep(2)
            # Cek apakah window browser masih terbuka, jika user menutup manual dari X di VNC, script akan break
            try:
                _ = driver.window_handles
            except Exception:
                print("\n[!] Browser ditutup secara manual dari VNC.")
                break
                
    except KeyboardInterrupt:
        print("\n[!] Menutup browser karena CTRL+C ditekan...")
    except Exception as e:
        print(f"\n[-] Error: {e}")
    finally:
        try:
            driver.quit()
            print("[+] Selesai.")
        except:
            pass

if __name__ == '__main__':
    main()
