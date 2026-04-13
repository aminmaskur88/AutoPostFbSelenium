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
        
        # XPath yang sangat spesifik untuk menghindari tombol Pemirsa/Privacy
        # Kita mengecualikan teks yang sering muncul di tombol privasi
        excluded_texts = "['Pemirsa', 'Publik', 'Teman', 'Hanya saya', 'Audience', 'Public', 'Friends', 'Only me']"
        post_submit_xpath = (
            f"//div[@role='dialog']//div[@role='button'][not(@aria-haspopup)]"
            f"[not(contains(@aria-label, 'Pemirsa'))][not(contains(@aria-label, 'Audience'))]"
            f"[.//span[contains(text(), 'Kirim') or contains(text(), 'Posting') or contains(text(), 'Post') or contains(text(), 'Selesai')]]"
            f"| //div[@role='dialog']//div[@aria-label='Kirim' or @aria-label='Posting' or @aria-label='Post'][not(@aria-haspopup)]"
        )
        
        try:
            # Ambil semua kandidat
            candidates = driver.find_elements(By.XPATH, post_submit_xpath)
            visible_btns = [b for b in candidates if b.is_displayed()]
            
            if not visible_btns:
                # Fallback jika pencarian super ketat gagal
                fallback_xpath = "//div[@role='dialog']//div[@role='button']//span[text()='Kirim' or text()='Posting' or text()='Selesai']"
                submit_btn = wait.until(EC.element_to_be_clickable((By.XPATH, fallback_xpath)))
            else:
                # Tombol Kirim/Posting biasanya adalah tombol terakhir (paling bawah) di dialog
                submit_btn = visible_btns[-1]

            # Verifikasi teks tombol sebelum klik (Log saja)
            btn_text = submit_btn.text.replace("\n", " ")
            print(f"[*] Mencoba mengklik tombol: {btn_text}")
            
            driver.execute_script("arguments[0].click();", submit_btn)
            
            # --- CEK JIKA TERJEBAK DI DIALOG PEMIRSA ---
            human_delay(3, 4)
            page_source = driver.page_source.lower()
            if "pilih pemirsa" in page_source or "select audience" in page_source or "siapa yang bisa melihat" in page_source:
                print("[!] Ups, sepertinya salah masuk ke menu Pemirsa. Mencari tombol Kembali...")
                back_btn_xpath = "//div[@role='dialog']//div[@aria-label='Kembali' or @aria-label='Back' or @role='button'][descendant::i or contains(., 'Kembali')]"
                try:
                    back_btn = wait.until(EC.element_to_be_clickable((By.XPATH, back_btn_xpath)))
                    driver.execute_script("arguments[0].click();", back_btn)
                    human_delay(2, 3)
                    
                    # RETRY: Cari tombol yang BENAR-BENAR berisi teks Kirim/Posting saja tanpa embel-embel
                    print("[*] Mencoba mencari tombol Kirim yang asli (biasanya berwarna Biru)...")
                    # Tombol Kirim utama seringkali memiliki background-color biru atau role tertentu
                    retry_xpath = "//div[@role='dialog']//div[@role='button']//span[text()='Kirim' or text()='Posting']"
                    retry_btn = wait.until(EC.element_to_be_clickable((By.XPATH, retry_xpath)))
                    driver.execute_script("arguments[0].click();", retry_btn)
                except Exception as ex:
                    print(f"[-] Gagal kembali dari dialog pemirsa: {ex}")

            # Tunggu proses postingan
            print("[*] Menunggu proses upload dan konfirmasi dari Facebook...")
            human_delay(10, 15)
            
            # Cek apakah ada tombol "Tutup" (X) dari dialog baru (Share ke WhatsApp dll)
            print("[*] Mengecek apakah ada dialog tambahan (seperti Share ke WhatsApp)...")
            close_btn_xpath = (
                "//div[@aria-label='Tutup' or @aria-label='Close'][@role='button']"
                "| //div[@role='dialog']//div[@aria-label='Tutup' or @aria-label='Close']"
            )
            try:
                close_btns = driver.find_elements(By.XPATH, close_btn_xpath)
                visible_close_btns = [btn for btn in close_btns if btn.is_displayed()]
                if visible_close_btns:
                    print("[*] Menemukan dialog tambahan, mengklik tombol 'X' (Tutup)...")
                    driver.execute_script("arguments[0].click();", visible_close_btns[0])
                    human_delay(2, 3)
            except Exception:
                pass
            
            # Cek tambahan: Pastikan tidak ada pesan error
            error_keywords = ["Gagal", "Error", "Maaf", "Something went wrong", "Could not"]
            page_text = driver.find_element(By.TAG_NAME, "body").text
            is_error = any(kw in page_text for kw in error_keywords) if "dialog" in page_text.lower() else False
            
            if not is_error:
                print("[+] Konfirmasi: Postingan berhasil terkirim!")
                with open(uploaded_marker, "w") as f:
                    f.write(f"Selesai: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print("[!] Peringatan: Ada indikasi pesan error atau kendala pada halaman.")
        except Exception as e:
            print(f"[-] Gagal konfirmasi postingan: {e}")
        except Exception as e:
            print(f"[-] Gagal kirim postingan: {e}")

    except Exception as e:
        print(f"[!] Error saat eksekusi: {e}")
    finally:
        driver.quit()
        cleanup_profile(profile_path)

# --- FUNGSI PENDUKUNG LOGIKA BARU ---
def get_pending_folders(base_dir):
    folders_data = []
    if not os.path.exists(base_dir):
        return []
        
    for f in os.listdir(base_dir):
        f_path = os.path.join(base_dir, f)
        if os.path.isdir(f_path) and not os.path.exists(os.path.join(f_path, "uploadedfb.txt")):
            # Cek jenis media dalam folder
            media_files = [file for file in os.listdir(f_path) if file.lower().endswith((".mp4", ".jpg", ".png", ".jpeg", ".webp"))]
            if media_files:
                # FIFO: Ambil waktu pembuatan folder
                ctime = os.path.getctime(f_path)
                # Tentukan apakah ini folder video atau foto (cek jika ada file mp4)
                is_video = any(m.lower().endswith((".mp4", ".mov", ".avi")) for m in media_files)
                folders_data.append({
                    'name': f,
                    'is_video': is_video,
                    'ctime': ctime
                })
    
    if not folders_data:
        return []

    # Sort berdasarkan waktu (FIFO)
    folders_data.sort(key=lambda x: x['ctime'])
    
    photos = [f for f in folders_data if not f['is_video']]
    videos = [f for f in folders_data if f['is_video']]
    
    result = []
    lp, lv = len(photos), len(videos)
    
    if lp == 0: return [v['name'] for v in videos]
    if lv == 0: return [p['name'] for p in photos]
    
    # Logika Interleaving (Pembagian Rata)
    if lp >= lv:
        ratio = lp // lv
        remainder = lp % lv
        p_idx, v_idx = 0, 0
        for i in range(lv):
            for _ in range(ratio):
                if p_idx < lp:
                    result.append(photos[p_idx]['name'])
                    p_idx += 1
            if i < remainder:
                if p_idx < lp:
                    result.append(photos[p_idx]['name'])
                    p_idx += 1
            if v_idx < lv:
                result.append(videos[v_idx]['name'])
                v_idx += 1
        # Sisanya jika ada
        while p_idx < lp:
            result.append(photos[p_idx]['name'])
            p_idx += 1
    else:
        ratio = lv // lp
        remainder = lv % lp
        p_idx, v_idx = 0, 0
        for i in range(lp):
            if p_idx < lp:
                result.append(photos[p_idx]['name'])
                p_idx += 1
            for _ in range(ratio):
                if v_idx < lv:
                    result.append(videos[v_idx]['name'])
                    v_idx += 1
            if i < remainder:
                if v_idx < lv:
                    result.append(videos[v_idx]['name'])
                    v_idx += 1
        # Sisanya jika ada
        while v_idx < lv:
            result.append(videos[v_idx]['name'])
            v_idx += 1
            
    return result

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
        print("\n=== FB UPLOADER (FIFO & Balanced Mode) ===")
        print("1. Upload Konten (Manual/Auto Scan)\n2. Atur Folder Akun\n3. Keluar")
        
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
                
                print("\n1. Manual (Sekali Jalan)\n2. Auto All (Continuous Scan)")
                mode = input("Pilih mode: ")
                
                if mode == '1':
                    folders = get_pending_folders(base_dir)
                    if not folders: print("[!] Tidak ada konten baru."); continue
                    for i, f in enumerate(folders): print(f"{i+1}. {f}")
                    run_fb_simulation(p, os.path.join(base_dir, folders[int(input("Nomor: "))-1]), headless=is_headless)
                
                elif mode == '2':
                    interval = int(input("Interval Antar Post (menit): "))
                    print(f"[*] Memulai mode Auto Scan di: {base_dir}")
                    print("[*] Tekan Ctrl+C untuk berhenti.")
                    
                    while True:
                        # Scan ulang setiap kali sebelum proses atau saat menunggu
                        all_pending = []
                        if os.path.exists(base_dir):
                            for f in os.listdir(base_dir):
                                f_path = os.path.join(base_dir, f)
                                if os.path.isdir(f_path) and not os.path.exists(os.path.join(f_path, "uploadedfb.txt")):
                                    media_files = [m for m in os.listdir(f_path) if m.lower().endswith((".mp4", ".jpg", ".png", ".jpeg", ".webp"))]
                                    if media_files:
                                        is_video = any(m.lower().endswith((".mp4", ".mov", ".avi")) for m in media_files)
                                        all_pending.append({'is_video': is_video})

                        n_video = len([f for f in all_pending if f['is_video']])
                        n_photo = len([f for f in all_pending if not f['is_video']])

                        folders = get_pending_folders(base_dir)
                        if not folders:
                            print(f"\r[*] Tidak ada konten baru. [Foto: {n_photo} | Video: {n_video}] Menunggu 1 menit...", end="")
                            time.sleep(60)
                            continue
                        
                        f_name = folders[0]
                        print(f"\n\n[+] Status Antrean: {n_photo} Foto, {n_video} Video (Total: {len(folders)})")
                        print(f"[*] Memproses folder: {f_name}")
                        
                        run_fb_simulation(p, os.path.join(base_dir, f_name), headless=is_headless)
                        
                        wait_seconds = interval * 60
                        print(f"\n[*] Selesai. Menunggu {interval} menit sebelum memproses berikutnya...")
                        try:
                            for remaining in range(wait_seconds, 0, -1):
                                # Update info sisa setiap detik agar akurat jika ada file baru masuk saat menunggu
                                if remaining % 10 == 0: # Scan ulang setiap 10 detik agar tidak berat
                                    temp_pending = []
                                    if os.path.exists(base_dir):
                                        for f in os.listdir(base_dir):
                                            f_path = os.path.join(base_dir, f)
                                            if os.path.isdir(f_path) and not os.path.exists(os.path.join(f_path, "uploadedfb.txt")):
                                                m_files = [m for m in os.listdir(f_path) if m.lower().endswith((".mp4", ".jpg", ".png", ".jpeg", ".webp"))]
                                                if m_files:
                                                    is_v = any(m.lower().endswith((".mp4", ".mov", ".avi")) for m in m_files)
                                                    temp_pending.append({'is_video': is_v})
                                    n_video = len([f for f in temp_pending if f['is_video']])
                                    n_photo = len([f for f in temp_pending if not f['is_video']])

                                mins, secs = divmod(remaining, 60)
                                sys.stdout.write(f"\r    Sisa waktu: {mins:02d}:{secs:02d} | Antrean: {n_photo} Foto, {n_video} Video ")
                                sys.stdout.flush()
                                time.sleep(1)
                        except KeyboardInterrupt:
                            print("\n[!] Berhenti otomatis.")
                            break
            except Exception as e: print(f"[!] Error: {e}")