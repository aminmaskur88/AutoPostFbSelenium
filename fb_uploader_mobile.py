import os
import json
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

# Konfigurasi Direktori
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS_FILE = os.path.join(BASE_DIR, 'accounts.json')

def clear_screen():
    os.system('clear' if os.name == 'posix' else 'cls')

def setup_browser():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=390,844')
    options.add_argument('--remote-allow-origins=*')
    options.add_argument('--user-agent=Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    if os.path.exists('/data/data/com.termux/files/usr/bin/chromium-browser'):
        options.binary_location = '/data/data/com.termux/files/usr/bin/chromium-browser'
    elif os.path.exists('/data/data/com.termux/files/usr/bin/chromium'):
        options.binary_location = '/data/data/com.termux/files/usr/bin/chromium'
    
    service = Service('/data/data/com.termux/files/usr/bin/chromedriver') if os.path.exists('/data/data/com.termux/files/usr/bin/chromedriver') else None
    return webdriver.Chrome(service=service, options=options) if service else webdriver.Chrome(options=options)

def load_cookies(driver, cookie_file):
    if not os.path.exists(cookie_file): return False
    try:
        with open(cookie_file, 'r') as f:
            cookies = json.load(f)
    except: return False

    driver.get('https://m.facebook.com/')
    time.sleep(3)
    for cookie in cookies:
        if 'sameSite' in cookie and cookie['sameSite'] not in ['Strict', 'Lax', 'None']:
            del cookie['sameSite']
        try: driver.add_cookie(cookie)
        except: pass
    driver.refresh()
    time.sleep(5)
    
    # CEK APAKAH LOGIN BERHASIL
    page_source = driver.page_source.lower()
    if "create new account" in page_source or "buat akun baru" in page_source or "log in" in page_source:
        print(f"[-] Cookie untuk {os.path.basename(cookie_file)} bermasalah atau mati!")
        return False
        
    return True

def generate_main_caption(album_dir):
    """Membaca post_meta.json dan merakit caption."""
    post_meta_path = os.path.join(album_dir, "post_meta.json")
    if not os.path.exists(post_meta_path):
        return os.path.basename(album_dir)

    try:
        with open(post_meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        parts = []
        if meta.get("post_title"):
            parts.append(meta.get("post_title"))
        if meta.get("summary"):
            parts.append(f"\n\n{meta.get('summary')}")
        if meta.get("cta"):
            parts.append(f"\n\n{meta.get('cta')}")
        if meta.get("hashtags"):
            hashtags = meta.get("hashtags")
            if isinstance(hashtags, list):
                formatted_tags = [f"#{tag.lstrip('#').strip()}" for tag in hashtags]
                parts.append(f"\n\n{' '.join(formatted_tags)}")
        
        caption = "".join(parts).strip()
        return caption if caption else os.path.basename(album_dir)
    except Exception as e:
        print(f"[-] Gagal membaca post_meta.json: {e}")
        return os.path.basename(album_dir)

def post_to_facebook(driver, image_paths, caption):
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    
    wait = WebDriverWait(driver, 25)
    print("[*] Mensimulasikan aktivitas manusia (membaca timeline)...")
    driver.get("https://m.facebook.com/")
    
    # Tunggu sampai body muat
    try: wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    except: pass
    time.sleep(random.uniform(3.0, 5.0))
    
    # Scroll bertahap ala manusia
    scroll_times = random.randint(2, 3)
    for _ in range(scroll_times):
        scroll_step = random.randint(300, 600)
        driver.execute_script(f"window.scrollBy(0, {scroll_step});")
        time.sleep(random.uniform(1.5, 3.0))

    # 1. BUKA COMPOSER (DENGAN KLIK DARI HOME - WAJIB!)
    clicked_composer = False
    try:
        print("[*] Mencari kotak status di home...")
        home_selectors = [
            "//*[contains(text(), 'Posting status baru')]",
            "//div[contains(@data-sigil, 'm-feed-composer-status-box')]",
            "//*[contains(text(), 'Apa yang Anda pikirkan')]",
            """//*[contains(text(), "What's on your mind")]""",
            "//a[contains(@href, '/composer/')]"
        ]
        
        for selector in home_selectors:
            try:
                elements = driver.find_elements(By.XPATH, selector)
                for element in elements:
                    if element.is_displayed():
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                        time.sleep(1)
                        driver.execute_script("arguments[0].click();", element)
                        print(f"[+] Berhasil klik kotak status di home.")
                        clicked_composer = True
                        break
                if clicked_composer: break
            except: continue
    except: pass

    if not clicked_composer:
        print("[!] Tidak bisa klik di home, paksa navigasi (Risiko input macet)...")
        driver.get("https://m.facebook.com/composer/")
    
    print("[*] Menunggu composer stabil (10 detik)...")
    time.sleep(10)
    
    try:
        # 2. ISI CAPTION (URUTAN PERTAMA)
        print("[*] Menyuntikkan caption (Metode Brutal)...")
        textarea_xpath = (
            "//div[@role='textbox' and @contenteditable='true'] | "
            "//textarea[@name='status'] | "
            "//textarea[@name='xc_message'] | "
            "//div[@contenteditable='true'] | "
            "//textarea"
        )
        
        input_field = None
        fields = driver.find_elements(By.XPATH, textarea_xpath)
        for f in fields:
            if f.is_displayed():
                input_field = f
                break
        
        if not input_field:
            input_field = wait.until(EC.visibility_of_element_located((By.XPATH, textarea_xpath)))

        print("[+] Area input ditemukan, memulai injeksi...")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", input_field)
        time.sleep(1)
        input_field.click()
        time.sleep(2)
        
        js_input = r'''
            var el = arguments[0];
            var text = arguments[1];
            el.focus();
            if (el.tagName === 'TEXTAREA') { el.value = ''; } 
            else { el.innerHTML = ''; } 

            var dataTransfer = new DataTransfer();
            dataTransfer.setData('text/plain', text);
            el.dispatchEvent(new ClipboardEvent('paste', {
                clipboardData: dataTransfer,
                bubbles: true,
                cancelable: true
            }));

            if (!el.innerText && !el.value) {
                if (el.tagName === 'TEXTAREA') { el.value = text; } 
                else { 
                    el.innerText = text; 
                    var lines = text.split('\\n');
                    var html = '';
                    for (var i=0; i<lines.length; i++) {
                        html += '<div>' + (lines[i] || '<br>') + '</div>';
                    }
                    el.innerHTML = html;
                }
            }

            ['input', 'change', 'blur'].forEach(function(evName) {
                el.dispatchEvent(new Event(evName, { bubbles: true }));
            });
        '''
        driver.execute_script(js_input, input_field, caption)
        time.sleep(5) 
        
        check_text = driver.execute_script("return (arguments[0].value || arguments[0].innerText || '');", input_field)
        if len(check_text.strip()) < 10:
            print("[!] Injeksi JS Clipboard gagal, mencoba memancing fokus ulang...")
            pancingan_xpaths = [
                "//*[contains(text(), 'Posting status baru')]",
                "//*[contains(text(), 'Apa yang Anda pikirkan')]",
                "//*[contains(text(), \"What's on your mind\")]"
            ]
            for px in pancingan_xpaths:
                try:
                    p_elems = driver.find_elements(By.XPATH, px)
                    for p_el in p_elems:
                        if p_el.is_displayed():
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", p_el)
                            time.sleep(1)
                            driver.execute_script("arguments[0].click();", p_el)
                            time.sleep(1.5)
                            break
                except: pass
            
            try:
                ActionChains(driver).send_keys(caption).perform()
            except:
                try: input_field.send_keys(caption)
                except: pass
            time.sleep(3)
            
            check_text = driver.execute_script("return (arguments[0].value || arguments[0].innerText || '');", input_field)
        
        print(f"[+] Caption selesai diproses ({len(check_text)} karakter).")
        
        print("[*] Deaktivasi fokus input (klik area kosong)...")
        driver.execute_script("document.body.click();")
        time.sleep(2)

        # 3. UPLOAD FOTO ATAU VIDEO
        has_video = any(p.lower().endswith(('.mp4', '.mov', '.mkv', '.avi')) for p in image_paths)
        print(f"[*] Mencari tombol upload {'Video' if has_video else 'Foto'}...")
        
        if has_video:
            media_xpath = "//*[contains(text(), 'Video')] | //*[@data-sigil='touchable' and .//*[contains(text(), 'Video')]]"
        else:
            media_xpath = "//*[contains(text(), 'Koleksi Foto')] | //*[contains(text(), 'Foto/Video')] | //*[contains(text(), 'Foto')]"
            
        btn_clicked = False
        media_btns = driver.find_elements(By.XPATH, media_xpath)
        for b in media_btns:
            if b.is_displayed():
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", b)
                    time.sleep(1)
                    driver.execute_script("arguments[0].click();", b)
                    time.sleep(random.uniform(3.0, 5.0))
                    btn_clicked = True
                    break
                except: pass
                
        if not btn_clicked:
            print("[!] Tombol media tidak ditemukan, mencoba bypass langsung ke input file...")

        try:
            file_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='file']")))
            driver.execute_script("arguments[0].style.display = 'block'; arguments[0].style.visibility = 'visible';", file_input)
            
            paths_string = "\\n".join(image_paths)
            file_input.send_keys(paths_string)
            print(f"[*] Mengupload {len(image_paths)} file media...")
            time.sleep(random.uniform(10.0, 15.0))
        except Exception as e:
            print(f"[-] Gagal upload media: {e}")
            return False
            
        # 4. TEKAN TOMBOL POSTING
        print("[*] Mencari tombol POSTING...")
        post_selectors = [
            "//div[@role='button' and .//*[contains(text(), 'POSTING')]]",
            "//div[@role='button' and contains(., 'POSTING')]",
            "//button[@type='submit' and contains(., 'POSTING')]",
            "//*[text()='POSTING' and @role='button']",
            "//div[contains(@data-sigil, 'submit')]//div[contains(., 'POSTING')]",
            "//div[@role='button' and contains(., 'KIRIM')]",
            "//div[@role='button' and contains(., 'POST')]"
        ]
        
        post_btn = None
        for ps in post_selectors:
            btns = driver.find_elements(By.XPATH, ps)
            for btn in btns:
                if btn.is_displayed() and btn.is_enabled():
                    post_btn = btn
                    break
            if post_btn: break

        if post_btn:
            print(f"[+] Ditemukan tombol Posting, mengirim...")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", post_btn)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", post_btn)
            
            if has_video:
                upload_wait = int(len(image_paths) * random.uniform(40.0, 70.0) + 60.0)
                print(f"[*] Post ditekan! Sedang mengunggah VIDEO SEBENARNYA...")
                for sisa in range(upload_wait, 0, -1):
                    menit = sisa // 60
                    detik = sisa % 60
                    print(f"\r[!] Sisa waktu upload: {menit:02d}:{detik:02d} - Jangan tutup script! ", end="", flush=True)
                    time.sleep(1)
                print("\\n[+] Waktu tunggu upload selesai!")
            else:
                upload_wait = int(random.uniform(15.0, 25.0))
                print(f"[*] Menunggu proses pengiriman selesai...")
                for sisa in range(upload_wait, 0, -1):
                    print(f"\r[!] Sisa waktu: {sisa:02d} detik... ", end="", flush=True)
                    time.sleep(1)
                print("\\n[+] Selesai!")
                
            return True
        else:
            print("[-] Gagal menemukan tombol POSTING.")
            return False
            
    except Exception as e:
        print(f"[-] Terjadi kesalahan: {e}")
        return False

def load_accounts():
    accounts = {}
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, 'r') as f:
                accounts = json.load(f)
        except:
            pass

    # Auto-detect dari folder Cookies
    cookies_dir = os.path.join(BASE_DIR, "Cookies")
    if os.path.exists(cookies_dir):
        for f_name in os.listdir(cookies_dir):
            if f_name.endswith(".json"):
                # Menentukan nama akun dari nama file
                acc_name = f_name.replace("cookies_", "").replace("_cookies", "").replace(".json", "")
                
                if acc_name not in accounts:
                    accounts[acc_name] = {
                        "cookie_file": f_name,
                        "folder_path": ""
                    }
                else:
                    accounts[acc_name]["cookie_file"] = f_name

    # Clean up file cookie yang tidak ada fisiknya
    valid_accounts = {}
    for acc_name, acc_data in accounts.items():
        cookie_path = os.path.join(BASE_DIR, "Cookies", acc_data["cookie_file"])
        if os.path.exists(cookie_path) or not os.path.exists(cookies_dir):
            valid_accounts[acc_name] = acc_data
            
    return valid_accounts

def save_accounts(accounts):
    with open(ACCOUNTS_FILE, 'w') as f:
        json.dump(accounts, f, indent=4)

def run_fb_simulation_mobile(account_name, acc_data, target_folders, is_auto=True, interval=120):
    cookie_file = os.path.join(BASE_DIR, "Cookies", acc_data["cookie_file"])
    
    print(f"[*] Membuka browser siluman (Headless)...")
    driver = setup_browser()
    if not load_cookies(driver, cookie_file):
        print(f"[-] Gagal memuat cookies dari {os.path.basename(cookie_file)}.")
        driver.quit()
        return

    print(f"[+] Login berhasil untuk akun {account_name}.\n")
    
    sukses, gagal = 0, 0
    for idx, folder_path in enumerate(target_folders):
        album_name = os.path.basename(folder_path)
        print(f"\n[ PROGRESS: {idx+1}/{len(target_folders)} ]")
        print(f"[*] Memproses folder album: {album_name}")
        
        valid_exts = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.mov', '.mkv', '.avi')
        image_files = sorted([os.path.abspath(os.path.join(folder_path, f)) for f in os.listdir(folder_path) if f.lower().endswith(valid_exts)])
        
        if not image_files:
            print(f"[-] Tidak ada file media di dalam folder '{album_name}'. Melewati...")
            continue
            
        caption = generate_main_caption(folder_path)
        
        if post_to_facebook(driver, image_files, caption):
            print(f"[+] SUKSES Memposting Album: {album_name}")
            with open(os.path.join(folder_path, "uploadedfb.txt"), 'w') as f:
                f.write(f"Selesai: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            sukses += 1
        else:
            print(f"[-] GAGAL Memposting Album: {album_name}")
            driver.save_screenshot(f"error_album_{album_name.replace(' ', '_')}.png")
            gagal += 1
            
        if is_auto and idx < len(target_folders) - 1:
            variasi_acak = random.randint(-15, 15)
            delay_detik = max(60, int((interval + variasi_acak) * 60))
            print(f"\n[*] Upload selesai. Menunggu sekitar {interval} menit untuk folder berikutnya...")
            for sisa in range(delay_detik, 0, -1):
                m = sisa // 60
                d = sisa % 60
                print(f"\r[⏳] Jeda menuju post berikutnya: {m:02d} menit {d:02d} detik... ", end="", flush=True)
                time.sleep(1)
            print("\n")
            
    print(f"\n[*] Selesai! Sukses: {sukses}, Gagal: {gagal}")
    driver.quit()

if __name__ == '__main__':
    import sys
    while True:
        clear_screen()
        print("\n=== AUTO POST FACEBOOK ALBUM BROWSER ===")
        print("1. Upload Konten\n2. Manajemen Akun\n3. Keluar")
        
        choice = input("Pilih (1-3): ").strip()
        if choice == '3': sys.exit()
        
        elif choice == '2':
            accounts = load_accounts()
            print("\n--- MANAJEMEN AKUN ---")
            acc_names = list(accounts.keys())
            if not acc_names:
                print("[!] Belum ada akun. Letakkan file cookie .json di folder 'Cookies/' atau gunakan opsi Tambah.")
            for i, p in enumerate(acc_names): 
                folder = accounts[p].get('folder_path', '')
                print(f"{i+1}. {p} (Folder: {folder if folder else 'Belum Diatur'})")
            print("--------------------")
            print("[+] Tambah Akun Manual (ketik 'tambah')")
            print("[-] Hapus Akun (ketik 'hapus')")
            print("[0] Kembali")
            
            sub_choice = input("\nPilih opsi (Ketik angka untuk atur folder): ").strip().lower()
            if sub_choice == '0': continue
            elif sub_choice == 'hapus':
                h_idx = input("Pilih nomor akun yang ingin dihapus (0 untuk batal): ").strip()
                try:
                    h_idx = int(h_idx)
                    if 1 <= h_idx <= len(acc_names):
                        nama_hapus = acc_names[h_idx-1]
                        cookie_hapus = accounts[nama_hapus]["cookie_file"]
                        del accounts[nama_hapus]
                        save_accounts(accounts)
                        if os.path.exists(os.path.join(BASE_DIR, "Cookies", cookie_hapus)):
                            os.remove(os.path.join(BASE_DIR, "Cookies", cookie_hapus))
                        print(f"[+] Akun {nama_hapus} berhasil dihapus!")
                        time.sleep(2)
                except: pass
            elif sub_choice == 'tambah':
                nama_akun = input("Masukkan Nama Akun: ").strip()
                folder_path = input("Masukkan Path Folder Target (misal: /storage/emulated/0/FolderAkun): ").strip()
                
                # Pastikan folder Cookies ada
                cookies_dir = os.path.join(BASE_DIR, "Cookies")
                if not os.path.exists(cookies_dir):
                    os.makedirs(cookies_dir)
                    
                cookie_file_name = f"cookies_{nama_akun.replace(' ', '_')}.json"
                cookie_file_path = os.path.join(cookies_dir, cookie_file_name)
                
                print(f"\n[!] Buka ekstensi EditThisCookie di PC, copy cookies-nya.")
                cookie_input = input("Paste Cookie (atau biarkan kosong lalu tekan Enter): ").strip()
                
                if cookie_input:
                    try:
                        json.loads(cookie_input)
                        with open(cookie_file_path, 'w') as f: f.write(cookie_input)
                        print(f"[+] Cookies berhasil disimpan ke {cookie_file_name}")
                    except:
                        with open(cookie_file_path, 'w') as f: f.write("[]")
                else:
                    with open(cookie_file_path, 'w') as f: f.write("[]")
                
                accounts[nama_akun] = {
                    "cookie_file": cookie_file_name,
                    "folder_path": folder_path
                }
                save_accounts(accounts)
                print(f"[+] Akun {nama_akun} berhasil ditambahkan!")
                time.sleep(2)
            else:
                try:
                    idx = int(sub_choice) - 1
                    if 0 <= idx < len(acc_names):
                        p = acc_names[idx]
                        path = input(f"Path baru untuk {p} (kosongkan jika tidak ingin ubah): ").strip()
                        if path:
                            accounts[p]["folder_path"] = path
                            save_accounts(accounts)
                            print("[+] Berhasil disimpan.")
                            time.sleep(1)
                except: pass

        elif choice == '1':
            accounts = load_accounts()
            if not accounts: print("[!] Akun kosong. Tambah akun di menu 2."); time.sleep(2); continue
            
            acc_names = list(accounts.keys())
            for i, p in enumerate(acc_names): print(f"{i+1}. {p}")
            try:
                p_idx = int(input("Pilih Akun: ")) - 1
                if p_idx < 0 or p_idx >= len(acc_names): continue
                p = acc_names[p_idx]
                acc_data = accounts[p]
                base_dir = acc_data.get("folder_path", "")
                
                if not base_dir or not os.path.exists(base_dir):
                    print(f"[!] Folder {base_dir} tidak ditemukan atau belum disetting! Atur folder dulu di menu 2.")
                    time.sleep(2); continue
                
                # Filter folder yang valid (punya media DAN belum diupload)
                folders = []
                for f in sorted(os.listdir(base_dir)):
                    f_path = os.path.join(base_dir, f)
                    if os.path.isdir(f_path) and not os.path.exists(os.path.join(f_path, "uploadedfb.txt")):
                        # Cek apakah ada file media di dalamnya
                        valid_exts = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.mov', '.mkv', '.avi')
                        has_media = any(file.lower().endswith(valid_exts) for file in os.listdir(f_path))
                        if has_media:
                            folders.append(f)
                
                if not folders: 
                    print("[!] Tidak ada album baru untuk diunggah.")
                    time.sleep(2); continue
                
                print(f"\n--- Ditemukan {len(folders)} folder ---")
                print("1. Manual\n2. Auto All")
                mode = input("Pilih mode: ").strip()
                
                if mode == '1':
                    for i, f in enumerate(folders): print(f"{i+1}. {f}")
                    f_idx = int(input("Nomor Folder: ")) - 1
                    target_folders = [os.path.join(base_dir, folders[f_idx])]
                    run_fb_simulation_mobile(p, acc_data, target_folders, is_auto=False)
                elif mode == '2':
                    interval = input("Interval (menit) [Default: 120]: ").strip()
                    interval = int(interval) if interval else 120
                    target_folders = [os.path.join(base_dir, f) for f in folders]
                    run_fb_simulation_mobile(p, acc_data, target_folders, is_auto=True, interval=interval)
            except Exception as e: print(f"[!] Error: {e}"); time.sleep(2)