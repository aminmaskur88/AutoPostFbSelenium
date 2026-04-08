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
    meta = {}
    try:
        if os.path.exists(meta_file):
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
    except Exception as e:
        print(f"[!] Gagal membaca metadata: {e}")

    # Cari file media
    video_file = None
    for f in os.listdir(folder_post):
        if f.lower().endswith((".mp4", ".jpg", ".png", ".jpeg")):
            video_file = os.path.abspath(os.path.join(folder_post, f))
            break
    
    if not video_file:
        print("[!] Media tidak ditemukan!")
        return

    # Fallback Judul dari Nama File jika meta kosong
    if not meta.get('post_title'):
        filename_only = os.path.splitext(os.path.basename(video_file))[0]
        # Ganti underscore atau dash dengan spasi agar lebih rapi
        meta['post_title'] = filename_only.replace("_", " ").replace("-", " ").title()

    print(f"[*] Menyiapkan postingan: {meta.get('post_title')}")

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
        
        # --- MENGKLIK TOMBOL BERIKUTNYA / SELESAI (JIKA ADA) ---
        print("[*] Mengecek apakah ada tombol 'Berikutnya' / 'Selesai'...")
        # Exclude 'Audience' to prevent accidental clicks on privacy settings
        next_btn_xpath = (
            "//div[@role='dialog']//div[@aria-label='Berikutnya'][not(contains(@aria-label, 'Pemirsa'))][not(contains(@aria-label, 'Audience'))]"
            "| //div[@role='dialog']//div[@aria-label='Next'][not(contains(@aria-label, 'Audience'))]"
            "| //div[@role='dialog']//div[@aria-label='Selesai'][not(contains(@aria-label, 'Pemirsa'))][not(contains(@aria-label, 'Audience'))]"
            "| //div[@role='dialog']//div[@aria-label='Done']"
            "| //div[@role='dialog']//div[@role='button']//span[text()='Berikutnya']"
            "| //div[@role='dialog']//div[@role='button']//span[text()='Next']"
            "| //div[@role='dialog']//div[@role='button']//span[text()='Selesai']"
            "| //div[@role='dialog']//div[@role='button']//span[text()='Done']"
            "| //div[@aria-label='Berikutnya']"
            "| //div[@aria-label='Next']"
            "| //div[@aria-label='Selesai']"
        )
        
        # Loop untuk menangani tombol 'Berikutnya' yang muncul berkali-kali (misal: optimasi video, subtitle, dll)
        for i in range(4): 
            try:
                human_delay(3, 5) # Berikan waktu agar React merender dialog baru
                buttons = driver.find_elements(By.XPATH, next_btn_xpath)
                # Ambil yang terlihat dan biasanya tombol utama ada di bagian bawah/akhir list
                visible_buttons = [btn for btn in buttons if btn.is_displayed()]
                
                if visible_buttons:
                    print(f"    [*] Mengklik tombol Berikutnya/Selesai (Tahap {i+1})...")
                    driver.execute_script("arguments[0].click();", visible_buttons[-1])
                else:
                    break
            except Exception:
                break

        # --- MENGKLIK TOMBOL POST / KIRIM (FINAL) ---
        human_delay(3, 5) # Tunggu sebentar sebelum klik final Kirim
        print("[*] Mencari tombol final 'Kirim' atau 'Posting'...")
        # Prioritaskan 'Kirim' atau 'Posting'. Exclude elements that definitely look like privacy selectors.
        # Biasanya tombol Kirim asli tidak punya aria-haspopup='true'
        post_submit_xpath = (
            "//div[@role='dialog']//div[@aria-label='Kirim'][not(@aria-haspopup)][not(contains(@aria-label, 'Pemirsa'))]"
            "| //div[@role='dialog']//div[@aria-label='Posting'][not(@aria-haspopup)][not(contains(@aria-label, 'Pemirsa'))]"
            "| //div[@role='dialog']//div[@aria-label='Post'][not(@aria-haspopup)][not(contains(@aria-label, 'Audience'))]"
            "| //div[@role='dialog']//div[@role='button']//span[text()='Kirim'][not(ancestor::div[@aria-haspopup])]"
            "| //div[@role='dialog']//div[@role='button']//span[text()='Posting'][not(ancestor::div[@aria-haspopup])]"
            "| //div[@role='dialog']//div[@role='button']//span[text()='Post'][not(ancestor::div[@aria-haspopup])]"
            "| //div[@role='dialog']//div[@aria-label[contains(., 'Kirim')]][not(@aria-haspopup)][not(contains(@aria-label, 'Pemirsa'))]"
            "| //div[@role='dialog']//div[@aria-label[contains(., 'Posting')]][not(@aria-haspopup)][not(contains(@aria-label, 'Pemirsa'))]"
            "| //div[@role='dialog']//div[@aria-label[contains(., 'Post')]][not(@aria-haspopup)][not(contains(@aria-label, 'Audience'))]"
            "| //div[@role='dialog']//div[@aria-label='Selesai'][not(@aria-haspopup)][not(contains(@aria-label, 'Pemirsa'))]"
            "| //div[@aria-label='Kirim'][not(@aria-haspopup)]"
            "| //div[@aria-label='Posting'][not(@aria-haspopup)]"
        )
        try:
            # Cari semua yang cocok dan pilih yang paling bawah (biasanya tombol utama)
            submit_btns = driver.find_elements(By.XPATH, post_submit_xpath)
            visible_btns = [b for b in submit_btns if b.is_displayed()]
            
            if not visible_btns:
                # Fallback ke xpath lama jika tidak ketemu yang tanpa aria-haspopup
                submit_btn = wait.until(EC.element_to_be_clickable((By.XPATH, post_submit_xpath.replace("[not(@aria-haspopup)]", ""))))
            else:
                submit_btn = visible_btns[-1]

            print("[*] Mengklik tombol Kirim...")
            driver.execute_script("arguments[0].click();", submit_btn)
            
            # --- CEK JIKA MALAH MASUK KE DIALOG PEMIRSA/AUDIENCE ---
            human_delay(3, 5)
            # XPath untuk tombol Kembali di dialog pemirsa
            back_btn_xpath = (
                "//div[@role='dialog']//div[@aria-label='Kembali']"
                "| //div[@role='dialog']//div[@aria-label='Back']"
                "| //div[@role='dialog']//div[@role='button']//i[contains(@class, 'back')]"
            )
            back_btns = [b for b in driver.find_elements(By.XPATH, back_btn_xpath) if b.is_displayed()]
            if back_btns:
                print("[!] Terdeteksi masuk ke dialog pemirsa, mengklik 'Kembali'...")
                driver.execute_script("arguments[0].click();", back_btns[0])
                human_delay(2, 3)
                
                # Coba cari tombol Kirim yang lebih spesifik agar tidak salah klik lagi
                print("[*] Mencari ulang tombol Kirim yang benar...")
                # Tombol kirim asli biasanya biru dan punya role button di level tertentu
                final_retry_xpath = "//div[@role='dialog']//div[@role='button']//span[text()='Kirim' or text()='Posting']"
                try:
                    retry_btn = wait.until(EC.element_to_be_clickable((By.XPATH, final_retry_xpath)))
                    driver.execute_script("arguments[0].click();", retry_btn)
                except:
                    # Jika tidak ketemu span, coba klik lagi yang tadi tapi hindari yang sama
                    driver.execute_script("arguments[0].click();", submit_btn) 

            # Tunggu dialog hilang (konfirmasi utama)
            print("[*] Menunggu konfirmasi dari Facebook...")
            wait.until(EC.invisibility_of_element_located((By.XPATH, "//div[@role='dialog']")))
            
            # Cek tambahan: Pastikan tidak ada pesan error yang tertinggal
            human_delay(3, 5)
            error_keywords = ["Gagal", "Error", "Maaf", "Something went wrong", "Could not"]
            page_text = driver.find_element(By.TAG_NAME, "body").text
            
            is_error = any(kw in page_text for kw in error_keywords) if "dialog" in page_text.lower() else False
            
            if not is_error:
                print("[+] Konfirmasi: Postingan berhasil terkirim!")
                with open(uploaded_marker, "w") as f:
                    f.write(f"Selesai: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print("[!] Peringatan: Dialog hilang tapi sepertinya ada pesan error atau kendala.")
        except Exception as e:
            print(f"[-] Gagal konfirmasi postingan: {e}")
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
                
                # Filter folder yang valid (punya media DAN belum diupload)
                folders = []
                for f in os.listdir(base_dir):
                    f_path = os.path.join(base_dir, f)
                    if os.path.isdir(f_path) and not os.path.exists(os.path.join(f_path, "uploadedfb.txt")):
                        # Cek apakah ada file media di dalamnya
                        has_media = any(file.lower().endswith((".mp4", ".jpg", ".png", ".jpeg")) for file in os.listdir(f_path))
                        if has_media:
                            folders.append(f)
                
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