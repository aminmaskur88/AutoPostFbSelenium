import os
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Deteksi Environment (Termux Android atau PC Desktop)
IS_TERMUX = "com.termux" in os.environ.get("PREFIX", "")
if IS_TERMUX:
    CHROME_PATH = "/data/data/com.termux/files/usr/bin/chromium-browser"
    CHROMEDRIVER_PATH = "/data/data/com.termux/files/usr/bin/chromedriver"
else:
    CHROME_PATH = None
    CHROMEDRIVER_PATH = None

PROFILE_PATH = os.path.join(os.getcwd(), "tiktok_profile")

def setup_driver():
    chrome_options = Options()
    if CHROME_PATH:
        chrome_options.binary_location = CHROME_PATH
    
    chrome_options.add_argument(f"--user-data-dir={PROFILE_PATH}")
    chrome_options.add_argument("--profile-directory=Default")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    
    # Aktifkan log browser
    chrome_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    
    if IS_TERMUX and CHROMEDRIVER_PATH:
        service = Service(CHROMEDRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=chrome_options)
    else:
        # Biarkan Selenium di PC mengunduh/mencari driver otomatis
        driver = webdriver.Chrome(options=chrome_options)

    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def main():
    print("\n" + "="*50)
    print("SKRIP PEMBANTU IDENTIFIKASI ELEMEN (ULTIMATE)")
    print("="*50)

    # 1. Input URL Wajib
    while True:
        url_input = input("[?] Masukkan URL yang ingin dibuka (WAJIB): ").strip()
        if url_input:
            if not url_input.startswith(('http://', 'https://')):
                target_url = "https://" + url_input
            else:
                target_url = url_input
            break
        print("[!] URL tidak boleh kosong!")
    
    driver = setup_driver()
    wait = WebDriverWait(driver, 30)

    try:
        print(f"[*] Membuka halaman: {target_url}")
        driver.get(target_url)
        
        # 2. Opsi Upload Otomatis (Hanya jika di halaman TikTok)
        if "tiktok.com" in target_url and "upload" in target_url:
            do_upload = input("[?] Ingin upload video contoh otomatis? (y/n): ").lower()
            if do_upload == 'y':
                try:
                    print("[*] Mencari input file...")
                    file_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='file']")))
                    video_path = os.path.abspath("Post/ai-cerdas-sortir-tomat-petani-modern/ai-cerdas-sortir-tomat-petani-modern.mp4")
                    if os.path.exists(video_path):
                        file_input.send_keys(video_path)
                        print(f"[+] Berhasil memicu upload video.")
                        time.sleep(5)
                    else:
                        print(f"[!] File tidak ditemukan: {video_path}")
                except Exception as e:
                    print(f"[!] Gagal upload: {e}")

        # 3. Injeksi Script JS Deteksi Klik
        js_script = """
        window.is_logging = false;
        console.warn("JS_READY");
        document.addEventListener('click', function(e) {
            if (!window.is_logging) return;
            e = e || window.event;
            var element = e.target || e.srcElement;
            function getXPath(el) {
                var xpath = '';
                while (el && el.nodeType === Node.ELEMENT_NODE) {
                    var index = 0;
                    var sibling = el.previousSibling;
                    while (sibling) {
                        if (sibling.nodeType === Node.ELEMENT_NODE && sibling.nodeName === el.nodeName) { index++; }
                        sibling = sibling.previousSibling;
                    }
                    var tagName = el.nodeName.toLowerCase();
                    var pathIndex = (index > 0 ? '[' + (index + 1) + ']' : '');
                    xpath = '/' + tagName + pathIndex + xpath;
                    el = el.parentNode;
                }
                return xpath;
            }
            var xp = getXPath(element);
            console.error("CLICK_DETECTED|" + xp + "|" + element.outerHTML.substring(0, 200));
        }, true);
        """
        driver.execute_script(js_script)
        
        print("\n" + "-"*30)
        print("[!] Silakan navigasi ke elemen yang diinginkan di VNC.")
        print("[!] Jika sudah siap mengambil XPath, tekan ENTER di terminal ini.")
        print("-"*30)
        input() # Menunggu instruksi user
        
        driver.execute_script("window.is_logging = true;")
        print("\n[+] LOGGING AKTIF! Silakan KLIK elemen di VNC untuk melihat XPath-nya.")
        print("[+] Tekan Ctrl+C untuk berhenti.\\n")

        # Bersihkan log lama sebelum mulai
        driver.get_log('browser')

        while True:
            logs = driver.get_log('browser')
            for entry in logs:
                msg = entry['message']
                if "CLICK_DETECTED" in msg:
                    if "|" in msg:
                        parts = msg.split("|")
                        if len(parts) >= 3:
                            xpath_val = parts[1]
                            html_val = parts[2].replace('\\"', '"').strip()
                            print(f"\\nXPath : {xpath_val}")
                            print(f"HTML  : {html_val[:150]}...")
                            print("-" * 20)
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nBerhenti...")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
