import os
import json
import time
import random
import socket
import shutil
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

# Deteksi Environment (Termux Android atau PC Desktop)
IS_TERMUX = "com.termux" in os.environ.get("PREFIX", "")
if IS_TERMUX:
    CHROME_PATH = "/data/data/com.termux/files/usr/bin/chromium-browser"
    CHROMEDRIVER_PATH = "/data/data/com.termux/files/usr/bin/chromedriver"
    os.environ["DISPLAY"] = ":1" # Pastikan terhubung ke VNC X11
else:
    CHROME_PATH = None
    CHROMEDRIVER_PATH = None

def cleanup_profile(profile_path):
    """Menghapus folder cache dan file tidak penting agar ukuran profil tetap kecil."""
    if not os.path.exists(profile_path):
        return

    folders_to_remove = [
        "Default/Cache", "Default/Code Cache", "Default/GPUCache",
        "Default/Service Worker/CacheStorage", "Default/Service Worker/ScriptCache",
        "Default/DawnWebGPUCache", "Default/DawnGraphiteCache", "Default/IndexedDB",
        "Default/Media Cache", "Default/Network/Reporting and NEL",
        "Default/VideoDecodeStats", "Default/Site Characteristics Database",
        "Default/optimization_guide_hint_cache_store",
        "Default/optimization_guide_model_metadata_store",
        "Crashpad", "component_crx_cache", "TranslateKit", "BrowserMetrics"
    ]

    print(f"[*] Membersihkan profil di: {profile_path}...")
    for folder in folders_to_remove:
        full_path = os.path.join(profile_path, folder)
        if os.path.exists(full_path):
            try:
                if os.path.isdir(full_path): shutil.rmtree(full_path)
                else: os.remove(full_path)
            except: pass
    print("[+] Pembersihan selesai.")

def setup_driver(profile_path, headless=False):
    cleanup_profile(profile_path)
    chrome_options = Options()
    if CHROME_PATH:
        chrome_options.binary_location = CHROME_PATH
    
    if headless:
        print("[*] Mode HEADLESS aktif...")
        chrome_options.add_argument("--headless=new")

    chrome_options.add_argument(f"--user-data-dir={profile_path}")
    chrome_options.add_argument("--profile-directory=Default")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    # Optimasi ukuran profil dari fb_login.py agar lebih ringan dan stabil di Termux
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-component-update")
    chrome_options.add_argument("--disable-features=Translate,OptimizationHints")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--no-default-browser-check")
    chrome_options.add_argument("--disk-cache-size=1")
    chrome_options.add_argument("--media-cache-size=1")
    chrome_options.add_argument("--disable-gpu-shader-disk-cache")
    chrome_options.add_argument("--disable-offline-load-stale-cache")
    chrome_options.add_argument("--disable-application-cache")
    chrome_options.add_argument("--disable-gpu") # Mencegah masalah grafis di VNC
    
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")

    if IS_TERMUX and CHROMEDRIVER_PATH:
        service = Service(CHROMEDRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=chrome_options)
    else:
        driver = webdriver.Chrome(options=chrome_options)

    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

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

def run_fb_simulation(profile_name, folder_post):
    profile_path = os.path.join(os.getcwd(), "fb_profiles", profile_name)
    if not os.path.exists(profile_path):
        print(f"[!] Folder profil '{profile_name}' tidak ditemukan di {profile_path}!")
        # Cek folder yang ada
        existing = os.listdir("fb_profiles") if os.path.exists("fb_profiles") else []
        print(f"[*] Profil yang tersedia: {existing}")
        return

    # Cek apakah sudah pernah diupload
    uploaded_marker = os.path.join(folder_post, "uploadedfb.txt")
    if os.path.exists(uploaded_marker):
        print(f"[!] Postingan di folder '{os.path.basename(folder_post)}' sudah pernah diupload. Melewati...")
        return

    # Load metadata (hanya untuk simulasi persiapan)
    meta_file = os.path.join(folder_post, "post_meta.json")
    with open(meta_file, 'r', encoding='utf-8') as f:
        meta = json.load(f)
    print(f"[*] Menyiapkan postingan: {meta['post_title']}")

    driver = setup_driver(profile_path, headless=False)
    wait = WebDriverWait(driver, 30)

    try:
        print("[*] Membuka Facebook...")
        driver.get("https://www.facebook.com/")
        human_delay(5, 8)

        # Cek apakah sudah login (sederhana: cari element pencarian atau profil)
        try:
            wait.until(EC.presence_of_element_located((By.XPATH, "//div[@aria-label='Facebook' or @role='search']")))
            print("[+] Berhasil masuk ke Beranda Facebook.")
        except:
            print("[!] Sepertinya belum login atau halaman lambat dimuat.")

        # Simulasi scroll di beranda
        scroll_page(driver, 3)
        scroll_to_top(driver)

        # --- SIMULASI DRAG AND DROP MEDIA ---
        print("[*] Mencari file media di folder...")
        video_file = None
        for f in os.listdir(folder_post):
            if f.lower().endswith((".mp4", ".jpg", ".png")):
                video_file = os.path.abspath(os.path.join(folder_post, f))
                break
        
        if not video_file:
            print("[!] Tidak ada file media untuk diupload!")
            return

        print(f"[+] File ditemukan: {video_file}")
        
        # Cari elemen target untuk diklik (kotak "What's on your mind?" di beranda)
        print("[*] Mencari area posting di beranda...")
        try:
            # Pastikan hanya mengklik area teks, bukan tombol Foto/video terpisah agar tidak membuka 2 dialog
            post_button_xpath = (
                "//div[@role='button']//span[contains(text(), 'Apa yang Anda pikirkan')]"
                "| //div[@role='button']//span[contains(text(), \"What's on your mind\")]"
            )
            target_el = wait.until(EC.element_to_be_clickable((By.XPATH, post_button_xpath)))
            
            # Scroll ke elemen target
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_el)
            human_delay(2, 3)

            print(f"[*] Mengklik area posting: {target_el.text or 'Area Post'}")
            target_el.click()
            
            # Tunggu popup/dialog muncul
            print("[*] Menunggu dialog postingan muncul...")
            dialog_xpath = "//div[@role='dialog']"
            wait.until(EC.presence_of_element_located((By.XPATH, dialog_xpath)))
            human_delay(2, 3)

            # --- MENAMBAHKAN CAPTION TERLEBIH DAHULU ---
            print("[*] Menyiapkan caption dari metadata...")
            caption_text = f"{meta.get('post_title', '')}\n\n{meta.get('summary', '')}\n\n{meta.get('cta', '')}\n\n"
            hashtags = " ".join(meta.get('hashtags', []))
            caption_text += hashtags
            
            try:
                print("[*] Mencari dan mengklik area 'Apa yang Anda pikirkan' di dalam dialog...")
                # Cari span atau elemen yang menampilkan teks pancingan di dalam dialog
                dialog_trigger_xpath = (
                    "//div[@role='dialog']//span[contains(text(), 'Apa yang Anda pikirkan')]"
                    "| //div[@role='dialog']//span[contains(text(), \"What's on your mind\")]"
                    "| //div[@role='dialog']//div[@aria-label[contains(., 'Apa yang Anda pikirkan')]]"
                    "| //div[@role='dialog']//div[@aria-label[contains(., \"What's on your mind\")]]"
                    "| //div[@role='dialog']//div[@role='textbox'][@contenteditable='true']"
                )
                
                # Tunggu dan klik elemen tersebut
                trigger_el = wait.until(EC.element_to_be_clickable((By.XPATH, dialog_trigger_xpath)))
                trigger_el.click()
                print("[*] Area teks pancingan di dalam dialog berhasil diklik.")
                human_delay(2, 3)
                
                print("[*] Menulis caption ke Facebook (Ketik kata pertama lalu Paste sisanya)...")
                # Pisahkan kata pertama dan sisa teks
                words = caption_text.split(" ", 1)
                first_word = words[0] + " " if len(words) > 1 else words[0]
                rest_of_text = words[1] if len(words) > 1 else ""

                # Gunakan JS untuk menyalin sisa teks ke clipboard browser
                js_copy_to_clipboard = """
                var text = arguments[0];
                var textArea = document.createElement("textarea");
                textArea.value = text;
                document.body.appendChild(textArea);
                textArea.select();
                try {
                    document.execCommand('copy');
                } catch (err) {
                    console.error('Gagal menyalin ke clipboard', err);
                }
                document.body.removeChild(textArea);
                """
                driver.execute_script(js_copy_to_clipboard, rest_of_text)
                
                # Cari kotak teks (contenteditable) yang sesungguhnya di dalam dialog
                real_textbox_xpath = "//div[@role='dialog']//div[@role='textbox'][@contenteditable='true']"
                real_textbox = wait.until(EC.presence_of_element_located((By.XPATH, real_textbox_xpath)))
                
                # Fokuskan dan ketik kata pertama langsung ke kotak teks yang benar
                ActionChains(driver).click(real_textbox).send_keys(first_word).perform()
                human_delay(1, 2)
                
                # Paste sisa teks menggunakan CTRL+V di kotak yang sama
                ActionChains(driver).click(real_textbox).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                
                print("[+] Caption berhasil dimasukkan.")
                human_delay(2, 4)
            except Exception as e:
                print(f"[-] Gagal menulis caption: {e}")

            # --- UPLOAD FILE MEDIA ---
            print("[*] Memasukkan media ke dalam postingan...")
            try:
                # Penjelasan: Kita tidak mengklik ikon "Foto/Video" karena itu akan memunculkan 
                # jendela "Pilih File" bawaan Android/OS yang akan membuat program macet (Selenium tidak bisa mengklik UI OS).
                # Solusinya: Kita langsung "menyuntikkan" file ke elemen input tersembunyi yang ada di dalam kotak tersebut.
                
                file_input_xpath = "//input[@type='file'][@accept='image/*,image/heif,image/heic,video/*,video/mp4,video/x-m4v,video/x-matroska,video/avi'] | //input[@type='file']"
                
                print("    [*] Mencari jalur input media tersembunyi dari kotak Foto/Video...")
                file_inputs = wait.until(EC.presence_of_all_elements_located((By.XPATH, file_input_xpath)))
                
                if file_inputs:
                     print(f"    [+] Ditemukan {len(file_inputs)} jalur input.")
                     # Biasanya input terakhir yang paling relevan dan aktif di dialog terbaru
                     for i, file_input in enumerate(reversed(file_inputs)):
                         try:
                             file_input.send_keys(video_file)
                             print("    [+] File media berhasil disuntikkan ke dalam kotak postingan!")
                             break 
                         except Exception as e:
                             print(f"    [-] Jalur {i+1} gagal: {e}")
                else:
                     print("    [!] Elemen input file tidak ditemukan!")

            except Exception as e:
                print(f"[-] Gagal dalam proses penambahan media: {e}")

            print("[*] Menunggu proses unggah (loading) media ke Facebook...")
            # Tunggu progres bar upload selesai (menghilang) jika ada
            try:
                progressbar_xpath = "//div[@role='progressbar']"
                # Menunggu hingga 60 detik jika ada proses upload video yang memakan waktu
                WebDriverWait(driver, 60).until(EC.invisibility_of_element_located((By.XPATH, progressbar_xpath)))
                print("    [+] Proses unggah (progress bar) selesai.")
            except Exception:
                print("    [-] Tidak mendeteksi indikator loading, mengasumsikan file sudah terproses.")
            
            # Berikan tambahan jeda statis agar thumbnail/preview benar-benar ter-render oleh React
            human_delay(8, 15)

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
                    # Berikan waktu agar React menghapus dialog lama dan merender yang baru
                    human_delay(2, 4)
                    
                    # Cari semua tombol yang cocok
                    buttons = driver.find_elements(By.XPATH, next_btn_xpath)
                    
                    visible_buttons = [btn for btn in buttons if btn.is_displayed()]
                    
                    if visible_buttons:
                        # Biasa ambil yang terakhir/terbaru dari DOM
                        target_btn = visible_buttons[-1]
                        print(f"    [*] Mengklik tombol Berikutnya (Tahap {i+1})...")
                        # Menggunakan JS klik karena lebih stabil di atas overlay
                        driver.execute_script("arguments[0].click();", target_btn)
                    else:
                        if i == 0:
                            print("    [-] Tidak ada tombol Berikutnya yang terlihat (langsung ke tahap Kirim).")
                        else:
                            print(f"    [+] Selesai melewati {i} tahap 'Berikutnya'.")
                        break
                        
                except Exception as e:
                    print(f"    [-] Berhenti di tahap 'Berikutnya' ke-{i+1} karena: {type(e).__name__}")
                    break

            # --- MENGKLIK TOMBOL POST ---
            print("[*] Mencari tombol biru 'Kirim' atau 'Post'...")
            post_submit_xpath = (
                "//div[@role='dialog']//div[@aria-label='Kirim']"
                "| //div[@role='dialog']//div[@aria-label='Post']"
                "| //div[@role='dialog']//div[@role='button']//span[text()='Kirim']"
                "| //div[@role='dialog']//div[@role='button']//span[text()='Post']"
                "| //div[@aria-label='Kirim']"
                "| //div[@aria-label='Post']"
            )
            
            try:
                submit_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, post_submit_xpath)))
                print("[*] Mengklik tombol Kirim (Post)...")
                driver.execute_script("arguments[0].click();", submit_btn)
                
                print("[*] Menunggu proses upload dan posting selesai (bisa memakan waktu)...")
                # Tunggu sampai semua dialog posting hilang (menandakan berhasil terkirim)
                wait.until(EC.invisibility_of_element_located((By.XPATH, "//div[@role='dialog']")))
                print("[+] Postingan berhasil terkirim!")
                
                # Tandai sebagai sudah diupload
                try:
                    with open(os.path.join(folder_post, "uploadedfb.txt"), "w") as f:
                        f.write(f"Diunggah pada: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"[+] Folder '{os.path.basename(folder_post)}' ditandai selesai (uploadedfb.txt).")
                except Exception as ex:
                    print(f"[-] Gagal membuat penanda upload: {ex}")
                    
                human_delay(5, 10) # Jeda tambahan sebelum menutup agar benar-benar aman
            except Exception as e:
                print(f"[-] Gagal mengklik tombol Kirim atau proses upload macet: {e}")

            except Exception as e:
                print(f"[-] Gagal menulis caption: {e}")

        except Exception as e:
            print(f"[!] Gagal proses upload: {e}")

        print("[+] Simulasi selesai.")

    except Exception as e:
        print(f"[!] Terjadi kesalahan: {e}")
    finally:
        driver.quit()
        cleanup_profile(profile_path)

if __name__ == "__main__":
    def get_profiles():
        path = os.path.join(os.getcwd(), "fb_profiles")
        return [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))] if os.path.exists(path) else []

    def get_config():
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r") as f: return json.load(f)
            except: pass
        return {}

    def save_config(config):
        with open("config.json", "w") as f: json.dump(config, f, indent=4)

    while True:
        print("\n==========================================")
        print("           FACEBOOK UPLOADER              ")
        print("==========================================")
        print("1. Upload Konten")
        print("2. Atur Folder Upload Akun")
        print("3. Keluar")
        print("==========================================")
        
        try:
            pilihan_menu = int(input("Pilih menu (1-3): "))
        except ValueError:
            print("[!] Input tidak valid.")
            continue
            
        if pilihan_menu == 3:
            print("Keluar dari program. Terima kasih!")
            sys.exit()
            
        elif pilihan_menu == 2:
            profiles = get_profiles()
            if not profiles:
                print("[!] Tidak ada profil ditemukan di folder fb_profiles.")
                continue
                
            print("\n--- ATUR FOLDER UPLOAD AKUN ---")
            print("Pilih Profil untuk mengatur foldernya:")
            for i, p in enumerate(profiles): print(f"{i+1}. {p}")
            try:
                p_idx = int(input("Nomor Profil: ")) - 1
                selected_profile = profiles[p_idx]
            except:
                print("[!] Input tidak valid."); continue
                
            config = get_config()
            current_dir = config.get(selected_profile, "Belum diatur")
            print(f"\nDirektori saat ini untuk '{selected_profile}': {current_dir}")
            new_dir = input("Masukkan path/direktori baru (misal: Contoh Post/AminMaskur): ").strip()
            
            if os.path.exists(new_dir) and os.path.isdir(new_dir):
                config[selected_profile] = new_dir
                save_config(config)
                print(f"[+] Direktori berhasil disimpan untuk profil '{selected_profile}'.")
            else:
                print("[!] Direktori tidak ditemukan. Pastikan path yang Anda masukkan benar.")
                
        elif pilihan_menu == 1:
            print("\n--- UPLOAD KONTEN ---")
            profiles = get_profiles()
            if not profiles:
                print("[!] Tidak ada profil ditemukan di folder fb_profiles.")
                continue

            print("Pilih Profil:")
            for i, p in enumerate(profiles): print(f"{i+1}. {p}")
            try:
                p_idx = int(input("Nomor Profil: ")) - 1
                selected_profile = profiles[p_idx]
            except:
                print("[!] Input tidak valid."); continue

            config = get_config()
            base_dir = config.get(selected_profile, "")
            
            if not base_dir or not os.path.exists(base_dir):
                print(f"\n[!] Direktori konten untuk profil '{selected_profile}' belum diatur atau tidak ditemukan.")
                print("[*] Silakan kembali ke Menu 2 (Atur Folder Upload Akun) terlebih dahulu.")
                continue

            if os.path.exists(base_dir):
                # Filter folder yang memiliki post_meta.json DAN belum ada uploadedfb.txt
                all_folders = [f for f in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, f)) and os.path.exists(os.path.join(base_dir, f, "post_meta.json"))]
                folders = [f for f in all_folders if not os.path.exists(os.path.join(base_dir, f, "uploadedfb.txt"))]

                if folders:
                    print("\nPilih Mode Upload:")
                    print("1. Upload Manual (Pilih satu folder)")
                    print("2. Auto Upload (Semua folder berurutan dengan interval)")
                    
                    try:
                        mode = int(input("Pilih mode (1/2): "))
                    except ValueError:
                        print("[!] Input tidak valid."); continue
                        
                    if mode == 1:
                        print(f"\n--- DAFTAR FOLDER (BELUM DIUPLOAD) ---")
                        for i, f in enumerate(folders): 
                            print(f"{i+1}. {f}")
                        try:
                            f_idx = int(input("\nNomor Folder: ")) - 1
                            target_post = os.path.join(base_dir, folders[f_idx])
                            if target_post and os.path.exists(target_post):
                                run_fb_simulation(selected_profile, target_post)
                            else:
                                print("[!] Folder postingan tidak ditemukan.")
                        except:
                            print("[!] Input tidak valid."); continue
                    elif mode == 2:
                        print("\nPilih Urutan/Filter Auto Upload:")
                        print("1. Berurutan (Sesuai daftar)")
                        print("2. Acak (Random)")
                        print("3. Hanya Foto")
                        print("4. Hanya Video")
                        print("5. Sesuaikan Urutan (Pilih manual)")
                        
                        try:
                            sub_mode = int(input("Pilihan (1-5): "))
                        except ValueError:
                            print("[!] Input tidak valid."); continue

                        selected_folders = []
                        if sub_mode == 1:
                            selected_folders = folders
                        elif sub_mode == 2:
                            selected_folders = folders.copy()
                            random.shuffle(selected_folders)
                        elif sub_mode == 3:
                            for f in folders:
                                f_path = os.path.join(base_dir, f)
                                if any(file.lower().endswith((".jpg", ".jpeg", ".png")) for file in os.listdir(f_path)):
                                    selected_folders.append(f)
                        elif sub_mode == 4:
                            for f in folders:
                                f_path = os.path.join(base_dir, f)
                                if any(file.lower().endswith((".mp4", ".mkv", ".avi")) for file in os.listdir(f_path)):
                                    selected_folders.append(f)
                        elif sub_mode == 5:
                            print(f"\n--- DAFTAR FOLDER (BELUM DIUPLOAD) ---")
                            for i, f in enumerate(folders): 
                                print(f"{i+1}. {f}")
                            print("\nMasukkan nomor folder yang ingin diupload, pisahkan dengan koma (misal: 3,1,2)")
                            try:
                                custom_input = input("Urutan: ").strip().split(",")
                                for x in custom_input:
                                    idx = int(x.strip()) - 1
                                    if 0 <= idx < len(folders):
                                        selected_folders.append(folders[idx])
                            except:
                                print("[!] Input tidak valid."); continue
                        else:
                            print("[!] Pilihan tidak valid."); continue
                            
                        if not selected_folders:
                            print("\n[!] Tidak ada folder yang sesuai dengan pilihan/filter Anda.")
                            continue
                        
                        try:
                            interval = int(input("\nMasukkan interval antar upload (menit): "))
                        except ValueError:
                            print("[!] Input tidak valid."); continue
                        
                        print(f"\n[*] Memulai Auto Upload untuk {len(selected_folders)} folder dengan interval {interval} menit...")
                        for idx, f in enumerate(selected_folders):
                            target_post = os.path.join(base_dir, f)
                            print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Mengunggah folder {idx+1}/{len(selected_folders)}: {f}")
                            run_fb_simulation(selected_profile, target_post)
                            
                            if idx < len(selected_folders) - 1:
                                print(f"\n[*] Upload selesai. Menunggu {interval} menit untuk folder berikutnya...")
                                # Fitur Countdown
                                for i in range(interval * 60, 0, -1):
                                    mins, secs = divmod(i, 60)
                                    print(f"\r    Sisa waktu tunggu: {mins:02d}:{secs:02d} ", end="", flush=True)
                                    time.sleep(1)
                                print("\n")
                        print("\n[+] Semua proses auto upload selesai!")
                    else:
                        print("[!] Pilihan mode tidak valid.")
                else:
                    if all_folders:
                        print(f"\n[!] Semua folder ({len(all_folders)}) di direktori ini sudah pernah diupload.")
                    else:
                        print(f"[!] Tidak ada folder postingan yang valid di {base_dir}.")
        else:
            print("[!] Pilihan tidak valid.")
