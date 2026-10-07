import os
import sys
import time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.utils import setup_driver

def main():
    print("=== DUMP FACEBOOK HTML ===")
    profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'fb_profiles'))
    profiles = [f for f in os.listdir(profile_dir) if os.path.isdir(os.path.join(profile_dir, f))]
    
    for i, p in enumerate(profiles, 1):
        print(f"{i}. {p}")
        
    pilihan = input("Masukkan nomor profil (pilih yang biasa Anda pakai): ").strip()
    try:
        profile_name = profiles[int(pilihan)-1]
    except:
        return
        
    profile_path = os.path.join(profile_dir, profile_name)
    driver = setup_driver(profile_path, headless=False)
    
    driver.get("https://www.facebook.com/post/create")
    print("\n[+] Browser terbuka. Halaman akan dialihkan ke post/create.")
    print("SILAKAN tunggu sampai halamannya termuat dengan sempurna.")
    
    input("\n[!] TEKAN ENTER JIKA HALAMAN 'POST/CREATE' SUDAH TERBUKA SEMPURNA...")
    
    print("\n[+] Menyimpan struktur HTML, mohon tunggu...")
    # Ambil isi seluruh tag <body>
    html_content = driver.find_element("tag name", "body").get_attribute('innerHTML')
    
    dump_path = os.path.join(os.path.dirname(__file__), '..', 'fb_dom_dump.html')
    with open(dump_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
        
    print(f"\n✅ SUKSES! HTML telah disimpan di: fb_dom_dump.html")
    print("Silakan kabari AI bahwa file sudah siap dibaca!")
    
    driver.quit()

if __name__ == "__main__":
    main()
