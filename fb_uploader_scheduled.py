import os
import json
import time
import random
import sys
import re
from datetime import datetime, timedelta
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from utils import setup_driver, cleanup_profile
from fb_uploader import manual_fallback

def human_delay(min_sec=2, max_sec=5):
    time.sleep(random.uniform(min_sec, max_sec))

def get_media_from_folder(folder_path):
    valid_ext = (".mp4", ".jpg", ".png", ".jpeg", ".webp")
    media = []
    if os.path.exists(folder_path):
        for f in os.listdir(folder_path):
            if f.lower().endswith(valid_ext):
                media.append(os.path.abspath(os.path.join(folder_path, f)))
    media.sort()
    return media

def run_fb_scheduled_task(driver, profile_name, folder_post, schedule_time):
    wait = WebDriverWait(driver, 30)
    folder_name = os.path.basename(folder_post)
    media_files = get_media_from_folder(folder_post)
    
    if not media_files:
        print(f"    [!] Skip: Tidak ada media di {folder_name}")
        return False

    meta_file = os.path.join(folder_post, "post_meta.json")
    meta = {}
    if os.path.exists(meta_file):
        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        except: pass
    
    title = meta.get('post_title') or folder_name.replace("_", " ").replace("-", " ").title()
    summary = meta.get('summary', '').strip()
    cta = meta.get('cta', '').strip()
    hashtags = meta.get('hashtags', [])
    
    # Format Hashtags: Pastikan diawali # dan dipisahkan spasi
    formatted_tags = ""
    if hashtags:
        tags_list = [f"#{tag.lstrip('#').strip()}" for tag in hashtags if tag.strip()]
        formatted_tags = " ".join(tags_list)

    # Gabungkan semua komponen
    caption_parts = []
    if title: caption_parts.append(f"*{title}*") # Tebalkan judul (opsional, FB mendukung beberapa formatting)
    if summary: caption_parts.append(summary)
    if cta: caption_parts.append(cta)
    if formatted_tags: caption_parts.append(formatted_tags)
    
    caption_text = "\n\n".join(caption_parts).strip()

    try:
        print(f"[*] Memproses {folder_name} -> Jadwal: {schedule_time}")
        driver.get("https://www.facebook.com/")
        time.sleep(5)

        # 1. Buka Dialog Post
        post_xpath = "//div[@role='button']//span[contains(text(), 'Apa yang Anda pikirkan')] | //div[@role='button']//span[contains(text(), \"What's on your mind\")]"
        wait.until(EC.element_to_be_clickable((By.XPATH, post_xpath))).click()
        wait.until(EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']")))
        human_delay(1, 1.5)

        # 2. Upload Media & Caption
        print(f"    [*] Mengunggah {len(media_files)} file media & Menyuntikkan caption...")
        driver.execute_script("var t = arguments[0]; var a = document.createElement('textarea'); a.value = t; document.body.appendChild(a); a.select(); document.execCommand('copy'); document.body.removeChild(a);", caption_text)
        
        file_input = driver.find_element(By.XPATH, "//input[@type='file']")
        file_input.send_keys("\n".join(media_files))
        time.sleep(1)
        ActionChains(driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
        
        upload_wait = 5
        print(f"    [*] Menunggu upload selesai (est. {upload_wait} detik)...")
        time.sleep(upload_wait)

        # 4. Penjadwalan
        print("[*] Masuk ke tahap penjadwalan...")
        next_btn_xpath = (
            "//div[@role='dialog']//div[@aria-label='Berikutnya'][not(contains(@aria-label, 'Pemirsa'))]"
            "| //div[@role='dialog']//div[@aria-label='Next']"
            "| //div[@role='dialog']//div[@role='button']//span[text()='Berikutnya' or text()='Next']"
        )
        opt_xpath = "//div[@role='dialog']//span[contains(text(), 'Opsi penjadwalan')] | //div[@role='dialog']//div[@aria-label='Opsi penjadwalan']"
        
        try:
            # Loop Adaptive: Klik Berikutnya sampai 'Opsi penjadwalan' muncul
            # Berguna untuk Video yang punya layar tambahan "Reels/Video"
            form_found = False
            for i in range(3):
                human_delay(2, 3)
                
                # Cek apakah 'Opsi penjadwalan' sudah ada tanpa klik Next lagi
                opts = driver.find_elements(By.XPATH, opt_xpath)
                if opts and opts[0].is_displayed():
                    target_opt = opts[0]
                    form_found = True
                    break
                
                # Jika belum ada, klik 'Berikutnya'
                buttons = driver.find_elements(By.XPATH, next_btn_xpath)
                visible_next = [btn for btn in buttons if btn.is_displayed()]
                if visible_next:
                    print(f"    [*] Mengklik tombol 'Berikutnya' (Langkah {i+1})...")
                    driver.execute_script("arguments[0].click();", visible_next[-1])
                    time.sleep(3)
                else:
                    print(f"    [!] Tombol 'Berikutnya' tidak terlihat di langkah {i+1}.")
                    break
            
            if not form_found:
                # Coba cari sekali lagi dengan wait formal yang lebih sabar (60 detik)
                # Video biasanya butuh waktu processing lebih lama sebelum menu ini muncul
                print("[*] Mencari menu 'Opsi penjadwalan' secara intensif (menunggu hingga 60 detik)...")
                target_opt = WebDriverWait(driver, 60).until(EC.element_to_be_clickable((By.XPATH, opt_xpath)))

            # Klik Opsi Penjadwalan (SAH)
            driver.execute_script("arguments[0].click();", target_opt)
            print("    [+] Menu 'Opsi penjadwalan' terbuka.")
            time.sleep(2) # Beri waktu container form untuk render sempurna

            # --- PENGATURAN OTOMATIS (SPECIFIC TAB SEQUENCE) ---
            print(f"[*] Menyiapkan waktu posting: {schedule_time}")
            
            dt_obj = datetime.strptime(schedule_time, "%Y-%m-%d %H:%M")
            # Ubah ke format Indonesia: DD/MM/YYYY
            date_val = dt_obj.strftime("%d/%m/%Y") 
            time_val = dt_obj.strftime("%H:%M")

            actions = ActionChains(driver)
            
            # 1. TAB Pertama (Abaikan)
            print("    [*] Navigasi TAB 1 (Abaikan)...")
            actions.send_keys(Keys.TAB).perform()
            time.sleep(0.3)

            # 2. Navigasi ke kotak Tanggal (TAB 2)
            print("    [*] Navigasi TAB 2 (Tanggal)...")
            actions.send_keys(Keys.TAB).perform()
            time.sleep(0.3)
            active_el = driver.switch_to.active_element
            active_el.send_keys(Keys.CONTROL + "a")
            active_el.send_keys(Keys.BACKSPACE)
            active_el.send_keys(date_val)
            time.sleep(0.2)
            active_el.send_keys(Keys.ENTER)
            print("    [+] Tanggal di-ENTER.")
            time.sleep(0.3)

            # 3. Navigasi ke kotak Waktu (TAB 3)
            print("    [*] Navigasi TAB 3 (Waktu)...")
            actions.send_keys(Keys.TAB).perform()
            time.sleep(0.3)
            active_el = driver.switch_to.active_element
            active_el.send_keys(Keys.CONTROL + "a")
            active_el.send_keys(Keys.BACKSPACE)
            active_el.send_keys(time_val)
            time.sleep(0.2)
            active_el.send_keys(Keys.ENTER)
            print("    [+] Jam di-ENTER.")
            time.sleep(0.3)

            # 4. Navigasi ke tombol Konfirmasi (TAB 4)
            print("    [*] Navigasi TAB 4 (Konfirmasi)...")
            actions.send_keys(Keys.TAB).perform()
            time.sleep(0.4)
            active_el = driver.switch_to.active_element
            print(f"    [*] Menekan ENTER pada: {active_el.text or 'Tombol Biru'}")
            active_el.send_keys(Keys.ENTER)
            
            time.sleep(1)

            # 4. Klik Jadwalkan FINAL
            print("[*] Mengklik tombol 'Jadwalkan' final...")
            final_xpath = "//div[@role='dialog']//div[@role='button']//span[text()='Jadwalkan' or text()='Schedule']"
            final_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, final_xpath)))
            driver.execute_script("arguments[0].click();", final_btn)
            
            with open(os.path.join(folder_post, "uploadedfb.txt"), "w") as f:
                f.write(f"Dijadwalkan: {schedule_time}")
            
            print(f"    [+] {folder_name} BERHASIL dijadwalkan.")
            time.sleep(5)
            return True

        except Exception as e:
            print(f"    [-] Gagal menjadwalkan: {e}")
            manual_fallback(driver, "Silakan selesaikan penjadwalan secara manual di VNC.")
            return False

    except Exception as e:
        print(f"    [!] Error: {e}")
        return False

if __name__ == "__main__":
    print("\n=== FB BATCH SCHEDULED UPLOADER (COORDINATE MODE) ===")
    
    profile_dir = os.path.join(os.getcwd(), "fb_profiles")
    profiles = sorted([d for d in os.listdir(profile_dir) if os.path.isdir(os.path.join(profile_dir, d))])
    if not profiles: print("[!] Profil kosong."); sys.exit()
    for i, p in enumerate(profiles): print(f"{i+1}. {p}")
    p_idx = int(input("\nPilih Nomor Profil: ")) - 1
    sel_profile = profiles[p_idx]

    parent_folder = input("Masukkan Path Folder Utama: ").strip().replace('"', '').replace("'", "")
    if not os.path.isdir(parent_folder): print("[!] Folder tidak valid!"); sys.exit()

    sub_folders = sorted([os.path.join(parent_folder, d) for d in os.listdir(parent_folder) if os.path.isdir(os.path.join(parent_folder, d))])
    pending_folders = [f for f in sub_folders if not os.path.exists(os.path.join(f, "uploadedfb.txt"))]

    if not pending_folders: print("[!] Tidak ada folder baru."); sys.exit()
    print(f"[+] Ditemukan {len(pending_folders)} sub-folder yang belum di-upload.")

    # --- LOGIKA PRIORITAS DASHBOARD ---
    order_path = os.path.join(parent_folder, "queue_order.json")
    if os.path.exists(order_path):
        try:
            with open(order_path, "r", encoding="utf-8") as f:
                custom_order = json.load(f)
            
            # Buat mapping folder name -> full path untuk pending_folders
            pending_map = {os.path.basename(f): f for f in pending_folders}
            
            ordered_pending = []
            for name in custom_order:
                if name in pending_map:
                    ordered_pending.append(pending_map[name])
                    del pending_map[name] # Hapus agar tidak duplikat
            
            # Tambahkan sisa folder yang mungkin baru dibuat tapi belum ada di order.json
            remaining = list(pending_map.values())
            pending_folders = ordered_pending + remaining
            
            if ordered_pending:
                print("[+] Menggunakan urutan kustom dari Dashboard.")
        except Exception as e:
            print(f"[!] Gagal membaca queue_order.json: {e}")

    num_post = input("Jumlah postingan yang ingin dijadwalkan (Enter = Semua): ").strip()
    limit = int(num_post) if num_post.isdigit() else 0
    
    is_random = input("Acak urutan folder? (y/n): ").lower() == 'y'
    if is_random:
        random.shuffle(pending_folders)
        print("[*] Urutan folder diacak.")
    
    if limit > 0:
        pending_folders = pending_folders[:limit]
        print(f"[*] Memproses {len(pending_folders)} folder terpilih.")

    start_str = input("Waktu Mulai (YYYY-MM-DD HH:MM) [Kosong = Sekarang]: ").strip()
    current_time = datetime.now() + timedelta(minutes=30) if not start_str else datetime.strptime(start_str, "%Y-%m-%d %H:%M")
    interval_mins = int(input("Jeda antar postingan (menit): "))

    driver = setup_driver(os.path.join(os.getcwd(), "fb_profiles", sel_profile), headless=False)
    try:
        for folder in pending_folders:
            sched_str = current_time.strftime("%Y-%m-%d %H:%M")
            if run_fb_scheduled_task(driver, sel_profile, folder, sched_str):
                current_time += timedelta(minutes=interval_mins)
            else:
                if input("[?] Lanjut? (y/n): ").lower() != 'y': break
    finally:
        driver.quit()
