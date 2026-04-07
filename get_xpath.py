import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils import setup_driver, cleanup_profile

def main():
    print("\n" + "="*50)
    print("SKRIP PEMBANTU IDENTIFIKASI ELEMEN (ULTIMATE)")
    print("="*50)

    while True:
        url_input = input("[?] Masukkan URL yang ingin dibuka (WAJIB): ").strip()
        if url_input:
            target_url = url_input if url_input.startswith(('http://', 'https://')) else "https://" + url_input
            break
        print("[!] URL tidak boleh kosong!")
    
    profile_path = os.path.join(os.getcwd(), "tiktok_profile")
    if not os.path.exists(profile_path):
        os.makedirs(profile_path)
    
    cleanup_profile(profile_path)
    driver = setup_driver(profile_path)
    wait = WebDriverWait(driver, 30)

    try:
        print(f"[*] Membuka halaman: {target_url}")
        if "com.termux" in os.environ.get("PREFIX", ""):
            print("    [!] BUKA VNC VIEWER SEKARANG! Sambungkan ke alamat: 127.0.0.1:5901")
        driver.get(target_url)
        
        # Opsi Upload Video TikTok (Opsional)
        if "tiktok.com" in target_url and "upload" in target_url:
            if input("[?] Ingin upload video contoh otomatis? (y/n): ").lower() == 'y':
                try:
                    video_path = os.path.abspath("Post/ai-cerdas-sortir-tomat-petani-modern/ai-cerdas-sortir-tomat-petani-modern.mp4")
                    if os.path.exists(video_path):
                        wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='file']"))).send_keys(video_path)
                        print("[+] Upload dipicu.")
                        time.sleep(5)
                    else: print(f"[!] File tidak ada: {video_path}")
                except Exception as e: print(f"[!] Gagal upload: {e}")

        # Injeksi Script JS Deteksi Klik
        js_script = """
        window.is_logging = false;
        document.addEventListener('click', function(e) {
            if (!window.is_logging) return;
            var el = e.target;
            var getXP = function(node) {
                var xp = '';
                for (; node && node.nodeType == 1; node = node.parentNode) {
                    var idx = 0;
                    for (var s = node.previousSibling; s; s = s.previousSibling) {
                        if (s.nodeType == 1 && s.nodeName == node.nodeName) idx++;
                    }
                    xp = '/' + node.nodeName.toLowerCase() + (idx > 0 ? '[' + (idx + 1) + ']' : '') + xp;
                }
                return xp;
            };
            console.error("CLICK_DETECTED|" + getXP(el) + "|" + el.outerHTML.substring(0, 150));
        }, true);
        """
        driver.execute_script(js_script)
        
        input("\n[!] Navigasi dulu di VNC, lalu tekan ENTER di sini untuk mulai Logging XPath...")
        
        driver.execute_script("window.is_logging = true;")
        print("\n[+] LOGGING AKTIF! Klik elemen di browser untuk melihat XPath-nya.")
        print("[+] Tekan Ctrl+C untuk berhenti.\n")

        # Bersihkan log & Mulai monitoring
        driver.get_log('browser')
        while True:
            for entry in driver.get_log('browser'):
                if "CLICK_DETECTED" in entry['message']:
                    parts = entry['message'].split("|")
                    if len(parts) >= 3:
                        print(f"\nXPath : {parts[1]}\nHTML  : {parts[2]}...")
                        print("-" * 20)
            time.sleep(0.5)

    except KeyboardInterrupt: print("\nBerhenti...")
    finally:
        driver.quit()
        cleanup_profile(profile_path)

if __name__ == "__main__":
    main()