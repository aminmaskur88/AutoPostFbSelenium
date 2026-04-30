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

def get_media_files(path):
    valid_ext = (".mp4", ".jpg", ".png", ".jpeg", ".webp")
    if os.path.isfile(path):
        return [os.path.abspath(path)] if path.lower().endswith(valid_ext) else []
    
    media = []
    if os.path.exists(path):
        for f in os.listdir(path):
            if f.lower().endswith(valid_ext):
                media.append(os.path.abspath(os.path.join(path, f)))
    media.sort()
    return media

def run_fb_scheduled_task(driver, profile_name, post_path, schedule_time):
    wait = WebDriverWait(driver, 30)
    item_name = os.path.basename(post_path)
    is_file = os.path.isfile(post_path)
    
    media_files = get_media_files(post_path)
    if not media_files:
        print(f"    [!] Skip: Tidak ada media di {item_name}")
        return False

    # Metadata Logic
    meta = {}
    if not is_file:
        meta_file = os.path.join(post_path, "post_meta.json")
        if os.path.exists(meta_file):
            try:
                with open(meta_file, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
            except: pass
    
    # Smart Title: Dari meta atau Nama Folder/File (tanpa _ dan extension)
    clean_name = os.path.splitext(item_name)[0] if is_file else item_name
    clean_title = clean_name.replace("_", " ").replace("-", " ").title()
    
    title = meta.get('post_title') or clean_title
    summary = meta.get('summary', '').strip()
    cta = meta.get('cta', '').strip()
    hashtags = meta.get('hashtags', [])
    
    formatted_tags = ""
    if hashtags:
        tags_list = [f"#{tag.lstrip('#').strip()}" for tag in hashtags if tag.strip()]
        formatted_tags = " ".join(tags_list)

    caption_parts = []
    if title: caption_parts.append(title)
    if summary: caption_parts.append(summary)
    if cta: caption_parts.append(cta)
    if formatted_tags: caption_parts.append(formatted_tags)
    
    caption_text = "\n\n".join(caption_parts).strip()

    try:
        print(f"[*] Memproses {item_name} -> Jadwal: {schedule_time}")
        driver.get("https://www.facebook.com/")
        time.sleep(5)

        # 1. Buka Dialog Post
        post_xpath = "//div[@role='button']//span[contains(text(), 'Apa yang Anda pikirkan')] | //div[@role='button']//span[contains(text(), \"What's on your mind\")]"
        wait.until(EC.element_to_be_clickable((By.XPATH, post_xpath))).click()
        wait.until(EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']")))
        human_delay(1, 1.5)

        # 2. Upload Media & Caption
        print(f"    [*] Mengunggah {len(media_files)} media & Menyuntikkan caption...")
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
            form_found = False
            for i in range(3):
                human_delay(2, 3)
                opts = driver.find_elements(By.XPATH, opt_xpath)
                if opts and opts[0].is_displayed():
                    target_opt = opts[0]
                    form_found = True
                    break
                
                buttons = driver.find_elements(By.XPATH, next_btn_xpath)
                visible_next = [btn for btn in buttons if btn.is_displayed()]
                if visible_next:
                    print(f"    [*] Mengklik tombol 'Berikutnya' (Langkah {i+1})...")
                    driver.execute_script("arguments[0].click();", visible_next[-1])
                    time.sleep(3)
                else: break
            
            if not form_found:
                print("[*] Mencari menu 'Opsi penjadwalan' intensif (60s)...")
                target_opt = WebDriverWait(driver, 60).until(EC.element_to_be_clickable((By.XPATH, opt_xpath)))

            driver.execute_script("arguments[0].click();", target_opt)
            print("    [+] Menu 'Opsi penjadwalan' terbuka.")
            time.sleep(2)

            # --- PENGATURAN OTOMATIS (MODE STABIL) ---
            dt_obj = datetime.strptime(schedule_time, "%Y-%m-%d %H:%M")
            date_val, time_val = dt_obj.strftime("%d/%m/%Y"), dt_obj.strftime("%H:%M")
            actions = ActionChains(driver)
            
            # 1. TAB Pertama (Abaikan)
            actions.send_keys(Keys.TAB).perform()
            time.sleep(1)

            # 2. Navigasi ke kotak Tanggal (TAB 2)
            actions.send_keys(Keys.TAB).perform()
            time.sleep(0.8)
            active_el = driver.switch_to.active_element
            active_el.send_keys(Keys.CONTROL + "a")
            active_el.send_keys(Keys.BACKSPACE)
            active_el.send_keys(date_val)
            time.sleep(0.5)
            active_el.send_keys(Keys.ENTER)
            time.sleep(0.8)
            
            # 3. Navigasi ke kotak Waktu (TAB 3)
            actions.send_keys(Keys.TAB).perform()
            time.sleep(0.8)
            active_el = driver.switch_to.active_element
            active_el.send_keys(Keys.CONTROL + "a")
            active_el.send_keys(Keys.BACKSPACE)
            active_el.send_keys(time_val)
            time.sleep(0.5)
            active_el.send_keys(Keys.ENTER)
            time.sleep(0.8)
            
            # 4. Navigasi ke tombol Konfirmasi (TAB 4)
            actions.send_keys(Keys.TAB).perform()
            time.sleep(1)
            driver.switch_to.active_element.send_keys(Keys.ENTER)
            time.sleep(2)

            final_xpath = "//div[@role='dialog']//div[@role='button']//span[text()='Jadwalkan' or text()='Schedule']"
            final_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, final_xpath)))
            driver.execute_script("arguments[0].click();", final_btn)
            
            # Marker Upload
            marker_file = post_path + ".uploadedfb" if is_file else os.path.join(post_path, "uploadedfb.txt")
            with open(marker_file, "w") as f:
                f.write(f"Dijadwalkan: {schedule_time}")
            
            print(f"    [+] {item_name} BERHASIL dijadwalkan.")
            time.sleep(5)
            return True

        except Exception as e:
            print(f"    [-] Gagal: {e}")
            manual_fallback(driver, "Selesaikan manual di VNC.")
            return False

    except Exception as e:
        print(f"    [!] Error: {e}"); return False

if __name__ == "__main__":
    print("\n=== FB SMART SCHEDULED UPLOADER ===")
    
    profile_dir = os.path.join(os.getcwd(), "fb_profiles")
    profiles = sorted([d for d in os.listdir(profile_dir) if os.path.isdir(os.path.join(profile_dir, d))])
    if not profiles: print("[!] Profil kosong."); sys.exit()
    for i, p in enumerate(profiles): print(f"{i+1}. {p}")
    sel_profile = profiles[int(input("\nPilih Profil: "))-1]

    parent_folder = input("Masukkan Path Folder Utama: ").strip().replace('"', '').replace("'", "")
    if not os.path.isdir(parent_folder): print("[!] Folder tidak valid!"); sys.exit()

    # DETEKSI SMART: Sub-folder vs Direct Files
    items = sorted([os.path.join(parent_folder, f) for f in os.listdir(parent_folder)])
    pending_items = []
    
    for item in items:
        if os.path.isdir(item):
            if not os.path.exists(os.path.join(item, "uploadedfb.txt")):
                pending_items.append(item)
        elif os.path.isfile(item) and item.lower().endswith((".mp4", ".jpg", ".png", ".jpeg", ".webp")):
            if not os.path.exists(item + ".uploadedfb"):
                pending_items.append(item)

    if not pending_items: print("[!] Tidak ada konten baru."); sys.exit()
    print(f"[+] Ditemukan {len(pending_items)} item (folder/file) baru.")

    # Sort berdasarkan Dashboard jika ada
    order_path = os.path.join(parent_folder, "queue_order.json")
    if os.path.exists(order_path):
        try:
            with open(order_path, "r", encoding="utf-8") as f:
                custom_order = json.load(f)
            p_map = {os.path.basename(p): p for p in pending_items}
            ordered = [p_map[name] for name in custom_order if name in p_map]
            pending_items = ordered + [p for p in pending_items if p not in ordered]
            print("[+] Menggunakan urutan Dashboard.")
        except: pass

    num_post = input("Jumlah postingan (Enter = Semua): ").strip()
    limit = int(num_post) if num_post.isdigit() else 0
    if input("Acak urutan? (y/n): ").lower() == 'y': random.shuffle(pending_items)
    if limit > 0: pending_items = pending_items[:limit]

    start_str = input("Waktu Mulai (YYYY-MM-DD HH:MM) [Enter = 30m lagi]: ").strip()
    current_time = datetime.now() + timedelta(minutes=30) if not start_str else datetime.strptime(start_str, "%Y-%m-%d %H:%M")
    interval_mins = int(input("Jeda (menit): "))

    driver = setup_driver(os.path.join(os.getcwd(), "fb_profiles", sel_profile), headless=False)
    try:
        for item in pending_items:
            if run_fb_scheduled_task(driver, sel_profile, item, current_time.strftime("%Y-%m-%d %H:%M")):
                current_time += timedelta(minutes=interval_mins)
            else:
                if input("[?] Lanjut? (y/n): ").lower() != 'y': break
    finally: driver.quit()
