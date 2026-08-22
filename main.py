import os
import sys
import subprocess

# Menambahkan direktori root dan core ke sys.path agar import modul aman
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.join(BASE_DIR, "core")

if CORE_DIR not in sys.path:
    sys.path.insert(0, CORE_DIR)

def main():
    os.chdir(BASE_DIR)
    
    # Jalankan menu utama terpadu dari module core
    scheduled_script = os.path.join(CORE_DIR, "fb_uploader_scheduled.py")
    if os.path.exists(scheduled_script):
        subprocess.run([sys.executable, scheduled_script] + sys.argv[1:])
    else:
        print(f"[✗] File utama {scheduled_script} tidak ditemukan!")

if __name__ == "__main__":
    main()
