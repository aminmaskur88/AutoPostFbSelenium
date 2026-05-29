import os
import json
import time
import random
import sys
import re
import threading
import http.server
import socketserver
import base64
import webbrowser
import atexit
from functools import partial
from datetime import datetime, timedelta
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from utils import setup_driver, cleanup_profile
from fb_uploader import manual_fallback

# --- UTILS UNTUK STICKY FOOTER ---

def reset_scroll_region():
    """Mengembalikan terminal ke mode normal."""
    sys.stdout.write("\033[r") # Reset scroll region
    sys.stdout.write("\033[?25h") # Show cursor
    # Pindah ke baris baru agar tidak menimpa footer terakhir
    sys.stdout.write("\n")
    sys.stdout.flush()

def setup_sticky_footer():
    """Menyiapkan terminal untuk sticky footer di baris terakhir."""
    try:
        rows, _ = os.get_terminal_size()
        # Set scroll region: Baris 1 sampai (rows-1)
        sys.stdout.write(f"\033[1;{rows-1}r")
        sys.stdout.flush()
        atexit.register(reset_scroll_region)
    except: pass

def print_progress_bar(current, total):
    """Menampilkan progress bar di baris paling bawah (Sticky Footer)."""
    try:
        rows, cols = os.get_terminal_size()
    except:
        rows, cols = 24, 80
        
    percent = (current / total) * 100
    # Sesuaikan panjang bar dengan lebar terminal
    bar_len = min(cols - 30, 40)
    if bar_len < 10: bar_len = 10
    
    filled_len = int(bar_len * current // total)
    bar = '█' * filled_len + '░' * (bar_len - filled_len)
    
    # Progress text (Hijau)
    bar_text = f"\033[92m SESI: [{bar}] {current}/{total} ({percent:.1f}%)\033[0m"
    
    # Simpan posisi kursor, pindah ke baris terakhir, hapus baris, cetak bar, kembalikan kursor
    sys.stdout.write("\033[s") # Save cursor
    sys.stdout.write(f"\033[{rows};1H") # Move to last line
    sys.stdout.write("\033[K") # Clear line
    sys.stdout.write(bar_text)
    sys.stdout.write("\033[u") # Restore cursor
    sys.stdout.flush()

# --- FUNGSI PREVIEW INTERAKTIF (Ala auto_poster_album.py) ---

class AlbumPreviewState:
    def __init__(self, pending_items, item_data_map):
        self.pending_items = pending_items # List of paths
        self.item_data_map = item_data_map # Path -> {caption, media_files, schedule_time}
        self.lock = threading.Lock()
        self.server_should_shutdown = False

class AlbumPreviewRequestHandler(http.server.BaseHTTPRequestHandler):
    def __init__(self, state, *args, **kwargs):
        self.state = state
        http.server.BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

    def log_message(self, format, *args):
        return # Silent logs

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            html = self.generate_html()
            self.wfile.write(html.encode('utf-8'))
        elif self.path.startswith('/media/'):
            # Path format: /media/<index>/<filename>
            parts = self.path.split('/')
            if len(parts) >= 4:
                try:
                    item_idx = int(parts[2])
                    filename = parts[3]
                    item_path = self.state.pending_items[item_idx]
                    media_path = os.path.join(item_path, filename) if os.path.isdir(item_path) else item_path
                    
                    if os.path.exists(media_path):
                        self.send_response(200)
                        ext = os.path.splitext(filename)[1].lower()
                        mime = "image/jpeg"
                        if ext in ['.mp4', '.mov', '.avi']: mime = "video/mp4"
                        elif ext == '.png': mime = "image/png"
                        elif ext == '.webp': mime = "image/webp"
                        
                        self.send_header("Content-type", mime)
                        self.end_headers()
                        with open(media_path, 'rb') as f:
                            self.wfile.write(f.read())
                        return
                except: pass
            self.send_error(404)
        else:
            self.send_error(404)

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)

        if self.path == '/shutdown':
            self.send_response(200)
            self.end_headers()
            self.state.server_should_shutdown = True
        elif self.path == '/edit_caption':
            with self.state.lock:
                idx = data['index']
                item_path = self.state.pending_items[idx]
                self.state.item_data_map[item_path]['caption'] = data['caption']
            self.send_response(200)
            self.end_headers()
        elif self.path == '/delete_item':
            with self.state.lock:
                idx = data['index']
                item_path = self.state.pending_items.pop(idx)
                if item_path in self.state.item_data_map:
                    del self.state.item_data_map[item_path]
            self.send_response(200)
            self.end_headers()
        elif self.path == '/reorder':
            with self.state.lock:
                new_order = data['order'] # List of indices
                new_items = [self.state.pending_items[int(i)] for i in new_order]
                self.state.pending_items[:] = new_items
            self.send_response(200)
            self.end_headers()
        elif self.path == '/delete_photo':
            with self.state.lock:
                idx = data['index']
                filename = data['filename']
                item_path = self.state.pending_items[idx]
                media_files = self.state.item_data_map[item_path]['media_files']
                self.state.item_data_map[item_path]['media_files'] = [m for m in media_files if os.path.basename(m) != filename]
            self.send_response(200)
            self.end_headers()
        elif self.path == '/add_photo':
            with self.state.lock:
                idx = data['index']
                filename = data['filename']
                photo_data = data['data']
                item_path = self.state.pending_items[idx]
                
                # Tentukan target directory
                target_dir = item_path if os.path.isdir(item_path) else os.path.dirname(item_path)
                new_path = os.path.join(target_dir, filename)
                
                try:
                    header, encoded = photo_data.split(",", 1)
                    file_data = base64.b64decode(encoded)
                    with open(new_path, "wb") as f:
                        f.write(file_data)
                    self.state.item_data_map[item_path]['media_files'].append(new_path)
                except Exception as e:
                    print(f"[!] Error saving photo: {e}")
                    self.send_response(500)
                    self.end_headers()
                    return
            self.send_response(200)
            self.end_headers()

    def generate_html(self):
        items_html = ""
        for i, path in enumerate(self.state.pending_items):
            data = self.state.item_data_map[path]
            name = os.path.basename(path)
            
            # Media Grid
            images_html = ""
            for m_idx, media_path in enumerate(data['media_files']):
                m_filename = os.path.basename(media_path)
                ext = os.path.splitext(m_filename)[1].lower()
                is_video = ext in ['.mp4', '.mov', '.avi']
                media_url = f"/media/{i}/{m_filename}"
                
                if is_video:
                    media_tag = f'<div class="video-thumb"><img src="{media_url}"><div class="play-icon">▶</div></div>'
                else:
                    media_tag = f'<img src="{media_url}">'
                
                images_html += f"""
                <div class="photo-card" id="photo-{i}-{m_filename}">
                    {media_tag}
                    <button class="delete-photo-btn" onclick="deletePhoto({i}, '{m_filename}')">×</button>
                </div>"""

            items_html += f"""
            <div class="item-card" data-index="{i}">
                <div class="album-header">
                    <div class="handle">☰</div>
                    <div class="album-info">
                        <div class="album-title">{name}</div>
                        <div class="album-meta">🕒 {data['schedule_time'] or '🚀 Posting SEKARANG'} | 🖼️ {len(data['media_files'])} Media</div>
                    </div>
                    <button class="btn-delete" onclick="deleteItem({i})">×</button>
                </div>
                <div class="caption-container">
                    <textarea onchange="editCaption({i}, this.value)">{data['caption']}</textarea>
                </div>
                <div class="photos-container" id="photos-container-{i}">
                    {images_html}
                    <div class="add-photo-card" onclick="document.getElementById('add-photo-input-{i}').click()">
                        <input type="file" id="add-photo-input-{i}" multiple accept="image/*,video/*" style="display: none;" onchange="handlePhotoAdd({i})">
                        <span>+</span>
                        <p>Tambah</p>
                    </div>
                </div>
            </div>
            """

        return f"""
        <!DOCTYPE html>
        <html lang="id">
        <head>
            <title>FB Post Preview & Editor</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js"></script>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; background: #f0f2f5; color: #1c1e21; }}
                .header {{ background: #1877f2; color: white; padding: 15px; text-align: center; position: sticky; top: 0; z-index: 1000; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .container {{ max-width: 800px; margin: 20px auto; padding: 0 15px; padding-bottom: 100px; }}
                
                .item-card {{ background: white; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.2); overflow: hidden; border: 1px solid #ddd; }}
                .album-header {{ padding: 12px; border-bottom: 1px solid #ebedf0; display: flex; align-items: center; gap: 12px; background: #fafafa; }}
                .handle {{ cursor: grab; font-size: 20px; color: #8d949e; }}
                .album-info {{ flex: 1; }}
                .album-title {{ font-weight: bold; font-size: 15px; color: #1c1e21; }}
                .album-meta {{ font-size: 12px; color: #606770; margin-top: 2px; }}
                
                .caption-container {{ padding: 12px; }}
                textarea {{ width: 100%; box-sizing: border-box; border: 1px solid #ddd; border-radius: 6px; padding: 10px; font-family: inherit; font-size: 14px; min-height: 100px; resize: vertical; background: #f5f6f7; transition: border-color 0.2s; }}
                textarea:focus {{ outline: none; border-color: #1877f2; background: white; }}
                
                .photos-container {{ display: flex; flex-wrap: wrap; gap: 8px; padding: 12px; background: #f0f2f5; border-top: 1px solid #ebedf0; }}
                .photo-card {{ width: calc(25% - 6px); aspect-ratio: 1/1; position: relative; border-radius: 4px; overflow: hidden; background: #000; }}
                .photo-card img {{ width: 100%; height: 100%; object-fit: cover; }}
                
                .delete-photo-btn {{ position: absolute; top: 2px; right: 2px; background: rgba(0,0,0,0.6); color: white; border: none; border-radius: 50%; width: 20px; height: 20px; cursor: pointer; font-size: 14px; display: flex; align-items: center; justify-content: center; }}
                .delete-photo-btn:hover {{ background: #f02849; }}

                .add-photo-card {{ width: calc(25% - 6px); aspect-ratio: 1/1; border: 2px dashed #ccd0d5; border-radius: 4px; display: flex; flex-direction: column; align-items: center; justify-content: center; cursor: pointer; color: #606770; background: #f5f6f7; }}
                .add-photo-card:hover {{ background: #ebedf0; border-color: #1877f2; color: #1877f2; }}
                .add-photo-card span {{ font-size: 24px; font-weight: bold; }}
                .add-photo-card p {{ margin: 0; font-size: 11px; font-weight: bold; }}

                .video-thumb {{ position: relative; width: 100%; height: 100%; }}
                .play-icon {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: white; background: rgba(0,0,0,0.5); border-radius: 50%; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; font-size: 14px; border: 2px solid white; }}
                
                .btn-delete {{ background: #f02849; color: white; border: none; width: 28px; height: 28px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: bold; }}
                .btn-delete:hover {{ background: #d22846; }}
                
                .footer-actions {{ position: fixed; bottom: 0; left: 0; right: 0; background: white; padding: 15px; box-shadow: 0 -2px 10px rgba(0,0,0,0.1); display: flex; justify-content: center; z-index: 1000; }}
                .btn-start {{ background: #42b72a; color: white; border: none; padding: 12px 40px; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; transition: background 0.2s; }}
                .btn-start:hover {{ background: #36a420; }}
                
                @media (max-width: 600px) {{
                    .photo-card, .add-photo-card {{ width: calc(33.33% - 6px); }}
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1 style="margin:0; font-size: 18px;">🚀 FB Post Preview & Editor</h1>
            </div>
            
            <div class="container" id="items-container">
                {items_html}
            </div>
            
            <div class="footer-actions">
                <button class="btn-start" onclick="startUpload()">MULAI UPLOAD SEKARANG</button>
            </div>

            <script>
                const container = document.getElementById('items-container');
                new Sortable(container, {{
                    handle: '.handle',
                    animation: 150,
                    onEnd: function() {{
                        const order = Array.from(container.querySelectorAll('.item-card')).map(el => el.dataset.index);
                        fetch('/reorder', {{ method: 'POST', body: JSON.stringify({{ order }}) }});
                    }}
                }});

                function editCaption(index, caption) {{
                    fetch('/edit_caption', {{ method: 'POST', body: JSON.stringify({{ index, caption }}) }});
                }}

                function deleteItem(index) {{
                    if(confirm('Hapus postingan ini dari antrean?')) {{
                        fetch('/delete_item', {{ method: 'POST', body: JSON.stringify({{ index }}) }}).then(() => location.reload());
                    }}
                }}

                function deletePhoto(index, filename) {{
                    if(confirm('Hapus media ini?')) {{
                        fetch('/delete_photo', {{ method: 'POST', body: JSON.stringify({{ index, filename }}) }})
                        .then(r => {{
                            if(r.ok) document.getElementById(`photo-${{index}}-${{filename}}`).remove();
                        }});
                    }}
                }}

                function handlePhotoAdd(index) {{
                    const input = document.getElementById(`add-photo-input-${{index}}`);
                    const files = input.files;
                    if (files.length === 0) return;

                    for (const file of files) {{
                        const reader = new FileReader();
                        reader.onload = function(e) {{
                            fetch('/add_photo', {{
                                method: 'POST',
                                body: JSON.stringify({{
                                    index: index,
                                    filename: file.name,
                                    data: e.target.result
                                }})
                            }}).then(r => {{
                                if(r.ok) location.reload();
                                else alert('Gagal menambah foto: ' + file.name);
                            }});
                        }};
                        reader.readAsDataURL(file);
                    }}
                }}

                function startUpload() {{
                    if(confirm('Mulai proses upload Selenium?')) {{
                        fetch('/shutdown', {{ method: 'POST', body: JSON.stringify({{}}) }}).then(() => {{
                            document.body.innerHTML = `
                                <div style="text-align:center; margin-top:100px; font-family:sans-serif;">
                                    <h2 style="color:#1877f2;">✅ Server Ditutup</h2>
                                    <p>Silakan kembali ke Terminal untuk melihat proses Selenium.</p>
                                </div>`;
                        }});
                    }}
                }}
            </script>
        </body>
        </html>
        """

def run_interactive_preview_web(pending_items, item_data_map):
    state = AlbumPreviewState(list(pending_items), dict(item_data_map))
    PORT = 8080
    Handler = partial(AlbumPreviewRequestHandler, state)
    socketserver.TCPServer.allow_reuse_address = True
    
    # Cari port kosong jika 8080 dipakai
    while True:
        try:
            httpd = socketserver.TCPServer(('', PORT), Handler)
            break
        except: PORT += 1

    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    url = f"http://127.0.0.1:{PORT}"
    print(f"\n✅ Server Pratinjau Interaktif berjalan di: {url}")
    print("   Silakan edit caption, hapus, atau atur urutan di browser.")
    
    try:
        webbrowser.open(url)
    except: pass

    try:
        while not state.server_should_shutdown:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[!] Dihentikan oleh pengguna.")

    httpd.shutdown()
    httpd.server_close()
    server_thread.join()
    print("✅ Pratinjau selesai. Melanjutkan ke proses upload...\n")
    
    return state.pending_items, state.item_data_map

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_datetime_input(prompt: str):
    while True:
        val = input(f"⏰ {prompt} (format: YYYY-MM-DD HH:MM atau ketik 'now'): ").strip().lower()
        if val in ['now', 'sekarang', 'y']:
            return 'now'
        try:
            return datetime.strptime(val, "%Y-%m-%d %H:%M")
        except ValueError:
            print("❌ Format salah. Mohon ulangi.")

def load_drafts():
    path = os.path.join(os.getcwd(), "draft_posts.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {}

def save_drafts(drafts):
    path = os.path.join(os.getcwd(), "draft_posts.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(drafts, f, indent=4)

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
                file_path = os.path.abspath(os.path.join(path, f))
                media.append(file_path)
    
    # Logika Cerdas: 
    # 1. Kelompokkan file yang dimodifikasi dalam rentang waktu yang sama (misal per 60 detik).
    # 2. Di dalam kelompok waktu tersebut, urutkan berdasarkan Nama (A-Z).
    # 3. File yang disisipkan jauh lebih baru akan otomatis berada di kelompok waktu terakhir (paling bawah).
    media.sort(key=lambda x: (int(os.path.getmtime(x) / 60), os.path.basename(x).lower()))
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

def get_caption_text(post_path):
    """Membangun caption utama dari post_meta.json (Logic ala reference script)."""
    item_name = os.path.basename(post_path)
    is_file = os.path.isfile(post_path)
    
    # Metadata Path
    meta = {}
    if not is_file:
        meta_file = os.path.join(post_path, "post_meta.json")
        if os.path.exists(meta_file):
            try:
                with open(meta_file, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
            except: pass
    
    # Fallback ke Nama Folder/File jika meta kosong
    clean_name = os.path.splitext(item_name)[0] if is_file else item_name
    default_title = clean_name.replace("_", " ").replace("-", " ").title()
    
    parts = []
    # 1. Judul
    title = meta.get('post_title') or default_title
    if title: parts.append(title)
    
    # 2. Ringkasan / Konten Utama
    summary = meta.get('summary', '').strip()
    if summary: parts.append(f"\n\n{summary}")
    
    # 3. Call to Action
    cta = meta.get('cta', '').strip()
    if cta: parts.append(f"\n\n{cta}")
    
    # 4. Hashtags
    hashtags = meta.get('hashtags', [])
    if hashtags:
        tags_list = [f"#{tag.lstrip('#').strip()}" for tag in hashtags if tag.strip()]
        parts.append(f"\n\n{' '.join(tags_list)}")
    
    return "".join(parts).strip()

def run_album_post_mode(args=None):
    clear_screen()
    print("📚 Mode Postingan Album\n")
    
    profile_dir = os.path.join(os.getcwd(), "fb_profiles")
    profiles = sorted([d for d in os.listdir(profile_dir) if os.path.isdir(os.path.join(profile_dir, d))])
    if not profiles: print("[!] Profil kosong."); return

    for i, p in enumerate(profiles): print(f"{i+1}. {p}")
    sel_profile = profiles[int(input("\nPilih Profil: "))-1]

    parent_folder = input("Masukkan Path Folder Utama: ").strip().replace('"', '').replace("'", "")
    if not os.path.isdir(parent_folder): print("[!] Folder tidak valid!"); return

    # DETEKSI PENDING (Smarter Detection: Files and Folders as separate posts)
    all_items = sorted([os.path.join(parent_folder, f) for f in os.listdir(parent_folder)])
    pending_items = []
    
    for item in all_items:
        item_name = os.path.basename(item)
        if item_name == "queue_order.json": continue
        
        is_dir = os.path.isdir(item)
        is_media = any(item.lower().endswith(ext) for ext in (".mp4", ".jpg", ".png", ".jpeg", ".webp"))
        
        if is_dir:
            # Jika folder, cek marker di dalamnya
            if not os.path.exists(os.path.join(item, "uploadedfb.txt")):
                # Pastikan ada media di dalam folder tersebut
                if any(f.lower().endswith((".mp4", ".jpg", ".png", ".jpeg", ".webp")) for f in os.listdir(item)):
                    pending_items.append(item)
        elif is_media:
            # Jika file media tunggal, cek marker file-nya
            if not os.path.exists(item + ".uploadedfb"):
                pending_items.append(item)

    if not pending_items: print("[!] Tidak ada konten baru."); return
    
    # ADVANCED SELECTION (Logic ala reference script)
    print(f"\n✅ {len(pending_items)} album siap untuk diproses.")
    print("--- Pilih Mode Unggahan ---")
    print("1. Unggah Semua Album (sesuai urutan)")
    print("2. Unggah Sejumlah Album Secara Acak")
    print("3. Pilih Album Tertentu untuk Diunggah")
    print("4. Unggah Satu Album Acak")
    sel_mode = input("Pilih mode (1/2/3/4, default 1): ").strip()

    if sel_mode == '2':
        num_random = int(input(f"Berapa album acak (maks: {len(pending_items)})? ").strip())
        pending_items = random.sample(pending_items, min(num_random, len(pending_items)))
    elif sel_mode == '3':
        for idx, p in enumerate(pending_items): print(f"{idx+1}. {os.path.basename(p)}")
        choices = input("Masukkan nomor (pisahkan dengan koma, cth: 1,3,5): ").strip()
        indices = [int(i.strip()) - 1 for i in choices.split(',') if i.strip().isdigit()]
        pending_items = [pending_items[i] for i in indices if 0 <= i < len(pending_items)]
    elif sel_mode == '4':
        pending_items = random.sample(pending_items, 1)
    
    # SORTING DASHBOARD (Hanya jika mode 1 dan ada file order)
    if sel_mode in ['', '1']:
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

    # STRATEGY
    print("\nPilih strategi penjadwalan:")
    print("1. Jadwalkan dengan Interval Jam (Otomatis)")
    print("2. Jadwalkan dengan Interval Hari (Otomatis)")
    print("3. Manual per Album (Tanya setiap album)")
    print("4. Langsung Publish Semua")
    print("5. Simpan Semua sebagai Draf Lokal")
    choice = input("Pilihan: ").strip()

    is_post_now = (choice == '4')
    is_draft = (choice == '5')
    
    current_time_obj = None
    interval_mins = 0
    
    if choice in ['1', '2']:
        start_time_input = get_datetime_input("Masukkan waktu mulai untuk album PERTAMA")
        current_time_obj = datetime.now() + timedelta(minutes=11) if start_time_input == 'now' else start_time_input
        unit = "jam" if choice == '1' else "hari"
        interval_val = int(input(f"Masukkan interval per album (dalam {unit}): ").strip())
        interval_mins = interval_val * 60 if choice == '1' else interval_val * 1440
    elif choice == '3':
        interval_mins = 0
    elif choice == '4':
        interval_mins = int(input("Jeda antar posting (menit) [Enter=0]: ") or 0)

    is_headless = input("Gunakan Mode Headless (n VNC)? (y/n): ").lower() == 'y'
    print("\n--- Pilihan Pratinjau ---")
    print("1. Tanpa Pratinjau")
    print("2. Pratinjau Terminal (Ringkas)")
    print("3. Pratinjau Web Interaktif (Full - Bisa Edit/Urut)")
    preview_choice = input("Pilih [1/2/3, default 1]: ").strip()
    is_preview = (preview_choice == '2')
    is_web_preview = (preview_choice == '3')

    # DATA PREP
    item_data_map = {}
    temp_time = current_time_obj
    for p in pending_items:
        sched_str = None
        if choice in ['1', '2'] and temp_time:
            # Tambahkan jitter 1-5 menit (ala reference script)
            jitter_time = temp_time + timedelta(minutes=random.randint(1, 5))
            sched_str = jitter_time.strftime("%Y-%m-%d %H:%M")
            temp_time += timedelta(minutes=interval_mins)
        elif choice == '3':
            pass
        
        item_data_map[p] = {
            'caption': get_caption_text(p),
            'media_files': get_media_files(p),
            'schedule_time': sched_str
        }

    if is_web_preview:
        pending_items, item_data_map = run_interactive_preview_web(pending_items, item_data_map)
        if not pending_items: return

    if is_draft:
        drafts = load_drafts()
        for item in pending_items:
            drafts[item] = item_data_map[item]
            drafts[item]['profile'] = sel_profile
        save_drafts(drafts)
        print(f"✅ {len(pending_items)} postingan disimpan ke draf lokal.")
        return

    # START SELENIUM
    setup_sticky_footer()
    driver = setup_driver(os.path.join(os.getcwd(), "fb_profiles", sel_profile), headless=is_headless)
    try:
        for i, item in enumerate(pending_items):
            print_progress_bar(i, len(pending_items))
            data = item_data_map.get(item, {})
            media_files = data.get('media_files', [])
            caption = data.get('caption')
            sched_str = data.get('schedule_time')
            
            # SPLITTING LOGIC (Logic ala reference script)
            if len(media_files) > 20:
                print(f"\n⚠️  Folder '{os.path.basename(item)}' punya {len(media_files)} foto (lebih dari 20).")
                print("1. Tetap upload semua sekaligus (mungkin gagal/lama).")
                print("2. Upload Part 1 (20 foto), sisanya simpan sebagai Part Sisa.")
                print("3. Upload sejumlah (n) foto, sisanya simpan sebagai Part Sisa.")
                split_choice = input("Pilih opsi (1/2/3, default 2): ").strip() or '2'
                
                if split_choice in ['2', '3']:
                    n = 20 if split_choice == '2' else int(input("Masukkan jumlah foto: "))
                    part1_files = media_files[:n]
                    part2_files = [os.path.basename(f) for f in media_files[n:]]
                    
                    if run_fb_scheduled_task(driver, sel_profile, item, sched_str, preview=is_preview, pre_caption=caption, custom_media=part1_files):
                        pending = load_pending_parts()
                        p2_key = f"{os.path.basename(item)} (Part 2)"
                        pending[p2_key] = {
                            "path": item,
                            "remaining_photos": part2_files,
                            "caption": caption,
                            "profile": sel_profile
                        }
                        save_pending_parts(pending)
                        print(f"✅ Part 1 Berhasil. Sisa {len(part2_files)} foto disimpan ke Part Sisa.")
                    continue

            if choice == '3':
                res = get_datetime_input(f"Jadwal untuk {os.path.basename(item)}")
                sched_str = None if res == 'now' else res.strftime("%Y-%m-%d %H:%M")
            
            if run_fb_scheduled_task(driver, sel_profile, item, sched_str, preview=is_preview, pre_caption=caption, custom_media=media_files):
                if not sched_str and interval_mins > 0 and item != pending_items[-1]:
                    print(f"[*] Menunggu {interval_mins} menit...")
                    time.sleep(interval_mins * 60)
            else:
                if input("[?] Lanjut? (y/n): ").lower() != 'y': break
        
        print_progress_bar(len(pending_items), len(pending_items))
        reset_scroll_region()
        print("✅ SEMUA POSTINGAN BERHASIL DIPROSES.")
    finally: driver.quit()

def load_pending_parts():
    path = os.path.join(os.getcwd(), "pending_parts.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {}

def save_pending_parts(data):
    path = os.path.join(os.getcwd(), "pending_parts.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def run_pending_parts_mode():
    clear_screen()
    print("🔄 Lanjutkan Upload Part Sisa\n")
    pending = load_pending_parts()
    if not pending:
        print("[-] Tidak ada Part Sisa yang pending."); return

    pending_list = list(pending.items())
    for i, (key, data) in enumerate(pending_list):
        print(f"{i+1}. {key} ({len(data['remaining_photos'])} foto)")
    
    choice = input("\nPilih nomor (atau 0 untuk batal): ").strip()
    if not choice.isdigit() or int(choice) == 0: return
    
    idx = int(choice) - 1
    if not (0 <= idx < len(pending_list)): return
    
    sel_key, sel_data = pending_list[idx]
    
    # Logic to upload remaining photos (similar to run_album_post_mode but simplified)
    profile = sel_data.get('profile', 'Default')
    print(f"[*] Melanjutkan '{sel_key}' menggunakan profil '{profile}'...")
    
    is_headless = input("Gunakan Mode Headless (n VNC)? (y/n): ").lower() == 'y'
    driver = setup_driver(os.path.join(os.getcwd(), "fb_profiles", profile), headless=is_headless)
    try:
        # Ask for schedule
        res = get_datetime_input("Jadwal")
        sched_str = None if res == 'now' else res.strftime("%Y-%m-%d %H:%M")
        
        # We need to temporarily recreate the folder structure or handle the files directly
        # In this implementation, we assume the folder still exists
        item_path = sel_data['path']
        media_files = [os.path.join(item_path, f) for f in sel_data['remaining_photos']]
        
        # Override get_media_files to use our specific list for this task
        # We'll pass media_files directly to run_fb_scheduled_task by modifying it to accept custom_media
        if run_fb_scheduled_task(driver, profile, item_path, sched_str, pre_caption=sel_data.get('caption'), custom_media=media_files):
            del pending[sel_key]
            save_pending_parts(pending)
            print("✅ Part Sisa berhasil diproses.")
    finally: driver.quit()

def run_fb_scheduled_task(driver, profile_name, post_path, schedule_time=None, preview=False, pre_caption=None, custom_media=None):
    wait = WebDriverWait(driver, 30)
    item_name = os.path.basename(post_path)
    is_file = os.path.isfile(post_path)
    
    media_files = custom_media if custom_media else get_media_files(post_path)
    if not media_files:
        print(f"    [!] Skip: Tidak ada media di {item_name}")
        return False

    caption_text = pre_caption if pre_caption else get_caption_text(post_path)

    # --- PRATINJAU POSTINGAN (Style ala auto_poster_album.py) ---
    if preview:
        print("\n" + "═"*60)
        print("   👀 PRATINJAU POSTINGAN FB")
        print("═"*60)
        print(f"📁 Item    : {item_name}")
        print(f"🕒 Jadwal  : {schedule_time if schedule_time else '🚀 Posting SEKARANG'}")
        print(f"🖼️  Media   : {len(media_files)} file")
        for i, m in enumerate(media_files[:3]):
            print(f"   {i+1}. {os.path.basename(m)}")
        if len(media_files) > 3:
            print(f"   ... dan {len(media_files)-3} lainnya.")
        print("─" * 60)
        print(f"📝 Caption :\n{caption_text}")
        print("═"*60)
        
        # Cek apakah stdin adalah TTY sebelum meminta input
        if sys.stdin.isatty():
            confirm = input("\n[?] Lanjut upload? (y/n, default y): ").lower()
            if confirm == 'n':
                print("❌ Upload dibatalkan oleh pengguna.")
                return False
        else:
            print("⚠️  Mode non-interaktif, melewati konfirmasi pratinjau.")

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
                
                # Fallback: Cek jika tombol 'Berikutnya'/'Next' atau 'Kirim'/'Post' sudah muncul dan aktif
                if time.time() - start_wait > 5:
                    check_btn_xpath = (
                        "//div[@role='dialog']//div[@aria-label='Berikutnya' or @aria-label='Next' or @aria-label='Selesai' or @aria-label='Done']"
                        "| //div[@role='dialog']//div[@role='button'][.//span[text()='Kirim' or text()='Posting' or text()='Post']]"
                        "| //div[@role='dialog']//div[@aria-label='Kirim' or @aria-label='Posting' or @aria-label='Post']"
                    )
                    check_btns = driver.find_elements(By.XPATH, check_btn_xpath)
                    
                    btn_ready = False
                    for b in check_btns:
                        if b.is_displayed():
                            if b.get_attribute("aria-disabled") != "true":
                                btn_ready = True
                                break
                                
                    if btn_ready:
                        print("\n    [+] Tombol navigasi/post terdeteksi aktif, upload selesai.")
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

def run_draft_mode():
    clear_screen()
    print("🗓️  Kelola Draf Tersimpan\n")
    drafts = load_drafts()
    if not drafts:
        print("[-] Tidak ada draf tersimpan."); return

    draft_list = list(drafts.items())
    for i, (path, data) in enumerate(draft_list):
        print(f"{i+1}. {os.path.basename(path)} (Profil: {data.get('profile', 'Default')})")
    
    choice = input("\nPilih nomor draf (atau 0 untuk batal): ").strip()
    if not choice.isdigit() or int(choice) == 0: return
    
    idx = int(choice) - 1
    if not (0 <= idx < len(draft_list)): return
    
    sel_path, sel_data = draft_list[idx]
    
    print(f"\nOpsi untuk '{os.path.basename(sel_path)}':")
    print("1. Posting / Jadwalkan Sekarang")
    print("2. Hapus Draf")
    print("3. Batal")
    opt = input("Pilih: ").strip()
    
    if opt == '1':
        res = get_datetime_input("Jadwal")
        sched_str = None if res == 'now' else res.strftime("%Y-%m-%d %H:%M")
        
        is_headless = input("Gunakan Mode Headless (n VNC)? (y/n): ").lower() == 'y'
        profile = sel_data.get('profile', 'Default')
        setup_sticky_footer()
        driver = setup_driver(os.path.join(os.getcwd(), "fb_profiles", profile), headless=is_headless)
        try:
            print_progress_bar(0, 1)
            media_files = sel_data.get('media_files')
            if run_fb_scheduled_task(driver, profile, sel_path, sched_str, pre_caption=sel_data.get('caption'), custom_media=media_files):
                del drafts[sel_path]
                save_drafts(drafts)
                print_progress_bar(1, 1)
                reset_scroll_region()
                print("✅ DRAF BERHASIL DIPOSTING.")
        finally: driver.quit()
    elif opt == '2':
        del drafts[sel_path]
        save_drafts(drafts)
        print("✅ Draf dihapus.")

def run_profile_mode():
    clear_screen()
    print("🔄 Kelola Profil Browser\n")
    profile_dir = os.path.join(os.getcwd(), "fb_profiles")
    profiles = sorted([d for d in os.listdir(profile_dir) if os.path.isdir(os.path.join(profile_dir, d))])
    
    for i, p in enumerate(profiles): print(f"{i+1}. {p}")
    
    print("\nOpsi:")
    print("1. Buka Profil (Cek Login / VNC)")
    print("2. Batal")
    choice = input("Pilih: ").strip()
    
    if choice == '1':
        p_idx = int(input("Pilih Nomor Profil: ")) - 1
        sel_profile = profiles[p_idx]
        print(f"[*] Membuka browser untuk profil '{sel_profile}'...")
        driver = setup_driver(os.path.join(os.getcwd(), "fb_profiles", sel_profile), headless=False)
        input("\n[!] Tekan ENTER di sini jika sudah selesai mengecek browser untuk menutup...")
        driver.quit()

def run_single_post_mode():
    print("\n🖼️ Mode Postingan Tunggal (WIP)")
    print("Fitur ini akan segera hadir.")
    time.sleep(2)

def main_menu():
    while True:
        clear_screen()
        print("🚀 Facebook Auto-Poster Terpadu (Selenium) 🚀")
        print("=====================================")
        print("1. 📚 Mode Postingan Album")
        print("2. 🗓️  Kelola Draf Tersimpan")
        print("3. 🔄 Lanjutkan Upload Part Sisa (WIP)")
        print("4. 🖼️  Mode Postingan Tunggal (WIP)")
        print("5. 🔄 Kelola Profil Browser")
        print("0. 🚪 Keluar")
        
        choice = input("\nMasukkan pilihan (1-5, 0): ").strip()
        
        if choice == '1': run_album_post_mode()
        elif choice == '2': run_draft_mode()
        elif choice == '3': run_pending_parts_mode()
        elif choice == '4': run_single_post_mode()
        elif choice == '5': run_profile_mode()
        elif choice == '0': break
        
        if choice != '0': input("\nTekan Enter untuk kembali ke menu utama...")

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
    parser.add_argument("--preview", action="store_true", help="Tampilkan pratinjau terminal")
    parser.add_argument("--web-preview", action="store_true", help="Tampilkan pratinjau interaktif via Web Browser")
    args = parser.parse_args()

    # --- JALANKAN MENU UTAMA JIKA TANPA ARGUMEN ---
    if not any([args.profile, args.path, args.multi]):
        main_menu()
        sys.exit()

    print("\n=== FB SMART SCHEDULED UPLOADER (CLI MODE) ===")
    
    # --- LOGIKA MULTI AKUN (NON-INTERAKTIF / AUTO SCAN) ---
    if args.multi:
        interval_mins = args.interval if args.interval is not None else 30
        is_headless = args.headless
        is_preview = args.preview
        is_web_preview = args.web_preview
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
                        # Web preview biasanya tidak cocok untuk mode multi-scan, tapi kita support jika flag ada
                        if is_web_preview:
                            item_data_map = {next_post: {'caption': get_caption_text(next_post), 'media_files': get_media_files(next_post), 'schedule_time': None}}
                            pending_items, item_data_map = run_interactive_preview_web([next_post], item_data_map)
                            if not pending_items: continue
                            next_post = pending_items[0]
                            data = item_data_map[next_post]
                            run_fb_scheduled_task(driver, profile, next_post, None, preview=is_preview, pre_caption=data['caption'], custom_media=data['media_files'])
                        else:
                            run_fb_scheduled_task(driver, profile, next_post, None, preview=is_preview)
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
        is_preview = args.preview
        is_web_preview = args.web_preview
    else:
        is_headless = input("Gunakan Mode Headless (n VNC)? (y/n): ").lower() == 'y'
        print("\n--- Pilihan Pratinjau ---")
        print("1. Tanpa Pratinjau")
        print("2. Pratinjau Terminal (Ringkas)")
        print("3. Pratinjau Web Interaktif (Full - Bisa Edit/Urut)")
        preview_choice = input("Pilih [1/2/3, default 1]: ").strip()
        is_preview = (preview_choice == '2')
        is_web_preview = (preview_choice == '3')

    # --- TAHAP PREVIEW WEB (JIKA DIPILIH) ---
    item_data_map = {}
    temp_time = current_time_obj
    for p in pending_items:
        sched_str = temp_time.strftime("%Y-%m-%d %H:%M") if temp_time else None
        item_data_map[p] = {
            'caption': get_caption_text(p),
            'media_files': get_media_files(p),
            'schedule_time': sched_str
        }
        if temp_time: temp_time += timedelta(minutes=interval_mins)

    if is_web_preview:
        pending_items, item_data_map = run_interactive_preview_web(pending_items, item_data_map)
        if not pending_items:
            print("[!] Semua postingan dibatalkan. Keluar.")
            sys.exit()

    if args.profile and pending_items:
        update_post_status(pending_items[0], "Inisialisasi bot...", 5)

    setup_sticky_footer()
    driver = setup_driver(os.path.join(os.getcwd(), "fb_profiles", sel_profile), headless=is_headless)
    try:
        for i, item in enumerate(pending_items):
            print_progress_bar(i, len(pending_items))
            update_post_status(item, "Browser siap, memulai...", 8)
            data = item_data_map.get(item, {})
            sched_str = data.get('schedule_time')
            caption = data.get('caption')
            media_files = data.get('media_files', [])
            
            if run_fb_scheduled_task(driver, sel_profile, item, sched_str, preview=is_preview, pre_caption=caption, custom_media=media_files):
                # Jeda antar posting jika bukan terjadwal
                if not sched_str and interval_mins > 0 and item != pending_items[-1]:
                    print(f"[*] Menunggu {interval_mins} menit sebelum posting berikutnya...")
                    time.sleep(interval_mins * 60)
            else:
                if input("[?] Lanjut? (y/n): ").lower() != 'y': break
        
        print_progress_bar(len(pending_items), len(pending_items))
        reset_scroll_region()
        print("✅ PROSES CLI SELESAI.")
    finally: driver.quit()
