import os
import time
import json
from utils import setup_driver, cleanup_profile, get_lan_ip

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
    if "com.termux" in os.environ.get("PREFIX", ""):
        lan_ip = get_lan_ip()
        print(f">>> [!] BUKA VNC VIEWER SEKARANG! Sambungkan ke alamat:")
        print(f"        (Dari HP yang sama): 127.0.0.1:5901")
        print(f"        (Dari PC/HP Lain)  : {lan_ip}:5901")
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