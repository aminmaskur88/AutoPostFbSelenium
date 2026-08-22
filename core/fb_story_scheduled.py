import os
import json
import time
import random
import sys
import re
import shutil
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils import setup_driver, cleanup_profile

# --- TERMINAL COLOR & STYLING UTILS ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_UNDERLINE = "\033[4m"

CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"
CLR_WHITE = "\033[97m"

TAG_INFO = f"{CLR_CYAN}[i]{CLR_RESET}"
TAG_SUCCESS = f"{CLR_GREEN}[✓]{CLR_RESET}"
TAG_WARNING = f"{CLR_YELLOW}[!]{CLR_RESET}"
TAG_ERROR = f"{CLR_RED}[✗]{CLR_RESET}"
TAG_INPUT = f"{CLR_MAGENTA}➜{CLR_RESET}"

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header(title):
    print(f"\n{CLR_BOLD}{CLR_WHITE}=== {title} ==={CLR_RESET}\n")

def print_menu_box(title, items):
    print(f"\n{CLR_BOLD}{CLR_WHITE}=== {title} ==={CLR_RESET}")
    for item in items:
        print(f"  {CLR_CYAN}{item}{CLR_RESET}")
    print()

def getch():
    try:
        import tty
        import termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                ch2 = sys.stdin.read(1)
                if ch2 == '[':
                    ch3 = sys.stdin.read(1)
                    if ch3 == 'A':
                        return 'up'
                    elif ch3 == 'B':
                        return 'down'
                    else:
                        return 'esc'
                return 'esc'
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch
    except Exception:
        return sys.stdin.read(1)

def select_menu_option(title, options, default_index=0):
    if not sys.stdin.isatty():
        print(f"\n=== {title} ===")
        for i, opt in enumerate(options):
            print(f"  {opt}")
        val = input(f"➜ Pilihan (1-{len(options)}): ").strip()
        try:
            for idx, opt in enumerate(options):
                clean_opt = re.sub(r'\033\[[0-9;]*m', '', opt).strip()
                if clean_opt.startswith(val):
                    return idx
            return int(val) - 1
        except:
            return default_index

    selected = default_index
    while True:
        sys.stdout.write("\033[H\033[J")
        print(f"=== {title} ===")
        print()
        for i, opt in enumerate(options):
            clean_opt = re.sub(r'\033\[[0-9;]*m', '', opt).strip()
            display_text = clean_opt
            if re.match(r'^\d+\.\s*', clean_opt):
                display_text = re.sub(r'^\d+\.\s*', '', clean_opt)
                
            if i == selected:
                print(f"  {CLR_GREEN}❯ {CLR_BOLD}{display_text}{CLR_RESET}")
            else:
                print(f"    {CLR_DIM}{display_text}{CLR_RESET}")
        print()
        print(f"{CLR_DIM}➜ Gunakan [↑/↓] lalu [Enter], atau tekan angka (1-{len(options)}) langsung...{CLR_RESET}")
        sys.stdout.flush()

        ch = getch()
        if ch == 'up':
            selected = (selected - 1) % len(options)
        elif ch == 'down':
            selected = (selected + 1) % len(options)
        elif ch in ['\r', '\n']:
            return selected
        elif ch.isdigit():
            for idx, opt in enumerate(options):
                clean_opt = re.sub(r'\033\[[0-9;]*m', '', opt).strip()
                if clean_opt.startswith(ch):
                    return idx
            try:
                num = int(ch) - 1
                if 0 <= num < len(options):
                    return num
            except:
                pass

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]

def human_delay(min_sec=2, max_sec=4):
    time.sleep(random.uniform(min_sec, max_sec))

def manual_fallback(driver, message="Terjebak di dialog?"):
    print(f"\n{TAG_WARNING} {message}")
    print(f"{TAG_INFO} Mencari tombol yang bisa diklik untuk membantu bot...")
    try:
        dialogs = driver.find_elements(By.XPATH, "//div[@role='dialog']")
        container = dialogs[-1] if dialogs else driver.find_element(By.TAG_NAME, "body")
        selectors = [".//div[@role='button']", ".//button", ".//div[@aria-label]", ".//span[@role='button']", ".//i"]
        candidates = []
        for sel in selectors:
            found = container.find_elements(By.XPATH, sel)
            for el in found:
                try:
                    if el.is_displayed(): candidates.append(el)
                except: pass
        
        unique_btns = []
        seen_ids = set()
        for b in candidates:
            if b.id not in seen_ids:
                unique_btns.append(b); seen_ids.add(b.id)

        if not unique_btns:
            print(f"    {TAG_ERROR} Tidak ada tombol ditemukan.")
            return

        print(f"\n{CLR_BOLD}=== ASISTEN DARURAT ==={CLR_RESET}")
        for i, btn in enumerate(unique_btns):
            lbl = btn.text.strip().replace("\n", " ") or btn.get_attribute("aria-label") or f"[{btn.tag_name.upper()}]"
            print(f"{i+1}. {lbl}")
        print("0. Lewati / Selesai (Lanjut Otomatis)")
        
        choice = input(f"{TAG_INPUT} Pilih nomor tombol untuk diklik (atau 0): ").strip()
        if choice and choice != '0':
            idx = int(choice) - 1
            if 0 <= idx < len(unique_btns):
                target = unique_btns[idx]
                driver.execute_script("arguments[0].style.outline = '5px solid red';", target)
                driver.execute_script("arguments[0].click();", target)
                print(f"{TAG_SUCCESS} Berhasil diklik. Mencoba lanjut otomatis...")
                time.sleep(2)
    except Exception as e:
        print(f"{TAG_ERROR} Gagal dalam mode asisten: {e}")

def get_media_files_for_story(folder_or_file):
    valid_exts = (".mp4", ".mov", ".jpg", ".jpeg", ".png", ".webp")
    media_files = []
    if os.path.isfile(folder_or_file):
        if folder_or_file.lower().endswith(valid_exts):
            media_files.append(folder_or_file)
    elif os.path.isdir(folder_or_file):
        for root, dirs, files in os.walk(folder_or_file):
            for file in sorted(files, key=natural_sort_key):
                if file.lower().endswith(valid_exts):
                    media_files.append(os.path.join(root, file))
    return media_files

def upload_fb_story(driver, media_file):
    print(f"\n{TAG_INFO} Mengunggah Facebook Story: {CLR_BOLD}{os.path.basename(media_file)}{CLR_RESET}")
    wait = WebDriverWait(driver, 35)

    try:
        driver.get("https://www.facebook.com/stories/create")
        human_delay(4, 6)

        file_inputs = driver.find_elements(By.XPATH, "//input[@type='file']")
        if not file_inputs:
            print(f"{TAG_WARNING} Input file tidak langsung ditemukan, mencari kartu pilihan Story...")
            cards = driver.find_elements(By.XPATH, "//div[@role='button']//span[contains(text(), 'Foto') or contains(text(), 'Photo') or contains(text(), 'Teks') or contains(text(), 'Text')]")
            if cards:
                try:
                    cards[0].click()
                    human_delay(2, 3)
                except Exception:
                    pass
            file_inputs = driver.find_elements(By.XPATH, "//input[@type='file']")

        if file_inputs:
            file_inputs[0].send_keys(media_file)
            print(f"    {TAG_SUCCESS} File disuntikkan: {os.path.basename(media_file)}")
            print(f"    {TAG_INFO} Menunggu pratinjau media dan tombol Bagikan muncul...")
            human_delay(8, 12)
        else:
            print(f"{TAG_ERROR} Tidak dapat memilih file untuk story.")
            manual_fallback(driver, "Gagal mengunggah file story secara otomatis.")
            return False

        # Coba klik tombol otomatis berdasarkan konfigurasi yang telah direkam atau selector pintar
        story_elem_file = os.path.join(os.getcwd(), "fb_story_button.json")
        saved_info = {}
        if os.path.exists(story_elem_file):
            try:
                with open(story_elem_file, "r", encoding="utf-8") as sf:
                    saved_info = json.load(sf)
            except Exception:
                pass

        clicked = False
        target_aria = saved_info.get("ariaLabel") or "Bagikan ke Cerita"
        target_text = saved_info.get("text") or "Bagikan ke Cerita"

        # List kemungkinan XPath dari yang paling spesifik ke umum
        xpaths = [
            f"//div[@role='button'][@aria-label='{target_aria}']",
            f"//div[@role='button'][.//span[text()='{target_text}']]",
            "//div[@role='button'][@aria-label[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'bagikan') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'share')]]",
            "//div[@role='button'][.//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'bagikan') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'share')]]",
            "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'bagikan') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'share')]"
        ]

        for xp in xpaths:
            try:
                elements = driver.find_elements(By.XPATH, xp)
                for el in elements:
                    if el.is_displayed():
                        try:
                            driver.execute_script("arguments[0].scrollIntoView(true);", el)
                            el.click()
                            clicked = True
                            break
                        except Exception:
                            try:
                                driver.execute_script("arguments[0].click();", el)
                                clicked = True
                                break
                            except Exception:
                                pass
                if clicked:
                    break
            except Exception:
                pass

        if clicked:
            print(f"    {TAG_SUCCESS} Tombol '{target_aria}' berhasil diklik secara otomatis!")
            human_delay(8, 12)
            return True
        else:
            print(f"    {TAG_WARNING} Gagal mengklik tombol otomatis, meminta bantuan manual...")
            manual_fallback(driver, "Pilih tombol Bagikan ke Cerita dari daftar di bawah:")
            return True

    except Exception as e:
        print(f"{TAG_ERROR} Terjadi kesalahan saat unggah story: {e}")
        manual_fallback(driver, "Terjadi galat saat memproses Story Facebook.")
        return False

def run_story_uploader_mode():
    clear_screen()
    print_header("📖 FB STORY AUTO-UPLOADER")
    
    # 1. Pemilihan Akun / Profil Browser
    profile_dir = os.path.join(os.getcwd(), "fb_profiles")
    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir, exist_ok=True)

    profiles = sorted([d for d in os.listdir(profile_dir) if os.path.isdir(os.path.join(profile_dir, d))])
    if not profiles:
        print(f"{TAG_ERROR} Profil browser kosong! Sila buat profil dahulu.")
        return

    profile_options = [f"{i+1}. {p}" for i, p in enumerate(profiles)] + ["0. ↩️  Batal / Kembali"]
    sel_idx = select_menu_option("PILIH PROFIL FACEBOOK", profile_options)
    if sel_idx == len(profiles):
        return
    sel_profile = profiles[sel_idx]

    # 2. Pemilihan Folder File Media
    parent_folder = input(f"\n{TAG_INPUT} Masukkan Path Folder / File Media: ").strip().replace('"', '').replace("'", "")
    if not os.path.exists(parent_folder):
        print(f"{TAG_ERROR} Path tidak valid atau tidak ditemukan!")
        return

    media_files = get_media_files_for_story(parent_folder)
    if not media_files:
        print(f"{TAG_WARNING} Tidak ditemukan file gambar atau video yang valid (.mp4, .jpg, .png, .jpeg, .webp)")
        return

    print(f"\n{TAG_SUCCESS} Terdeteksi {CLR_BOLD}{CLR_GREEN}{len(media_files)}{CLR_RESET} file media untuk Story:")
    for idx, f in enumerate(media_files[:5], 1):
        print(f"  {idx}. {os.path.basename(f)}")
    if len(media_files) > 5:
        print(f"  ... dan {len(media_files) - 5} media lainnya.")

    # 3. Mode Penjadwalan & Interval Upload Story
    sched_modes = [
        "1. Langsung Upload Berturut-turut (Jeda Menit)",
        "2. Interval Beberapa Jam Sekali (cth: setiap 2 jam)",
        "3. Jam Spesifik Setiap Hari (cth: Jam 08:00, 12:00, 18:00)"
    ]
    sel_sched_idx = select_menu_option("PILIH MODUS STRATEGI INTERVAL", sched_modes)
    
    interval_seconds_list = []
    
    if sel_sched_idx == 0:
        # Mode Jeda Menit
        inp = input(f"\n{TAG_INPUT} Masukkan interval jeda antar story (menit, default 2): ").strip()
        try:
            mins = float(inp) if inp else 2.0
        except ValueError:
            mins = 2.0
        interval_seconds_list = [int(mins * 60)] * (len(media_files) - 1)
        print(f"   {TAG_INFO} Mode Jeda Menit: {mins} menit antar story.")
        
    elif sel_sched_idx == 1:
        # Mode Jeda Jam
        inp = input(f"\n{TAG_INPUT} Berapa jam sekali story diunggah? (cth: 2 atau 1.5, default 1): ").strip()
        try:
            hrs = float(inp) if inp else 1.0
        except ValueError:
            hrs = 1.0
        interval_seconds_list = [int(hrs * 3600)] * (len(media_files) - 1)
        print(f"   {TAG_INFO} Mode Jeda Jam: Unggah setiap {hrs} jam sekali.")
        
    elif sel_sched_idx == 2:
        # Mode Jam Spesifik (misal: 08:00, 12:00, 17:00, 20:00)
        print(f"\n{TAG_INFO} Masukkan jam target tayang dalam sehari.")
        inp_times = input(f"{TAG_INPUT} Masukkan jam (pisahkan dengan koma, cth: 08:00, 12:00, 17:00, 20:00): ").strip()
        time_stubs = [t.strip() for t in inp_times.split(",") if t.strip()]
        if not time_stubs:
            time_stubs = ["08:00", "12:00", "16:00", "20:00"]
            print(f"   {TAG_WARNING} Menggunakan jadwal default: {', '.join(time_stubs)}")
        else:
            print(f"   {TAG_SUCCESS} Target jam per hari: {', '.join(time_stubs)}")

    confirm = input(f"\n{TAG_INPUT} Lanjut unggah ke Story Facebook untuk akun '{sel_profile}'? (y/n, default y): ").strip().lower()
    if confirm == 'n':
        print(f"{TAG_ERROR} Dibatalkan oleh pengguna.")
        return

    # Initializing Driver
    profile_path = os.path.join(profile_dir, sel_profile)
    cleanup_profile(profile_path)
    print(f"\n{TAG_INFO} Membuka browser dengan profil {CLR_BOLD}{sel_profile}{CLR_RESET}...")
    driver = setup_driver(profile_path, headless=False)

    try:
        success_count = 0
        current_time = datetime.now()
        
        # Hitung waktu rilis jika menggunakan target jam spesifik
        scheduled_target_times = []
        if sel_sched_idx == 2:
            parsed_hours = []
            for ts in time_stubs:
                try:
                    parts = ts.split(":")
                    parsed_hours.append((int(parts[0]), int(parts[1])))
                except Exception:
                    pass
            parsed_hours.sort()

            next_date = datetime.now().date()
            while len(scheduled_target_times) < len(media_files):
                for h, m in parsed_hours:
                    dt = datetime.combine(next_date, datetime.min.time()).replace(hour=h, minute=m)
                    if dt > current_time:
                        scheduled_target_times.append(dt)
                        if len(scheduled_target_times) == len(media_files):
                            break
                next_date += timedelta(days=1)

        for i, media_file in enumerate(media_files, 1):
            if sel_sched_idx == 2 and i <= len(scheduled_target_times):
                target_dt = scheduled_target_times[i-1]
                wait_duration = (target_dt - datetime.now()).total_seconds()
                if wait_duration > 0:
                    print(f"\n{TAG_INFO} [JADWAL TARGET] Story #{i} dijadwalkan pada {CLR_BOLD}{target_dt.strftime('%d-%m-%Y %H:%M')}{CLR_RESET}")
                    print(f"   ⏳ Menunggu selama {int(wait_duration // 3600)} jam {int((wait_duration % 3600) // 60)} menit...")
                    time.sleep(wait_duration)

            print(f"\n{CLR_BOLD}--- Processing Story [{i}/{len(media_files)}] ---{CLR_RESET}")
            res = upload_fb_story(driver, media_file)
            if res:
                success_count += 1
                # Tandai file jika berupa file tunggal
                marker_file = media_file + ".uploadedfb"
                try:
                    with open(marker_file, "w") as f:
                        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                except Exception:
                    pass
            
            if i < len(media_files) and sel_sched_idx in [0, 1]:
                wait_sec = interval_seconds_list[i-1]
                # Tambahkan sedikit variasi acak (±15 detik) agar natural
                wait_sec += random.randint(-15, 15)
                if wait_sec < 5: wait_sec = 5
                
                if wait_sec >= 3600:
                    hrs_disp = round(wait_sec / 3600, 1)
                    print(f"{TAG_INFO} Menunggu jeda interval ~{hrs_disp} jam sebelum story berikutnya...")
                else:
                    mins_disp = round(wait_sec / 60, 1)
                    print(f"{TAG_INFO} Menunggu jeda interval ~{mins_disp} menit sebelum story berikutnya...")
                time.sleep(wait_sec)

        print(f"\n{TAG_SUCCESS} Selesai! Berhasil mengunggah {success_count}/{len(media_files)} Story.")
    finally:
        input(f"\n{TAG_INPUT} Tekan Enter untuk menutup browser...")
        driver.quit()

if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    run_story_uploader_mode()
