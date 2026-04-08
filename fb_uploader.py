import os
import json
import time
import random
import sys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from utils import setup_driver, cleanup_profile, get_lan_ip

# Pastikan DISPLAY teratur untuk VNC di Termux
if "com.termux" in os.environ.get("PREFIX", ""):
    os.environ["DISPLAY"] = ":1"

def human_delay(min_sec=2, max_sec=5):
    time.sleep(random.uniform(min_sec, max_sec))

def scroll_page(driver, scrolls=3):
    print(f"[*] Melakukan scroll sebanyak {scrolls} kali...")
    for i in range(scrolls):
        try:
            driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.PAGE_DOWN)
            print(f"    Scroll ke-{i+1}")
            human_delay(2, 4)
        except Exception as e:
            print(f"    [-] Gagal scroll ke-{i+1}: {e}")
            break

def scroll_to_top(driver):
    print("[*] Kembali ke paling atas...")
    try:
        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.HOME)
        human_delay(2, 3)
    except Exception as e:
        print(f"[-] Gagal scroll ke atas: {e}")

def run_fb_simulation(profile_name, folder_post, headless=False):
    profile_path = os.path.join(os.getcwd(), "fb_profiles", profile_name)
    if not os.path.exists(profile_path):
        print(f"[!] Folder profil '{profile_name}' tidak ditemukan!")
        return

    uploaded_marker = os.path.join(folder_post, "uploadedfb.txt")
    if os.path.exists(uploaded_marker):
        print(f"[!] Folder '{os.path.basename(folder_post)}' sudah pernah diupload. Lewati.")
        return

    meta_file = os.path.join(folder_post, "post_meta.json")
    try:
        with open(meta_file, 'r', encoding='utf-8') as f:
            meta = json.load(f)
    except Exception as e:
        print(f"[!] Gagal membaca metadata: {e}")
        return

    print(f"[*] Menyiapkan postingan: {meta.get('post_title', 'Tanpa Judul')}")

    # Bersihkan sebelum buka
    cleanup_profile(profile_path)
    driver = setup_driver(profile_path, headless=headless)
    wait = WebDriverWait(driver, 30)

    try:
        print("[*] Membuka Facebook...")
        if not headless and "com.termux" in os.environ.get("PREFIX", ""):
            lan_ip = get_lan_ip()
            print(f"    [!] (Opsional) Buka VNC Viewer -> {lan_ip}:5901 (PC/HP Lain) atau 127.0.0.1:5901 (Lokal)")
        driver.get("https://www.facebook.com/")
        human_delay(5, 8)

        # Cek login
        try:
            wait.until(EC.presence_of_element_located((By.XPATH, "//div[@aria-label='Facebook' or @role='search']")))
            print("[+] Berhasil masuk ke Beranda.")
        except:
            print("[!] Peringatan: Halaman mungkin belum login atau lambat dimuat.")

        scroll_page(driver, 2)
        scroll_to_top(driver)

        # Cari file media
        video_file = None
        for f in os.listdir(folder_post):
            if f.lower().endswith((".mp4", ".jpg", ".png", ".jpeg")):
                video_file = os.path.abspath(os.path.join(folder_post, f))
                break
        
        if not video_file:
            print("[!] Media tidak ditemukan!")
            return

        # Klik "What's on your mind?"
        post_button_xpath = "//div[@role='button']//span[contains(text(), 'Apa yang Anda pikirkan')] | //div[@role='button']//span[contains(text(), \"What's on your mind\")]"
        try:
            target_el = wait.until(EC.element_to_be_clickable((By.XPATH, post_button_xpath)))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_el)
            human_delay(1, 2)
            target_el.click()
        except Exception as e:
            print(f"[!] Gagal klik area posting: {e}")
            return

        # Tunggu dialog
        wait.until(EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']")))
        human_delay(2, 3)

        # --- INPUT CAPTION (Versi Original) ---
        print("[*] Menyiapkan caption dari metadata...")
        caption_text = f"{meta.get('post_title', '')}\n\n{meta.get('summary', '')}\n\n{meta.get('cta', '')}\n\n" + " ".join(meta.get('hashtags', []))
        
        try:
            print("[*] Mencari dan mengklik area pancingan di dalam dialog...")
            dialog_trigger_xpath = (
                "//div[@role='dialog']//span[contains(text(), 'Apa yang Anda pikirkan')]"
                "| //div[@role='dialog']//span[contains(text(), \"What's on your mind\")]"
                "| //div[@role='dialog']//div[@aria-label[contains(., 'Apa yang Anda pikirkan')]]"
                "| //div[@role='dialog']//div[@aria-label[contains(., \"What's on your mind\")]]"
                "| //div[@role='dialog']//div[@role='textbox'][@contenteditable='true']"
            )
            trigger_el = wait.until(EC.element_to_be_clickable((By.XPATH, dialog_trigger_xpath)))
            trigger_el.click()
            human_delay(1, 2)
            
            # Pisahkan kata pertama untuk memicu fokus
            words = caption_text.split(" ", 1)
            first_word = words[0] + " " if len(words) > 1 else words[0]
            rest_of_text = words[1] if len(words) > 1 else ""

            # Gunakan JS untuk copy sisa teks
            js_copy = "var t = arguments[0]; var a = document.createElement('textarea'); a.value = t; document.body.appendChild(a); a.select(); document.execCommand('copy'); document.body.removeChild(a);"
            driver.execute_script(js_copy, rest_of_text)
            
            real_textbox_xpath = "//div[@role='dialog']//div[@role='textbox'][@contenteditable='true']"
            real_textbox = wait.until(EC.presence_of_element_located((By.XPATH, real_textbox_xpath)))
            
            # Ketik kata pertama lalu Paste sisanya
            ActionChains(driver).click(real_textbox).send_keys(first_word).perform()
            human_delay(1, 2)
            ActionChains(driver).click(real_textbox).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
            
            print("[+] Caption berhasil dimasukkan.")
            human_delay(2, 4)
        except Exception as e:
            print(f"[-] Gagal menulis caption: {e}")

        # --- INPUT MEDIA (Versi Original) ---
        print("[*] Memasukkan media ke dalam postingan...")
        try:
            file_input_xpath = "//input[@type='file' and contains(@accept, 'image')] | //input[@type='file' and contains(@accept, 'video')] | //input[@type='file']"
            file_inputs = wait.until(EC.presence_of_all_elements_located((By.XPATH, file_input_xpath)))
            
            if file_inputs:
                print(f"    [+] Ditemukan {len(file_inputs)} jalur input. Mencoba menyuntikkan...")
                # Mencoba input terakhir (biasanya yang paling aktif di React)
                for i, file_input in enumerate(reversed(file_inputs)):
                    try:
                        file_input.send_keys(video_file)
                        print("    [+] Media berhasil disuntikkan!")
                        break 
                    except Exception:
                        if i == len(file_inputs) - 1: print("    [!] Semua jalur input gagal.")
            else:
                print("    [!] Jalur input media tidak ditemukan!")
        except Exception as e:
            print(f"[-] Gagal dalam proses penambahan media: {e}")

        # Tunggu Upload & Klik Submit
        human_delay(10, 15)
        
        # --- MENGKLIK TOMBOL BERIKUTNYA (JIKA ADA) ---
        print("[*] Mengecek apakah ada tombol 'Berikutnya' / 'Next'...")
        next_btn_xpath = (
            "//div[@role='dialog']//div[@aria-label='Berikutnya']"
            "| //div[@role='dialog']//div[@aria-label='Next']"
            "| //div[@role='dialog']//div[@role='button']//span[text()='Berikutnya']"
            "| //div[@role='dialog']//div[@role='button']//span[text()='Next']"
            "| //div[@aria-label='Berikutnya']"
            "| //div[@aria-label='Next']"
        )
        
        # Loop untuk menangani tombol 'Berikutnya' yang muncul berkali-kali (misal: optimasi video, subtitle, dll)
        for i in range(3): 
            try:
                human_delay(2, 4) # Berikan waktu agar React merender dialog baru
                buttons = driver.find_elements(By.XPATH, next_btn_xpath)
                visible_buttons = [btn for btn in buttons if btn.is_displayed()]
                
                if visible_buttons:
                    print(f"    [*] Mengklik tombol Berikutnya (Tahap {i+1})...")
                    driver.execute_script("arguments[0].click();", visible_buttons[-1])
                else:
                    break
            except Exception:
                break

        # --- MENGKLIK TOMBOL POST ---
        print("[*] Mencari tombol 'Kirim' atau 'Post'...")
        post_submit_xpath = (
            "//div[@role='dialog']//div[@aria-label='Kirim']"
            "| //div[@role='dialog']//div[@aria-label='Post']"
            "| //div[@role='dialog']//div[@role='button']//span[text()='Kirim']"
            "| //div[@role='dialog']//div[@role='button']//span[text()='Post']"
            "| //div[@aria-label='Kirim']"
            "| //div[@aria-label='Post']"
        )
        try:
            submit_btn = wait.until(EC.element_to_be_clickable((By.XPATH, post_submit_xpath)))
            print("[*] Mengklik tombol Kirim (Post)...")
            driver.execute_script("arguments[0].click();", submit_btn)
            wait.until(EC.invisibility_of_element_located((By.XPATH, "//div[@role='dialog']")))
            print("[+] Berhasil diposting!")
            with open(uploaded_marker, "w") as f:
                f.write(f"Selesai: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            print(f"[-] Gagal kirim postingan: {e}")

    except Exception as e:
        print(f"[!] Error saat eksekusi: {e}")
    finally:
        driver.quit()
        cleanup_profile(profile_path)

# --- FUNGSI MENU & CONFIG ---
def get_profiles():
    path = os.path.join(os.getcwd(), "fb_profiles")
    return [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))] if os.path.exists(path) else []

def load_config():
    if os.path.exists("config.json"):
        with open("config.json", "r") as f:
            return json.load(f)
    return {}

def save_config(config):
    with open("config.json", "w") as f:
        json.dump(config, f, indent=4)

if __name__ == "__main__":
    is_headless = input("Gunakan Mode Headless (n VNC)? (y/n): ").lower() == 'y'
    while True:
        print("\n=== FB UPLOADER ===")
        print("1. Upload Konten\n2. Atur Folder Akun\n3. Keluar")
        
        choice = input("Pilih (1-3): ").strip()
        if choice == '3': sys.exit()
        
        elif choice == '2':
            profiles = get_profiles()
            if not profiles: print("[!] Profil kosong."); continue
            for i, p in enumerate(profiles): print(f"{i+1}. {p}")
            try:
                p = profiles[int(input("Pilih Profil: "))-1]
                path = input(f"Path baru untuk {p}: ").strip()
                if os.path.isdir(path):
                    cfg = load_config()
                    cfg[p] = path
                    save_config(cfg)
                    print("[+] Berhasil disimpan.")
                else: print("[!] Path tidak valid.")
            except: print("[!] Error input.")

        elif choice == '1':
            profiles = get_profiles()
            if not profiles: print("[!] Profil kosong."); continue
            for i, p in enumerate(profiles): print(f"{i+1}. {p}")
            try:
                p = profiles[int(input("Pilih Profil: "))-1]
                base_dir = load_config().get(p, "")
                if not base_dir or not os.path.exists(base_dir):
                    print("[!] Atur folder dulu di menu 2."); continue
                
                # Filter folder yang valid
                folders = [f for f in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, f)) 
                          and os.path.exists(os.path.join(base_dir, f, "post_meta.json"))
                          and not os.path.exists(os.path.join(base_dir, f, "uploadedfb.txt"))]
                
                if not folders: print("[!] Tidak ada konten baru."); continue
                
                print(f"\n--- Ditemukan {len(folders)} folder ---")
                print("1. Manual\n2. Auto All")
                mode = input("Pilih mode: ")
                
                if mode == '1':
                    for i, f in enumerate(folders): print(f"{i+1}. {f}")
                    run_fb_simulation(p, os.path.join(base_dir, folders[int(input("Nomor: "))-1]), headless=is_headless)
                elif mode == '2':
                    interval = int(input("Interval (menit): "))
                    for i, f in enumerate(folders):
                        print(f"[{i+1}/{len(folders)}] Processing {f}...")
                        run_fb_simulation(p, os.path.join(base_dir, f), headless=is_headless)
                        if i < len(folders)-1:
                            wait_seconds = interval * 60
                            print(f"\n[*] Upload selesai. Menunggu {interval} menit untuk folder berikutnya...")
                            for remaining in range(wait_seconds, 0, -1):
                                mins, secs = divmod(remaining, 60)
                                sys.stdout.write(f"\r    Sisa waktu tunggu: {mins:02d}:{secs:02d} ")
                                sys.stdout.flush()
                                time.sleep(1)
                            print("\n")
            except Exception as e: print(f"[!] Error: {e}")