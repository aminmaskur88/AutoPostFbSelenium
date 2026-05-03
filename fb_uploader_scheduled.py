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

def update_post_status(post_path, status, progress=0):
    """Update status file for Web Dashboard to read."""
    # Selalu arahkan ke upload_status.json di folder yang bersangkutan
    if os.path.isfile(post_path):
        # Jika itu file, simpan di folder file tersebut
        status_file = os.path.join(os.path.dirname(post_path), "upload_status.json")
    else:
        status_file = os.path.join(post_path, "upload_status.json")
        
    try:
        with open(status_file, "w") as f:
            json.dump({"status": status, "progress": progress, "timestamp": time.time()}, f)
    except: pass

def get_next_folder(base_dir):
    if not os.path.exists(base_dir):
        return None
        
    # --- CEK QUEUE ORDER DARI WEB DASHBOARD ---
    order_path = os.path.join(base_dir, "queue_order.json")
    if os.path.exists(order_path):
        try:
            with open(order_path, "r", encoding="utf-8") as f:
                custom_order = json.load(f)
            
            for f_name in custom_order:
                f_path = os.path.join(base_dir, f_name)
                marker = os.path.join(f_path, "uploadedfb.txt")
                if os.path.isdir(f_path) and not os.path.exists(marker):
                    return f_path
        except: pass
            
    pending = []
    for f in os.listdir(base_dir):
        f_path = os.path.join(base_dir, f)
        if not os.path.isdir(f_path): continue
            
        marker = os.path.join(f_path, "uploadedfb.txt")
        if not os.path.exists(marker):
            media = get_media_files(f_path)
            if media:
                pending.append({'path': f_path, 'ctime': os.path.getmtime(f_path)})
    
    if not pending: return None
    pending.sort(key=lambda x: x['ctime']) # FIFO
    return pending[0]['path']

def run_fb_scheduled_task(driver, profile_name, post_path, schedule_time=None):
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
        update_post_status(post_path, "Membuka Facebook...", 10)
        print(f"[*] Memproses {item_name} -> Jadwal: {schedule_time}")
        driver.get("https://www.facebook.com/")
        time.sleep(5)

        # 1. Buka Dialog Post
        update_post_status(post_path, "Membuka dialog posting...", 20)
        post_xpath = "//div[@role='button']//span[contains(text(), 'Apa yang Anda pikirkan')] | //div[@role='button']//span[contains(text(), \"What's on your mind\")]"
        wait.until(EC.element_to_be_clickable((By.XPATH, post_xpath))).click()
        wait.until(EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']")))
        human_delay(1, 1.5)

        # 2. Upload Media & Caption
        update_post_status(post_path, f"Mengunggah {len(media_files)} media...", 40)
        print(f"    [*] Mengunggah {len(media_files)} media & Menyuntikkan caption...")
        driver.execute_script("var t = arguments[0]; var a = document.createElement('textarea'); a.value = t; document.body.appendChild(a); a.select(); document.execCommand('copy'); document.body.removeChild(a);", caption_text)
        
        file_input = driver.find_element(By.XPATH, "//input[@type='file']")
        file_input.send_keys("\n".join(media_files))
        time.sleep(1)
        ActionChains(driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
        
        # 3. Deteksi Progress Upload
        print(f"    [*] Mendeteksi progress upload media...")
        last_percent = -1
        start_wait = time.time()
        while time.time() - start_wait < 600: # Max 10 menit
            try:
                # Cari angka % di dialog (bisa di teks atau aria-label)
                els = driver.find_elements(By.XPATH, "//div[@role='dialog']//*[contains(text(), '%') or contains(@aria-label, '%')]")
                found_percent = False
                for el in els:
                    txt = el.text or el.get_attribute("aria-label") or ""
                    match = re.search(r'(\d+)%', txt)
                    if match:
                        percent = int(match.group(1))
                        found_percent = True
                        if percent != last_percent:
                            # Update ke dashboard: range 40% - 70% adalah untuk upload media
                            ui_progress = 40 + int(percent * 0.3)
                            update_post_status(post_path, f"Mengunggah media: {percent}%", ui_progress)
                            print(f"\r    [+] Uploading: {percent}%", end="")
                            last_percent = percent
                        break
                
                # Jika indikator % hilang tapi sebelumnya ada, berarti selesai
                if not found_percent and last_percent >= 0:
                    print("\n    [+] Indikator progress hilang, upload selesai.")
                    break
                
                # Fallback: Cek jika tombol 'Berikutnya'/'Next' sudah muncul dan aktif
                if not found_percent and time.time() - start_wait > 5:
                    check_next = driver.find_elements(By.XPATH, "//div[@role='dialog']//div[@aria-label='Berikutnya' or @aria-label='Next' or @aria-label='Selesai' or @aria-label='Done']")
                    if any(b.is_displayed() for b in check_next):
                        print("\n    [+] Tombol navigasi terdeteksi, upload selesai.")
                        break
            except: pass
            time.sleep(2)

        # 4. Posting / Penjadwalan
        update_post_status(post_path, "Tahap akhir (Post/Jadwalkan)...", 70)
        print("[*] Tahap akhir posting...")
        next_btn_xpath = (
            "//div[@role='dialog']//div[@aria-label='Berikutnya'][not(contains(@aria-label, 'Pemirsa'))]"
            "| //div[@role='dialog']//div[@aria-label='Next']"
            "| //div[@role='dialog']//div[@role='button']//span[text()='Berikutnya' or text()='Next']"
        )
        
        try:
            if not schedule_time:
                print("    [*] Mode: Posting SEKARANG")
                post_submit_xpath = (
                    "//div[@role='dialog']//div[@role='button'][not(@aria-haspopup)]"
                    "[not(contains(@aria-label, 'Pemirsa'))][not(contains(@aria-label, 'Audience'))]"
                    "[.//span[contains(text(), 'Kirim') or contains(text(), 'Posting') or contains(text(), 'Post') or contains(text(), 'Selesai')]]"
                    "| //div[@role='dialog']//div[@aria-label='Kirim' or @aria-label='Posting' or @aria-label='Post'][not(@aria-haspopup)]"
                )
                
                # Loop untuk menangani tombol 'Berikutnya' yang muncul berkali-kali
                for i in range(4):
                    human_delay(2, 3)
                    btns = driver.find_elements(By.XPATH, post_submit_xpath)
                    visible_post = [b for b in btns if b.is_displayed()]
                    if visible_post:
                        driver.execute_script("arguments[0].click();", visible_post[-1])
                        print("    [+] Tombol 'Kirim/Post' diklik.")
                        break
                    
                    btns_next = driver.find_elements(By.XPATH, next_btn_xpath)
                    visible_next = [b for b in btns_next if b.is_displayed()]
                    if visible_next:
                        print(f"    [*] Mengklik tombol 'Berikutnya' (Langkah {i+1})...")
                        driver.execute_script("arguments[0].click();", visible_next[-1])
                    else:
                        if i == 3: print("    [!] Tombol Post tidak ditemukan."); return False
            else:
                print(f"    [*] Mode: Penjadwalan -> {schedule_time}")
                opt_xpath = "//div[@role='dialog']//span[contains(text(), 'Opsi penjadwalan')] | //div[@role='dialog']//div[@aria-label='Opsi penjadwalan']"
                
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
                    print("    [*] Mencari menu 'Opsi penjadwalan' intensif (60s)...")
                    target_opt = WebDriverWait(driver, 60).until(EC.element_to_be_clickable((By.XPATH, opt_xpath)))

                driver.execute_script("arguments[0].click();", target_opt)
                print("    [+] Menu 'Opsi penjadwalan' terbuka.")
                time.sleep(2)

                # --- PENGATURAN OTOMATIS (MODE STABIL) ---
                dt_obj = datetime.strptime(schedule_time, "%Y-%m-%d %H:%M")
                date_val, time_val = dt_obj.strftime("%d/%m/%Y"), dt_obj.strftime("%H:%M")
                actions = ActionChains(driver)
                
                # 1. TAB Pertama (Pancing Fokus ke Form)
                actions.send_keys(Keys.TAB).perform(); time.sleep(1)

                # 2. Navigasi ke kotak Tanggal (TAB 2)
                actions.send_keys(Keys.TAB).perform(); time.sleep(1)
                active_el = driver.switch_to.active_element
                active_el.send_keys(Keys.CONTROL + "a"); active_el.send_keys(Keys.BACKSPACE)
                active_el.send_keys(date_val); time.sleep(1)
                active_el.send_keys(Keys.ENTER); time.sleep(1.5) # Enter setelah tanggal
                
                # 3. Navigasi ke kotak Waktu (TAB 3)
                actions.send_keys(Keys.TAB).perform(); time.sleep(1)
                active_el = driver.switch_to.active_element
                active_el.send_keys(Keys.CONTROL + "a"); active_el.send_keys(Keys.BACKSPACE)
                active_el.send_keys(time_val); time.sleep(1)
                active_el.send_keys(Keys.ENTER); time.sleep(1.5) # Enter setelah waktu
                
                actions.send_keys(Keys.TAB).perform(); time.sleep(1)
                driver.switch_to.active_element.send_keys(Keys.ENTER); time.sleep(2)

                final_xpath = "//div[@role='dialog']//div[@role='button']//span[text()='Jadwalkan' or text()='Schedule']"
                final_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, final_xpath)))
                driver.execute_script("arguments[0].click();", final_btn)
            
            print("    [*] Menunggu konfirmasi akhir...")
            
            # --- PENANGANAN DIALOG WHATSAPP / SHARE ---
            time.sleep(5)
            try:
                whatsapp_xpath = "//div[@role='dialog']//span[contains(text(), 'WhatsApp')] | //div[@role='dialog']//span[contains(text(), 'Bagikan')] | //div[@role='dialog']//div[@aria-label='Tutup' or @aria-label='Close']"
                dialogs = driver.find_elements(By.XPATH, whatsapp_xpath)
                if dialogs:
                    print("    [*] Mendeteksi dialog konfirmasi/WhatsApp, menutup...")
                    ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                    time.sleep(2)
            except: pass
            
            # Marker Upload
            marker_file = post_path + ".uploadedfb" if is_file else os.path.join(post_path, "uploadedfb.txt")
            with open(marker_file, "w") as f:
                if schedule_time:
                    f.write(f"Dijadwalkan: {schedule_time}")
                else:
                    f.write(f"Diposting: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            
            print(f"    [+] {item_name} BERHASIL {'dijadwalkan' if schedule_time else 'diposting'}.")
            update_post_status(post_path, "SELESAI!", 100)
            time.sleep(5)
            # Hapus file status setelah sukses
            status_file = (post_path + ".status") if is_file else os.path.join(post_path, "upload_status.json")
            if os.path.exists(status_file): os.remove(status_file)
            return True

        except Exception as e:
            update_post_status(post_path, f"Gagal: {str(e)}", 0)
            print(f"    [-] Gagal: {e}")
            manual_fallback(driver, "Selesaikan manual di VNC.")
            return False

    except Exception as e:
        update_post_status(post_path, f"Error: {str(e)}", 0)
        print(f"    [!] Error: {e}"); return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="FB Smart Scheduled Uploader")
    parser.add_argument("--profile", help="Nama profil")
    parser.add_argument("--path", help="Path folder utama")
    parser.add_argument("--limit", type=int, default=0, help="Jumlah postingan")
    parser.add_argument("--mode", type=int, choices=[1, 2], help="1: Jadwalkan, 2: Post Now")
    parser.add_argument("--interval", type=int, default=0, help="Jeda antar posting (menit)")
    parser.add_argument("--start", help="Waktu mulai (YYYY-MM-DD HH:MM)")
    parser.add_argument("--headless", action="store_true", help="Gunakan mode headless")
    parser.add_argument("--multi", action="store_true", help="Jalankan untuk SEMUA akun di config.json")
    args = parser.parse_args()

    print("\n=== FB SMART SCHEDULED UPLOADER ===")
    
    # --- LOGIKA MULTI AKUN (NON-INTERAKTIF / AUTO SCAN) ---
    if args.multi:
        interval_mins = args.interval if args.interval is not None else 30
        is_headless = args.headless
        print(f"[*] Memulai mode MULTI-ACCOUNT Auto Scan (Jeda: {interval_mins}m)")
        
        while True:
            # Muat ulang config setiap loop agar bisa update akun baru tanpa restart
            if not os.path.exists("config.json"):
                print("[!] config.json tidak ditemukan."); time.sleep(60); continue
            
            with open("config.json", "r") as f:
                config_data = json.load(f)
            
            found_any = False
            for profile, base_dir in config_data.items():
                if not os.path.isdir(base_dir): continue
                
                next_post = get_next_folder(base_dir)
                if next_post:
                    found_any = True
                    print(f"\n[+] Akun: {profile} -> Folder: {os.path.basename(next_post)}")
                    
                    profile_path = os.path.join(os.getcwd(), "fb_profiles", profile)
                    cleanup_profile(profile_path)
                    driver = setup_driver(profile_path, headless=is_headless)
                    try:
                        run_fb_scheduled_task(driver, profile, next_post, None) # Post Now
                    finally:
                        driver.quit()
                    
                    print(f"[*] Selesai. Menunggu {interval_mins} menit...")
                    time.sleep(interval_mins * 60)
            
            if not found_any:
                sys.stdout.write(f"\r[*] Tidak ada konten di semua akun. Menunggu 5 menit... ")
                sys.stdout.flush()
                time.sleep(300)
        sys.exit()

    profile_dir = os.path.join(os.getcwd(), "fb_profiles")
    profiles = sorted([d for d in os.listdir(profile_dir) if os.path.isdir(os.path.join(profile_dir, d))])
    if not profiles: print("[!] Profil kosong."); sys.exit()

    if args.profile:
        sel_profile = args.profile
    else:
        for i, p in enumerate(profiles): print(f"{i+1}. {p}")
        sel_profile = profiles[int(input("\nPilih Profil: "))-1]

    if args.path:
        parent_folder = args.path
    else:
        parent_folder = input("Masukkan Path Folder Utama: ").strip().replace('"', '').replace("'", "")
    
    if not os.path.isdir(parent_folder): print("[!] Folder tidak valid!"); sys.exit()

    # DETEKSI SMART: Sub-folder vs Direct Files
    # Jika path menunjuk langsung ke folder yang berisi media (bukan folder induk)
    # maka kita anggap itu adalah satu item tunggal.
    if any(f.lower().endswith((".mp4", ".jpg", ".png", ".jpeg", ".webp")) for f in os.listdir(parent_folder)):
        pending_items = [parent_folder]
    else:
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
    
    # Argumen CLI tidak perlu sorting dashboard manual
    if not args.path:
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

    if args.limit is not None and args.profile: # Jika via CLI
        limit = args.limit
    else:
        num_post = input("Jumlah postingan (Enter = Semua): ").strip()
        limit = int(num_post) if num_post.isdigit() else 0
    
    if not args.profile:
        if input("Acak urutan? (y/n): ").lower() == 'y': random.shuffle(pending_items)
    
    if limit > 0: pending_items = pending_items[:limit]

    if args.mode:
        is_post_now = (args.mode == 2)
    else:
        print("\n[?] Ingin menjadwalkan atau posting sekarang?")
        print("1. Jadwalkan (Scheduled)")
        print("2. Posting Sekarang (Post Now)")
        mode_choice = input("Pilih [1/2, default 1]: ").strip()
        is_post_now = (mode_choice == '2')

    if is_post_now:
        current_time_obj = None
        if args.profile:
            interval_mins = args.interval if args.interval is not None else 0
        else:
            interval_mins = int(input("Jeda antar posting (menit) [Enter=0]: ") or 0)
    else:
        if args.start:
            start_str = args.start
        elif args.profile:
            start_str = "" # Default to 30m if profile given but no start
        else:
            start_str = input("Waktu Mulai (YYYY-MM-DD HH:MM) [Enter = 30m lagi]: ").strip()
        
        current_time_obj = datetime.now() + timedelta(minutes=30) if not start_str else datetime.strptime(start_str, "%Y-%m-%d %H:%M")
        
        if args.profile:
            interval_mins = args.interval if args.interval is not None else 60
        else:
            interval_mins = int(input("Jeda antar jadwal (menit): "))

    if args.profile:
        is_headless = args.headless
    else:
        is_headless = input("Gunakan Mode Headless (n VNC)? (y/n): ").lower() == 'y'

    if args.profile and pending_items:
        update_post_status(pending_items[0], "Inisialisasi bot...", 5)

    driver = setup_driver(os.path.join(os.getcwd(), "fb_profiles", sel_profile), headless=is_headless)
    try:
        for item in pending_items:
            update_post_status(item, "Browser siap, memulai...", 8)
            sched_str = current_time_obj.strftime("%Y-%m-%d %H:%M") if current_time_obj else None
            if run_fb_scheduled_task(driver, sel_profile, item, sched_str):
                if current_time_obj:
                    current_time_obj += timedelta(minutes=interval_mins)
                elif interval_mins > 0 and item != pending_items[-1]:
                    print(f"[*] Menunggu {interval_mins} menit sebelum posting berikutnya...")
                    time.sleep(interval_mins * 60)
            else:
                if input("[?] Lanjut? (y/n): ").lower() != 'y': break
    finally: driver.quit()
