import os
import json
import time
import sys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils import setup_driver

def record_click(driver, label):
    print(f"\n[>>>] SILAKAN KLIK TEPAT DI TENGAH KOTAK '{label.upper()}' DI VNC...")
    
    # Injeksi JS untuk mendeteksi koordinat klik (X, Y)
    js_script = """
    window.last_clicked_coords = null;
    document.addEventListener('mousedown', function(e) {
        e.preventDefault();
        e.stopPropagation();
        window.last_clicked_coords = { x: e.clientX, y: e.clientY };
    }, {once: true});
    """
    driver.execute_script(js_script)
    
    while True:
        coords = driver.execute_script("return window.last_clicked_coords;")
        if coords:
            print(f"[+] Berhasil Merekam Koordinat untuk {label}: {coords}")
            return coords
        time.sleep(0.5)

def main():
    print("=== FB COORDINATE RECORDER (ADVANCED) ===")
    
    profile_dir = os.path.join(os.getcwd(), "fb_profiles")
    profiles = sorted([d for d in os.listdir(profile_dir) if os.path.isdir(os.path.join(profile_dir, d))])
    for i, p in enumerate(profiles): print(f"{i+1}. {p}")
    p_idx = int(input("\nPilih Nomor Profil: ")) - 1
    sel_profile = profiles[p_idx]

    driver = setup_driver(os.path.join(os.getcwd(), "fb_profiles", sel_profile), headless=False)

    try:
        driver.get("https://www.facebook.com/")
        print("\n[!] INSTRUKSI:")
        print("1. Buka Facebook di VNC.")
        print("2. Masuk ke layar penjadwalan (isi caption, upload foto, klik 'Berikutnya' & 'Opsi Penjadwalan').")
        print("3. Kembali ke terminal ini jika form Tanggal/Waktu sudah muncul di layar.")
        
        input("\n[?] Sudah di layar jadwal? Tekan ENTER untuk mulai merekam...")

        coords_data = {}
        coords_data['date'] = record_click(driver, "Tanggal")
        time.sleep(1)
        coords_data['time'] = record_click(driver, "Waktu")
        time.sleep(1)
        coords_data['confirm'] = record_click(driver, "Tombol Jadwalkan Untuk Nanti")

        with open("fb_coords.json", "w") as f:
            json.dump(coords_data, f, indent=4)
        
        print("\n[+++] KOORDINAT BERHASIL DISIMPAN!")
        print("[!] Sekarang jalankan fb_uploader_scheduled.py.")

    except Exception as e:
        print(f"[!] Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
