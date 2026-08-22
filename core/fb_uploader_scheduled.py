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
import html
import shutil
import urllib.parse
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

def print_header(title):
    print(f"\n{CLR_BOLD}{CLR_WHITE}=== {title} ==={CLR_RESET}\n")

def print_menu_box(title, items):
    print(f"\n{CLR_BOLD}{CLR_WHITE}=== {title} ==={CLR_RESET}")
    for item in items:
        print(f"  {CLR_CYAN}{item}{CLR_RESET}")
    print()

# --- UTILS UNTUK STICKY FOOTER ---

def reset_scroll_region():
    """Mengembalikan terminal ke mode normal."""
    # Dinonaktifkan untuk mencegah pembersihan layar / pergeseran kursor
    pass

def setup_sticky_footer():
    """Menyiapkan terminal untuk sticky footer di baris terakhir."""
    # Dinonaktifkan agar tidak membagi wilayah layar terminal
    pass

def print_progress_bar(current, total):
    """Menampilkan progress bar secara inline tanpa escape code pembagi layar."""
    try:
        _, cols = os.get_terminal_size()
    except:
        cols = 80
        
    if total == 0:
        percent = 0.0
        filled_len = 0
    else:
        percent = (current / total) * 100
        bar_len = min(cols - 35, 40)
        if bar_len < 10: bar_len = 10
        filled_len = int(bar_len * current // total)
        
    bar_len = min(cols - 35, 40)
    if bar_len < 10: bar_len = 10
    bar = '█' * filled_len + '░' * (bar_len - filled_len)
    
    # Progress text (Hijau)
    bar_text = f"{CLR_GREEN}⚡ [PROGRESS UPLOAD] : [{bar}] {current}/{total} ({percent:.1f}%){CLR_RESET}"
    print(f"\n{bar_text}\n")

# --- FUNGSI PREVIEW INTERAKTIF (Ala auto_poster_album.py) ---

def get_template_paths():
    search_paths = [
        Path(__file__).resolve().parent,
        Path("/storage/emulated/0/ProjectKURKUR"),
        Path(os.getcwd())
    ]
    templates = []
    seen = set()
    for p in search_paths:
        if p.exists():
            for f in p.glob("bersambung*"):
                if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.png'] and f.name not in seen:
                    templates.append(f)
                    seen.add(f.name)
    return sorted(templates)

def load_photo_captions(item_path):
    captions_data = {}
    if os.path.isfile(item_path):
        return captions_data
    manifest_path = os.path.join(item_path, "content_manifest.json")
    if not os.path.exists(manifest_path):
        return captions_data

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        
        for filename, data in manifest.items():
            if isinstance(data, dict):
                captions_data[filename] = {
                    "description": data.get("description", "").strip(),
                    "description2": data.get("description2", "").strip()
                }
        return captions_data
    except Exception as e:
        print(f"[!] Gagal membaca content_manifest.json di {os.path.basename(item_path)}: {e}")
        return {}

class AlbumPreviewState:
    def __init__(self, pending_items, item_data_map, templates=None):
        self.pending_items = pending_items # List of paths
        self.item_data_map = item_data_map # Path -> {caption, media_files, schedule_time, photo_captions}
        self.templates = templates or []
        self.lock = threading.Lock()
        self.server_should_shutdown = False

class AlbumPreviewRequestHandler(http.server.BaseHTTPRequestHandler):
    def __init__(self, state, *args, **kwargs):
        self.state = state
        http.server.BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

    def log_message(self, format, *args):
        return # Silent logs

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            html_content = self.generate_html()
            self.wfile.write(html_content.encode('utf-8'))
        elif self.path.startswith('/media/'):
            # Path format: /media/<item_idx>/<media_idx>
            parts = self.path.split('/')
            if len(parts) >= 4:
                try:
                    item_idx = int(parts[2])
                    media_idx = int(parts[3])
                    item_key = self.state.pending_items[item_idx]
                    data = self.state.item_data_map.get(item_key, {})
                    media_files = data.get('media_files', [])
                    
                    media_path = None
                    if 0 <= media_idx < len(media_files):
                        media_path = media_files[media_idx]
                    
                    if media_path and os.path.exists(media_path):
                        self.send_response(200)
                        ext = os.path.splitext(media_path)[1].lower()
                        mime = "image/jpeg"
                        if ext in ['.mp4', '.mov', '.avi']: mime = "video/mp4"
                        elif ext == '.png': mime = "image/png"
                        elif ext == '.webp': mime = "image/webp"
                        
                        self.send_header("Content-type", mime)
                        self.end_headers()
                        with open(media_path, 'rb') as f:
                            self.wfile.write(f.read())
                        return
                except Exception as e:
                    print(f"[!] Media serve error: {e}")
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
                media_idx = data.get('media_idx')
                filename = data.get('filename')
                item_path = self.state.pending_items[idx]
                media_files = self.state.item_data_map[item_path]['media_files']
                
                if media_idx is not None and 0 <= media_idx < len(media_files):
                    media_files.pop(media_idx)
                else:
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
        elif self.path == '/edit_photo_caption':
            with self.state.lock:
                idx = data['index']
                photo_name = data['photo_name']
                new_caption = data['caption']
                item_path = self.state.pending_items[idx]
                
                if 'photo_captions' not in self.state.item_data_map[item_path]:
                    self.state.item_data_map[item_path]['photo_captions'] = {}
                    
                if photo_name in self.state.item_data_map[item_path]['photo_captions']:
                    self.state.item_data_map[item_path]['photo_captions'][photo_name]['description2'] = new_caption
                else:
                    self.state.item_data_map[item_path]['photo_captions'][photo_name] = {'description': '', 'description2': new_caption}
            self.send_response(200)
            self.end_headers()
        elif self.path == '/add_connector':
            with self.state.lock:
                idx = data['index']
                template_name = data['template_name']
                
                template_path = next((p for p in self.state.templates if p.name == template_name), None)
                item_path = self.state.pending_items[idx]
                
                if template_path and os.path.exists(item_path):
                    try:
                        timestamp = int(time.time() * 1000)
                        ext = template_path.suffix
                        new_filename = f"connector_{timestamp}{ext}"
                        
                        # Tentukan target directory
                        target_dir = item_path if os.path.isdir(item_path) else os.path.dirname(item_path)
                        new_path = os.path.join(target_dir, new_filename)
                        
                        shutil.copyfile(str(template_path), new_path)
                        
                        self.state.item_data_map[item_path]['media_files'].append(new_path)
                        
                        if 'photo_captions' not in self.state.item_data_map[item_path]:
                            self.state.item_data_map[item_path]['photo_captions'] = {}
                        self.state.item_data_map[item_path]['photo_captions'][new_filename] = {'description': '', 'description2': ''}
                    except Exception as e:
                        print(f"[!] Error adding connector: {e}")
                        self.send_response(500)
                        self.end_headers()
                        return
            self.send_response(200)
            self.end_headers()
        elif self.path == '/reorder_photos':
            with self.state.lock:
                idx = data['index']
                item_path = self.state.pending_items[idx]
                current_photos = self.state.item_data_map[item_path]['media_files']
                
                if 'photo_order_indices' in data:
                    new_order_indices = [int(i) for i in data['photo_order_indices']]
                    new_photo_list = [current_photos[i] for i in new_order_indices if 0 <= i < len(current_photos)]
                    self.state.item_data_map[item_path]['media_files'] = new_photo_list
                elif 'photo_order' in data:
                    new_order_filenames = data['photo_order']
                    photo_map = {os.path.basename(p): p for p in current_photos}
                    new_photo_list = [photo_map[name] for name in new_order_filenames if name in photo_map]
                    self.state.item_data_map[item_path]['media_files'] = new_photo_list
            self.send_response(200)
            self.end_headers()

    def generate_html(self):
        items_html = ""
        for i, path in enumerate(self.state.pending_items):
            data = self.state.item_data_map[path]
            name = os.path.basename(path)
            photo_captions_for_item = data.get('photo_captions', {})
            
            # Media Grid
            images_html = ""
            for m_idx, media_path in enumerate(data['media_files']):
                m_filename = os.path.basename(media_path)
                m_folder = os.path.basename(os.path.dirname(media_path))
                display_label = f"[{m_folder}] {m_filename}" if len(data.get('original_paths', [])) > 1 else m_filename
                
                ext = os.path.splitext(m_filename)[1].lower()
                is_video = ext in ['.mp4', '.mov', '.avi']
                media_url = f"/media/{i}/{m_idx}"
                
                if is_video:
                    media_tag = f'<div class="video-thumb"><img src="{media_url}"><div class="play-icon">▶</div></div>'
                else:
                    media_tag = f'<img src="{media_url}">'
                
                caption_data = photo_captions_for_item.get(m_filename, {'description': '', 'description2': ''})
                desc2 = caption_data.get('description2', '')
                desc1 = caption_data.get('description', '')

                photo_card_content = ''
                if desc2:
                    photo_card_content = f'''
                        <p class="photo-description" id="caption-{i}-{m_idx}">{html.escape(desc2)}</p>
                        <button class="edit-button" onclick="togglePhotoEdit(this, {i}, \'{m_filename}\')">Edit Caption</button>
                    '''
                elif desc1:
                    photo_card_content = f'''
                        <div class="caption-choice-container" id="choice-container-{i}-{m_idx}">
                            <p class="choice-prompt">Caption kosong. Pilih aksi:</p>
                            <select class="caption-choice-select" onchange="handleCaptionChoice(this, {i}, \'{m_filename}\', \'{html.escape(desc1)}\')">
                                <option value="use_desc">Gunakan 'description'</option>
                                <option value="empty" selected>Biarkan Kosong</option>
                            </select>
                            <p class="fallback-preview"><b>Preview:</b> {html.escape(desc1)}</p>
                        </div>
                        <p class="photo-description" id="caption-{i}-{m_idx}" style="display:none;"></p>
                        <button class="edit-button" onclick="togglePhotoEdit(this, {i}, \'{m_filename}\')" style="display:none;">Edit Caption</button>
                    '''
                else:
                    photo_card_content = f'''
                        <p class="photo-description" id="caption-{i}-{m_idx}"></p>
                        <button class="edit-button" onclick="togglePhotoEdit(this, {i}, \'{m_filename}\')">Edit Caption</button>
                    '''

                images_html += f"""
                <div class="photo-card" id="photo-{i}-{m_idx}" data-filename="{m_filename}" data-m-idx="{m_idx}">
                    {media_tag}
                    <div class="photo-info">
                        <p class="photo-filename">{html.escape(display_label)}</p>
                        {photo_card_content}
                    </div>
                    <button class="delete-photo-btn" onclick="deletePhoto({i}, {m_idx}, '{m_filename}')">×</button>
                </div>"""

            templates_html = ""
            if self.state.templates:
                template_opts = ""
                for t in self.state.templates:
                    try:
                        with open(t, "rb") as f:
                            t_b64 = base64.b64encode(f.read()).decode("utf-8")
                        t_src = f"data:image/{t.suffix[1:]};base64,{t_b64}"
                        template_opts += f'''
                        <div class="template-item" onclick="addConnector({i}, '{t.name}')">
                            <img src="{t_src}">
                            <span>{t.name}</span>
                        </div>'''
                    except: pass
                
                if template_opts:
                    templates_html = f'''
                    <div class="connector-container">
                        <p class="connector-label">Tambahkan Gambar Penyambung:</p>
                        <div class="template-list">{template_opts}</div>
                    </div>'''

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
                {templates_html}
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
                .container {{ max-width: 900px; margin: 20px auto; padding: 0 15px; padding-bottom: 100px; }}
                
                .item-card {{ background: white; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.2); overflow: hidden; border: 1px solid #ddd; }}
                .album-header {{ padding: 12px; border-bottom: 1px solid #ebedf0; display: flex; align-items: center; gap: 12px; background: #fafafa; }}
                .handle {{ cursor: grab; font-size: 20px; color: #8d949e; }}
                .album-info {{ flex: 1; }}
                .album-title {{ font-weight: bold; font-size: 15px; color: #1c1e21; }}
                .album-meta {{ font-size: 12px; color: #606770; margin-top: 2px; }}
                
                .caption-container {{ padding: 12px; }}
                textarea {{ width: 100%; box-sizing: border-box; border: 1px solid #ddd; border-radius: 6px; padding: 10px; font-family: inherit; font-size: 14px; min-height: 100px; resize: vertical; background: #f5f6f7; transition: border-color 0.2s; }}
                textarea:focus {{ outline: none; border-color: #1877f2; background: white; }}
                
                .photos-container {{ display: flex; flex-wrap: wrap; gap: 8px; padding: 12px; background: #f0f2f5; border-top: 1px solid #ebedf0; align-items: flex-start; }}
                
                .photo-card {{ width: 180px; position: relative; border: 1px solid #ddd; border-radius: 6px; overflow: hidden; background: #fff; display: flex; flex-direction: column; cursor: grab; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }}
                .photo-card img {{ width: 100%; height: 180px; object-fit: contain; background: #000; display: block; }}
                .photo-info {{ padding: 8px; font-size: 12px; }}
                .photo-filename {{ font-weight: bold; font-size: 11px; margin: 0 0 5px 0; word-wrap: break-word; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
                .photo-description {{ font-size: 11px; color: #333; margin: 5px 0 0 0; white-space: pre-wrap; word-wrap: break-word; background: #f0f2f5; padding: 4px; border-radius: 4px; border-left: 2px solid #1877f2; }}
                
                .edit-button {{ background: #e4e6eb; color: #050505; border: none; border-radius: 4px; padding: 4px 8px; cursor: pointer; font-size: 11px; font-weight: bold; margin-top: 5px; width: 100%; text-align: center; }}
                .edit-button:hover {{ background: #d8dadf; }}
                .choice-prompt {{ font-weight: bold; font-size: 10px; margin: 5px 0; color: #606770; }}
                .caption-choice-select {{ width: 100%; padding: 4px; border-radius: 4px; margin-bottom: 5px; font-size: 11px; }}
                .fallback-preview {{ font-size: 10px; color: #555; margin: 0; padding: 4px; background: #f0f0f0; border-radius: 4px; word-wrap: break-word; }}

                .delete-photo-btn {{ position: absolute; top: 4px; right: 4px; background: rgba(0,0,0,0.6); color: white; border: none; border-radius: 50%; width: 22px; height: 22px; cursor: pointer; font-size: 14px; display: flex; align-items: center; justify-content: center; z-index: 10; }}
                .delete-photo-btn:hover {{ background: #f02849; }}

                .add-photo-card {{ width: 180px; height: 260px; border: 2px dashed #ccd0d5; border-radius: 6px; display: flex; flex-direction: column; align-items: center; justify-content: center; cursor: pointer; color: #606770; background: #f5f6f7; box-sizing: border-box; }}
                .add-photo-card:hover {{ background: #ebedf0; border-color: #1877f2; color: #1877f2; }}
                .add-photo-card span {{ font-size: 32px; font-weight: bold; line-height: 1; }}
                .add-photo-card p {{ margin: 5px 0 0 0; font-size: 12px; font-weight: bold; }}

                .video-thumb {{ position: relative; width: 100%; height: 180px; background: #000; }}
                .video-thumb img {{ width: 100%; height: 100%; object-fit: contain; }}
                .play-icon {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: white; background: rgba(0,0,0,0.5); border-radius: 50%; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; font-size: 18px; border: 2px solid white; }}
                
                .btn-delete {{ background: #f02849; color: white; border: none; width: 28px; height: 28px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: bold; }}
                .btn-delete:hover {{ background: #d22846; }}
                
                .connector-container {{ padding: 0 12px 12px 12px; border-top: 1px solid #ebedf0; background: #fafafa; }}
                .connector-label {{ font-weight: bold; margin: 10px 0 5px; font-size: 13px; color: #606770; }}
                .template-list {{ display: flex; gap: 10px; overflow-x: auto; padding-bottom: 5px; }}
                .template-item {{ border: 1px solid #ddd; border-radius: 4px; padding: 4px; background: white; cursor: pointer; text-align: center; width: 80px; flex-shrink: 0; transition: all 0.2s; }}
                .template-item:hover {{ border-color: #1877f2; background: #e7f3ff; }}
                .template-item img {{ width: 100%; height: 60px; object-fit: cover; border-radius: 2px; display: block; margin-bottom: 4px; }}
                .template-item span {{ font-size: 9px; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: bold; }}

                .footer-actions {{ position: fixed; bottom: 0; left: 0; right: 0; background: white; padding: 15px; box-shadow: 0 -2px 10px rgba(0,0,0,0.1); display: flex; justify-content: center; z-index: 1000; }}
                .btn-start {{ background: #42b72a; color: white; border: none; padding: 12px 40px; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; transition: background 0.2s; }}
                .btn-start:hover {{ background: #36a420; }}
                
                .sortable-ghost {{ opacity: 0.4; background: #c8ebfb; }}
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
                function postAction(path, body) {{
                    return fetch(path, {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(body) }});
                }}

                function initSortable() {{
                    // Sort items (albums)
                    const container = document.getElementById('items-container');
                    new Sortable(container, {{
                        handle: '.handle',
                        animation: 150,
                        onEnd: function() {{
                            const order = Array.from(container.querySelectorAll('.item-card')).map(el => el.dataset.index);
                            postAction('/reorder', {{ order }});
                        }}
                    }});

                    // Sort photos inside each album
                    document.querySelectorAll('.photos-container').forEach(container => {{
                        if (container.sortableInstance) {{
                            container.sortableInstance.destroy();
                        }}
                        const itemIndex = container.id.replace('photos-container-', '');
                        container.sortableInstance = new Sortable(container, {{
                            animation: 150,
                            ghostClass: 'sortable-ghost',
                            filter: '.add-photo-card',
                            preventOnFilter: true,
                            onEnd: function (evt) {{
                                const newOrderIndices = Array.from(evt.to.querySelectorAll('.photo-card')).map(card => card.dataset.mIdx);
                                postAction('/reorder_photos', {{ index: parseInt(itemIndex), photo_order_indices: newOrderIndices }})
                                .then(r => {{
                                    if(r.ok) location.reload();
                                }});
                            }}
                        }});
                    }});
                }}

                document.addEventListener('DOMContentLoaded', initSortable);

                function editCaption(index, caption) {{
                    postAction('/edit_caption', {{ index, caption }});
                }}

                function deleteItem(index) {{
                    if(confirm('Hapus postingan ini dari antrean?')) {{
                        postAction('/delete_item', {{ index }}).then(() => location.reload());
                    }}
                }}

                function deletePhoto(index, mediaIdx, filename) {{
                    if(confirm('Hapus media ini?')) {{
                        postAction('/delete_photo', {{ index: index, media_idx: mediaIdx, filename: filename }})
                        .then(r => {{
                            if(r.ok) location.reload();
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
                            postAction('/add_photo', {{
                                index: index,
                                filename: file.name,
                                data: e.target.result
                            }}).then(r => {{
                                if(r.ok) location.reload();
                                else alert('Gagal menambah foto: ' + file.name);
                            }});
                        }};
                        reader.readAsDataURL(file);
                    }}
                }}

                function addConnector(index, templateName) {{
                    postAction('/add_connector', {{ index: index, template_name: templateName }})
                    .then(r => {{
                        if (r.ok) location.reload();
                        else alert('Gagal menambahkan connector');
                    }});
                }}

                function togglePhotoEdit(btn, index, photoName) {{
                    const el = document.getElementById('caption-' + index + '-' + photoName);
                    if (btn.textContent === 'Edit Caption') {{
                        el.contentEditable = true;
                        el.focus();
                        btn.textContent = 'Simpan';
                    }} else {{
                        el.contentEditable = false;
                        btn.textContent = 'Edit Caption';
                        postAction('/edit_photo_caption', {{
                            index: index,
                            photo_name: photoName,
                            caption: el.innerText
                        }});
                    }}
                }}

                function handleCaptionChoice(selectElement, index, photoName, fallbackCaption) {{
                    const choice = selectElement.value;
                    let newCaption = '';
                    if (choice === 'use_desc') {{
                        newCaption = fallbackCaption;
                    }}
                    
                    const choiceContainer = document.getElementById('choice-container-' + index + '-' + photoName);
                    const descriptionEl = choiceContainer.nextElementSibling;
                    const editButton = descriptionEl.nextElementSibling;

                    descriptionEl.innerText = newCaption;
                    choiceContainer.style.display = 'none';
                    descriptionEl.style.display = 'block';
                    editButton.style.display = 'inline-block';

                    postAction('/edit_photo_caption', {{
                        index: index,
                        photo_name: photoName,
                        caption: newCaption
                    }});
                }}

                function startUpload() {{
                    if(confirm('Mulai proses upload Selenium?')) {{
                        postAction('/shutdown', {{}}).then(() => {{
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

class SilentTCPServer(socketserver.TCPServer):
    def handle_error(self, request, client_address):
        exc_type, _, _ = sys.exc_info()
        if exc_type in (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return
        super().handle_error(request, client_address)

def run_interactive_preview_web(pending_items, item_data_map):
    templates = get_template_paths()
    state = AlbumPreviewState(list(pending_items), dict(item_data_map), templates=templates)
    PORT = 8080
    Handler = partial(AlbumPreviewRequestHandler, state)
    SilentTCPServer.allow_reuse_address = True
    
    # Cari port kosong jika 8080 dipakai
    while True:
        try:
            httpd = SilentTCPServer(('', PORT), Handler)
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
    try:
        sys.stdout.write("\033[r")     # Reset scroll region ke default
        sys.stdout.write("\033[?25h")   # Tampilkan kursor jika tersembunyi
        sys.stdout.flush()
    except:
        pass
    os.system('cls' if os.name == 'nt' else 'clear')

def getch():
    import sys
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
    import re
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

def get_datetime_input(prompt: str):
    while True:
        val = input(f"⏰ {CLR_BOLD}{prompt}{CLR_RESET}\n   (format: YYYY-MM-DD HH:MM atau ketik 'now'): ").strip().lower()
        if val in ['now', 'sekarang', 'y']:
            return 'now'
        try:
            return datetime.strptime(val, "%Y-%m-%d %H:%M")
        except ValueError:
            print(f"   {TAG_ERROR} Format salah. Mohon ulangi.")

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

def natural_sort_key(s):
    """Sort key for natural sorting (e.g. 01.jpg, 02.jpg, 10.jpg)."""
    basename = os.path.splitext(os.path.basename(s))[0]
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', basename)]

def get_media_files(path):
    valid_ext = (".mp4", ".jpg", ".png", ".jpeg", ".webp")
    if os.path.isfile(path):
        return [os.path.abspath(path)] if path.lower().endswith(valid_ext) else []
    
    media = []
    if os.path.exists(path):
        for f in os.listdir(path):
            if f.lower().endswith(valid_ext) and not f.lower().startswith(("bersambung", "tamat")):
                file_path = os.path.abspath(os.path.join(path, f))
                media.append(file_path)
    
    media.sort(key=natural_sort_key)
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
    # Bersihkan prefix angka indeks (misal: "0001. ") dan nomor episode (misal: "EP. 1 - ")
    clean_title = re.sub(r"^(?:[A-Z0-9]+\.\s*)?(?:EP\.\s*\d+(?:\s*[a-z])?\s*[-–]\s*)?", "", clean_name, flags=re.IGNORECASE).strip()
    default_title = clean_title if clean_title else clean_name.replace("_", " ").replace("-", " ").title()
    
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

def group_stories_only(pending_items):
    pattern = r"^(?:[A-Z0-9]+\.\s*)?(?:EP\.\s*\d+(?:\s*[a-z])?\s*[-–]\s*)?(.*?)(?:\s*\(\d+\))?$"
    groups = {}
    for p in pending_items:
        if os.path.isdir(p):
            bname = os.path.basename(p)
            m = re.match(pattern, bname, re.IGNORECASE)
            title = m.group(1).strip() if m else bname
        else:
            title = os.path.splitext(os.path.basename(p))[0]
            
        if title not in groups:
            groups[title] = []
        groups[title].append(p)

    story_items = []
    story_map = {}
    for title, paths in groups.items():
        # Urutkan folder episode secara natural (EP. 1, EP. 2, dst.)
        sorted_paths = sorted(paths, key=natural_sort_key)
        all_media = []

        for p in sorted_paths:
            if os.path.isdir(p):
                # Urutkan gambar di dalam tiap folder episode secara natural (01.jpg, 02.jpg, dst.)
                m_files = sorted([
                    os.path.join(p, f) for f in os.listdir(p) 
                    if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) 
                    and not f.lower().startswith(("bersambung", "tamat"))
                ], key=natural_sort_key)
                
                all_media.extend(m_files)
            else:
                all_media.append(p)
                
        if not all_media: continue
        story_key = sorted_paths[0]
        story_items.append(story_key)
        story_map[story_key] = {
            "caption": title,
            "media_files": all_media,
            "schedule_time": None,
            "photo_captions": {},
            "display_name": title,
            "story_title": title,
            "original_paths": sorted_paths
        }
    return story_items, story_map, groups

def split_stories_into_parts(story_items, story_map):
    new_items = []
    new_map = {}
    for key in story_items:
        data = story_map[key]
        title = data.get("caption") or data.get("story_title")
        all_media = data["media_files"]
        paths = data["original_paths"]
        
        chunk_size = 20
        chunks = [all_media[i:i + chunk_size] for i in range(0, len(all_media), chunk_size)]
        
        for idx, chunk in enumerate(chunks, 1):
            is_last = (idx == len(chunks))
            img_name = "tamat.jpg" if is_last else "bersambung.jpg"
            parent_dir = os.path.dirname(paths[0])
            parent_suffix = os.path.join(parent_dir, img_name)
            fallback_suffix = f"/storage/emulated/0/ProjectKURKUR/{img_name}"
            suffix_img = parent_suffix if os.path.exists(parent_suffix) else fallback_suffix
            
            final_chunk = list(chunk)
            if os.path.exists(suffix_img):
                final_chunk.append(suffix_img)
                
            caption_title = f"{title} ({idx})" if len(chunks) > 1 else title
            part_key = f"{paths[0]}__part_{idx}" if len(chunks) > 1 else paths[0]
            
            new_items.append(part_key)
            new_map[part_key] = {
                "caption": caption_title,
                "media_files": final_chunk,
                "schedule_time": data.get("schedule_time"),
                "photo_captions": data.get("photo_captions", {}),
                "display_name": caption_title,
                "story_title": title,
                "original_paths": paths
            }
            
    return new_items, new_map

def get_title_from_path(p):
    pattern = r"^(?:[A-Z0-9]+\.\s*)?(?:EP\.\s*\d+(?:\s*[a-z])?\s*[-–]\s*)?(.*?)(?:\s*\(\d+\))?$"
    if os.path.isdir(p):
        bname = os.path.basename(p)
        m = re.match(pattern, bname, re.IGNORECASE)
        return m.group(1).strip() if m else bname
    return os.path.splitext(os.path.basename(p))[0]

def run_album_post_mode(args=None):
    clear_screen()
    print_header("📚 MODE POSTINGAN ALBUM")
    
    profile_dir = os.path.join(os.getcwd(), "fb_profiles")
    profiles = sorted([d for d in os.listdir(profile_dir) if os.path.isdir(os.path.join(profile_dir, d))])
    if not profiles:
        print(f"{TAG_ERROR} Profil browser kosong! Sila buat profil dahulu.")
        return

    profile_options = [f"{i+1}. {p}" for i, p in enumerate(profiles)]
    sel_idx = select_menu_option("PILIH PROFIL FACEBOOK", profile_options)
    sel_profile = profiles[sel_idx]

    parent_folder = input(f"\n{TAG_INPUT} Masukkan Path Folder Utama: ").strip().replace('"', '').replace("'", "")
    if not os.path.isdir(parent_folder):
        print(f"{TAG_ERROR} Folder tidak valid!")
        return

    print(f"\n{TAG_INFO} Memindai folder dan menyiapkan daftar episode...")

    # DETEKSI PENDING (Smarter Detection: Skip folder/file yang sudah memiliki marker uploadedfb)
    all_items = sorted([os.path.join(parent_folder, f) for f in os.listdir(parent_folder)], key=natural_sort_key)
    pending_items = []
    
    for item in all_items:
        item_name = os.path.basename(item)
        if item_name == "queue_order.json": continue
        
        is_dir = os.path.isdir(item)
        is_media = any(item.lower().endswith(ext) for ext in (".mp4", ".jpg", ".png", ".jpeg", ".webp"))
        
        if is_dir:
            # 1. Cek apakah folder ini sendiri memiliki marker uploadedfb.txt
            if os.path.exists(os.path.join(item, "uploadedfb.txt")):
                continue
            
            # 2. Cek apakah ini folder episode atau folder seri yang berisi subfolder episode
            sub_dirs = [os.path.join(item, d) for d in os.listdir(item) if os.path.isdir(os.path.join(item, d))]
            if sub_dirs:
                # Jika berisi subfolder episode, filter hanya subfolder yang belum di-upload
                has_valid_sub = False
                for sd in sub_dirs:
                    if not os.path.exists(os.path.join(sd, "uploadedfb.txt")):
                        if any(f.lower().endswith((".mp4", ".jpg", ".png", ".jpeg", ".webp")) for f in os.listdir(sd)):
                            pending_items.append(sd)
                            has_valid_sub = True
                # Jika tidak ada subfolder tapi ada foto di folder ini
                if not has_valid_sub and any(f.lower().endswith((".mp4", ".jpg", ".png", ".jpeg", ".webp")) for f in os.listdir(item)):
                    pending_items.append(item)
            else:
                # Jika folder episode langsung (isi foto), cek media
                if any(f.lower().endswith((".mp4", ".jpg", ".png", ".jpeg", ".webp")) for f in os.listdir(item)):
                    pending_items.append(item)
        elif is_media:
            # Jika file media tunggal, cek marker file-nya
            if not os.path.exists(item + ".uploadedfb"):
                pending_items.append(item)

    if not pending_items:
        print(f"\n{TAG_WARNING} Tidak ada konten baru.")
        return
    
    # 1. GROUPING CERITA UTUH (Disajikan per judul seri komik)
    story_items, story_map, story_groups = group_stories_only(pending_items)
    story_titles = list(story_groups.keys())

    print(f"\n{TAG_SUCCESS} Terdeteksi {CLR_BOLD}{CLR_GREEN}{len(story_titles)}{CLR_RESET} judul seri komik.")
    
    upload_modes = [
        "1. Unggah Semua Album (sesuai urutan)",
        "2. Unggah Sejumlah Album Secara Acak",
        "3. Pilih Album Tertentu untuk Diunggah",
        "4. Unggah Satu Album Acak"
    ]
    sel_mode_idx = select_menu_option("PILIH MODE UNGGAHAN", upload_modes)
    sel_mode = str(sel_mode_idx + 1)

    if sel_mode == '1':
        pass
    elif sel_mode == '2':
        try:
            num_random = int(input(f"\n{TAG_INPUT} Berapa seri judul acak (maks: {len(story_titles)})? ").strip())
            chosen_titles = random.sample(story_titles, min(num_random, len(story_titles)))
            story_items = [s for s in story_items if story_map[s]['story_title'] in chosen_titles]
        except ValueError:
            print(f"   {TAG_ERROR} Input tidak valid, menggunakan semua album.")
    elif sel_mode == '3':
        menu_items = []
        for idx, t in enumerate(story_titles, 1):
            s_key = [k for k in story_items if story_map[k]['story_title'] == t][0]
            total_photos = len(story_map[s_key]['media_files'])
            menu_items.append(f"{idx}. {t} ({total_photos} foto utuh)")

        print_menu_box("PILIH ALBUM CERITA", menu_items)
        choices = input(f"\n{TAG_INPUT} Masukkan nomor (pisahkan dengan koma, cth: 1,3,5): ").strip()
        indices = [int(i.strip()) - 1 for i in choices.split(',') if i.strip().isdigit()]
        selected_titles = set(story_titles[i] for i in indices if 0 <= i < len(story_titles))
        story_items = [s for s in story_items if story_map[s]['story_title'] in selected_titles]
    elif sel_mode == '4':
        chosen_title = random.choice(story_titles)
        story_items = [s for s in story_items if story_map[s]['story_title'] == chosen_title]

    # STRATEGY
    sched_options = [
        "1. Jadwalkan dengan Interval Jam (Otomatis)",
        "2. Jadwalkan dengan Interval Hari (Otomatis)",
        "3. Manual per Album (Tanya setiap album)",
        "4. Langsung Publish Semua",
        "5. Simpan Semua sebagai Draf Lokal"
    ]
    choice_idx = select_menu_option("STRATEGI PENJADWALAN", sched_options)
    choice = str(choice_idx + 1)

    is_post_now = (choice == '4')
    is_draft = (choice == '5')
    
    current_time_obj = None
    interval_mins = 0
    
    if choice in ['1', '2']:
        start_time_input = get_datetime_input("Masukkan waktu mulai untuk album PERTAMA")
        current_time_obj = datetime.now() + timedelta(minutes=11) if start_time_input == 'now' else start_time_input
        unit = "jam" if choice == '1' else "hari"
        try:
            interval_val = int(input(f"\n{TAG_INPUT} Masukkan interval per album (dalam {unit}): ").strip())
            interval_mins = interval_val * 60 if choice == '1' else interval_val * 1440
        except ValueError:
            print(f"   {TAG_ERROR} Input tidak valid, menggunakan interval default 1 {unit}.")
            interval_mins = 60 if choice == '1' else 1440
    elif choice == '3':
        interval_mins = 0
    elif choice == '4':
        try:
            interval_mins = int(input(f"\n{TAG_INPUT} Jeda antar posting (menit) [Enter=0]: ") or 0)
        except ValueError:
            interval_mins = 0

    is_headless = input(f"\n{TAG_INPUT} Gunakan Mode Headless (n VNC)? (y/n, default n): ").lower() == 'y'
    preview_options = [
        "1. Tanpa Pratinjau",
        "2. Pratinjau Terminal (Ringkas)",
        "3. Pratinjau Web Interaktif (Full - Bisa Edit/Urut)"
    ]
    preview_idx = select_menu_option("PILIHAN PRATINJAU", preview_options)
    preview_choice = str(preview_idx + 1)
    is_preview = (preview_choice == '2')
    is_web_preview = (preview_choice == '3')

    # PRATINJAU WEB INTERAKTIF (Berdasarkan Judul Cerita Utuh)
    if is_web_preview:
        story_items, story_map = run_interactive_preview_web(story_items, story_map)
        if not story_items: return

    # 2. SEKARANG KITA SPLIT PER 20 FOTO (Auto-Split + Bersambung / Tamat)
    pending_items, item_data_map = split_stories_into_parts(story_items, story_map)

    # OPSI PENANGANAN PART (> 20 FOTO / MULTI-PART)
    multi_part_count = len(pending_items)
    if multi_part_count > 1:
        print(f"\n{TAG_WARNING} Terdeteksi total {CLR_BOLD}{multi_part_count}{CLR_RESET} Part postingan hasil split yang akan diunggah.")
        split_options = [
            "1. Unggah SEMUA Part bertahap sesuai interval jadwal.",
            "2. Unggah SEBAGIAN Part saja (sisanya simpan otomatis ke Part Sisa / pending_parts.json)."
        ]
        split_idx = select_menu_option("PILIH METODE UPLOAD PART", split_options)
        
        if split_idx == 1: # Pilih Opsi 2 (Sebagian)
            try:
                max_parts = int(input(f"\n{TAG_INPUT} Mau unggah berapa Part sekarang (1 - {multi_part_count})? ").strip())
            except ValueError:
                max_parts = 1
                
            parts_to_upload = pending_items[:max_parts]
            parts_to_save = pending_items[max_parts:]
            
            if parts_to_save:
                pending = load_pending_parts()
                for p_key in parts_to_save:
                    data_save = item_data_map[p_key]
                    pending[p_key] = {
                        "path": p_key,
                        "remaining_photos": [os.path.basename(f) for f in data_save['media_files']],
                        "caption": data_save['caption'],
                        "profile": sel_profile
                    }
                save_pending_parts(pending)
                print(f"   {TAG_SUCCESS} {len(parts_to_upload)} Part akan diunggah sekarang. {len(parts_to_save)} Part sisa disimpan ke pending_parts.json.")
            
            pending_items = parts_to_upload

    # PENETAPAN JADWAL & PROTEKSI 28 HARI
    max_allowed_date = datetime.now() + timedelta(days=28)
    valid_pending_items = []
    overflow_pending_items = []

    temp_time = current_time_obj
    for p in pending_items:
        sched_str = None
        if choice in ['1', '2'] and temp_time:
            jitter_time = temp_time + timedelta(minutes=random.randint(1, 5))
            if jitter_time > max_allowed_date:
                overflow_pending_items.append(p)
                continue
            sched_str = jitter_time.strftime("%Y-%m-%d %H:%M")
            temp_time += timedelta(minutes=interval_mins)
        
        item_data_map[p]['schedule_time'] = sched_str
        valid_pending_items.append(p)

    if overflow_pending_items:
        print(f"\n{TAG_WARNING} {len(overflow_pending_items)} Part terdeteksi melebihi batas jadwal Facebook (28 hari).")
        pending = load_pending_parts()
        for p_key in overflow_pending_items:
            data_save = item_data_map[p_key]
            pending[p_key] = {
                "path": p_key,
                "remaining_photos": [os.path.basename(f) for f in data_save['media_files']],
                "caption": data_save['caption'],
                "profile": sel_profile
            }
        save_pending_parts(pending)
        print(f"   {TAG_SUCCESS} {len(overflow_pending_items)} Part yang melebihi 28 hari otomatis disimpan ke pending_parts.json.")
        pending_items = valid_pending_items

    if is_web_preview:
        pending_items, item_data_map = run_interactive_preview_web(pending_items, item_data_map)
        if not pending_items: return

    if is_draft:
        drafts = load_drafts()
        for item in pending_items:
            drafts[item] = item_data_map[item]
            drafts[item]['profile'] = sel_profile
        save_drafts(drafts)
        print(f"\n{TAG_SUCCESS} {CLR_BOLD}{CLR_GREEN}{len(pending_items)}{CLR_RESET} postingan disimpan ke draf lokal.")
        return

    # START SELENIUM
    os.system('cls' if os.name == 'nt' else 'clear')
    setup_sticky_footer()
    dashboard = UploadDashboard(pending_items, item_data_map)
    driver = setup_driver(os.path.join(os.getcwd(), "fb_profiles", sel_profile), headless=is_headless)
    try:
        for i, item in enumerate(pending_items):
            dashboard.current_idx = i
            print_progress_bar(i, len(pending_items))
            data = item_data_map.get(item, {})
            media_files = data.get('media_files', [])
            caption = data.get('caption')
            sched_str = data.get('schedule_time')
            
            if choice == '3':
                res = get_datetime_input(f"Jadwal untuk {data.get('display_name', os.path.basename(item))}")
                sched_str = None if res == 'now' else res.strftime("%Y-%m-%d %H:%M")
            
            if run_fb_scheduled_task(driver, sel_profile, item, sched_str, preview=is_preview, pre_caption=caption, custom_media=media_files, dashboard=dashboard):
                if not sched_str and interval_mins > 0 and item != pending_items[-1]:
                    print(f"   {TAG_INFO} Menunggu {interval_mins} menit...")
                    time.sleep(interval_mins * 60)
            else:
                if input(f"\n{TAG_INPUT} Lanjut? (y/n, default y): ").lower() == 'n': break
        
        print_progress_bar(len(pending_items), len(pending_items))
        reset_scroll_region()
        print(f"\n{TAG_SUCCESS} {CLR_BOLD}{CLR_GREEN}SEMUA POSTINGAN BERHASIL DIPROSES.{CLR_RESET}")
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
    print_header("🔄 LANJUTKAN UPLOAD PART SISA")
    pending = load_pending_parts()
    if not pending:
        print(f"{TAG_WARNING} Tidak ada Part Sisa yang pending.")
        return

    pending_list = list(pending.items())
    pending_options = [f"{i+1}. {key} ({len(data['remaining_photos'])} foto)" for i, (key, data) in enumerate(pending_list)]
    pending_options.append(f"{len(pending_list)+1}. 🗑️  Bersihkan / Hapus Semua Part Pending")
    pending_options.append("0. Batal")
    
    idx = select_menu_option("DAFTAR PART SISA PENDING", pending_options)
    if idx == len(pending_options) - 1: # "0. Batal"
        return
    elif idx == len(pending_list): # Clear all
        save_pending_parts({})
        print(f"\n{TAG_SUCCESS} {CLR_BOLD}{CLR_GREEN}Semua data part pending berhasil dibersihkan!{CLR_RESET}")
        time.sleep(1.5)
        return
    
    sel_key, sel_data = pending_list[idx]
    
    # Logic to upload remaining photos (similar to run_album_post_mode but simplified)
    profile = sel_data.get('profile', 'Default')
    item_path = sel_data['path']
    print(f"\n{TAG_INFO} Melanjutkan '{CLR_BOLD}{sel_key}{CLR_RESET}' menggunakan profil '{CLR_BOLD}{profile}{CLR_RESET}'...")
    
    is_headless = input(f"\n{TAG_INPUT} Gunakan Mode Headless (n VNC)? (y/n, default n): ").lower() == 'y'
    res = get_datetime_input("Jadwal")
    sched_str = None if res == 'now' else res.strftime("%Y-%m-%d %H:%M")
    
    os.system('cls' if os.name == 'nt' else 'clear')
    dashboard = UploadDashboard([item_path], {item_path: {'schedule_time': sched_str}})
    driver = setup_driver(os.path.join(os.getcwd(), "fb_profiles", profile), headless=is_headless)
    try:
        
        # We need to temporarily recreate the folder structure or handle the files directly
        # In this implementation, we assume the folder still exists
        media_files = [os.path.join(item_path, f) for f in sel_data['remaining_photos']]
        
        # Override get_media_files to use our specific list for this task
        # We'll pass media_files directly to run_fb_scheduled_task by modifying it to accept custom_media
        if run_fb_scheduled_task(driver, profile, item_path, sched_str, pre_caption=sel_data.get('caption'), custom_media=media_files, dashboard=dashboard):
            del pending[sel_key]
            save_pending_parts(pending)
            print(f"\n{TAG_SUCCESS} {CLR_BOLD}{CLR_GREEN}Part Sisa berhasil diproses.{CLR_RESET}")
    finally: driver.quit()

class UploadDashboard:
    def __init__(self, pending_items, item_data_map):
        self.pending_items = list(pending_items)
        self.item_data_map = dict(item_data_map)
        self.statuses = {item: "pending" for item in self.pending_items}  # pending, processing, success, failed
        self.current_idx = 0
        self.success_count = 0
        self.failed_count = 0
        self.current_job = {
            "name": "",
            "date": "",
            "upload": "Pending",
            "caption": "Pending",
            "scheduling": "Pending",
            "activity": "Pending"
        }

    def render(self):
        sys.stdout.write("\033[H\033[J")
        
        # 1. Header
        print("╭──────────────────────────────────────────────────────────────╮")
        print("│                    ⚡ FACEBOOK SCHEDULER                     │")
        print("│                       Upload Manager                         │")
        print("╰──────────────────────────────────────────────────────────────╯")
        print()
        
        # 2. Progress
        total = len(self.pending_items)
        current = self.current_idx
        percent = 0.0 if total == 0 else (current / total) * 100
        bar_len = 36
        filled_len = int(bar_len * current // total) if total > 0 else 0
        bar = '█' * filled_len + '░' * (bar_len - filled_len)
        print("  Progress")
        print(f"  {CLR_GREEN}{bar}{CLR_RESET}  {current}/{total}  ({percent:.1f}%)")
        print()
        
        # 3. Current Job
        print("  CURRENT JOB")
        job = self.current_job
        name_truncated = job["name"][:50] + "..." if len(job["name"]) > 53 else job["name"]
        
        print(f"  📄 {CLR_BOLD}{CLR_WHITE}{name_truncated}{CLR_RESET}")
        print(f"  📅 {CLR_YELLOW}{job['date']}{CLR_RESET}")
        print()
        
        upload_status = job["upload"]
        if upload_status == "Completed":
            upload_line = f"{CLR_GREEN}✓ Selesai{CLR_RESET}"
        elif upload_status == "Pending":
            upload_line = f"{CLR_DIM}Pending{CLR_RESET}"
        elif upload_status == "Failed":
            upload_line = f"{CLR_RED}✗ Gagal{CLR_RESET}"
        else:
            upload_line = f"{CLR_BLUE}⟳ {upload_status}{CLR_RESET}"
            
        caption_status = job["caption"]
        if caption_status == "Injected":
            caption_line = f"{CLR_GREEN}✓ Selesai{CLR_RESET}"
        elif caption_status == "Pending":
            caption_line = f"{CLR_DIM}Pending{CLR_RESET}"
        elif caption_status == "Failed":
            caption_line = f"{CLR_RED}✗ Gagal{CLR_RESET}"
        else:
            caption_line = f"{CLR_BLUE}⟳ {caption_status}{CLR_RESET}"
            
        sched_status = job["scheduling"]
        if sched_status == "Completed":
            sched_line = f"{CLR_GREEN}✓ Selesai{CLR_RESET}"
        elif sched_status == "Pending":
            sched_line = f"{CLR_DIM}Pending{CLR_RESET}"
        elif sched_status == "Failed":
            sched_line = f"{CLR_RED}✗ Gagal{CLR_RESET}"
        else:
            sched_line = f"{CLR_BLUE}⟳ {sched_status}{CLR_RESET}"
            
        print(f"  📤 Upload       {upload_line}")
        print(f"  📝 Caption      {caption_line}")
        print(f"  🗓️  Scheduling  {sched_line}")
        
        # Activity field
        activity_status = job.get("activity", "-")
        activity_truncated = activity_status[:50] + "..." if len(activity_status) > 53 else activity_status
        print()
        print(f"  ⚙️ Aktivitas   {CLR_DIM}{activity_truncated}{CLR_RESET}")
        print()
        
        # 4. Recent (up to 4 items)
        print("  RECENT")
        recent_items = []
        for idx, item in enumerate(self.pending_items):
            item_name = os.path.basename(item)
            item_name_tr = item_name[:35] + "..." if len(item_name) > 38 else item_name
            status = self.statuses[item]
            
            sched_time = self.item_data_map[item].get('schedule_time')
            time_str = ""
            if sched_time:
                try:
                    time_str = sched_time.split()[1]
                except:
                    time_str = "sched"
            else:
                time_str = "now"
                
            if status == "success":
                icon = f"{CLR_GREEN}✓{CLR_RESET}"
                recent_items.append(f"  {icon} {item_name_tr:<38} {CLR_DIM}{time_str:>8}{CLR_RESET}")
            elif status == "failed":
                icon = f"{CLR_RED}✗{CLR_RESET}"
                recent_items.append(f"  {icon} {item_name_tr:<38} {CLR_RED}{time_str:>8}{CLR_RESET}")
            elif idx == current:
                icon = f"{CLR_BLUE}⟳{CLR_RESET}"
                recent_items.append(f"  {icon} {CLR_BOLD}{item_name_tr:<38} {CLR_YELLOW}{time_str:>8}{CLR_RESET}")
            else:
                icon = f"{CLR_DIM}○{CLR_RESET}"
                recent_items.append(f"  {icon} {CLR_DIM}{item_name_tr:<38} {time_str:>8}{CLR_RESET}")
                
        start_slice = max(0, current - 2)
        end_slice = min(len(recent_items), start_slice + 4)
        if end_slice - start_slice < 4 and len(recent_items) >= 4:
            start_slice = len(recent_items) - 4
            
        for r_line in recent_items[start_slice:end_slice]:
            print(r_line)
        print()
        
        # 5. Summary Line
        print("──────────────────────────────────────────────────────────────")
        proc_count = 1 if current < total else 0
        print(f"  {CLR_GREEN}✓ Success: {self.success_count}{CLR_RESET}     {CLR_RED}✗ Failed: {self.failed_count}{CLR_RESET}     {CLR_BLUE}⟳ Processing: {proc_count}{CLR_RESET}")
        print("──────────────────────────────────────────────────────────────")
        print()
        sys.stdout.flush()

    def _format_border_line(self, left_content, width=56):
        raw_len = len(re.sub(r'\033\[[0-9;]*m', '', left_content))
        emojis = ["📄", "📅", "📤", "📝", "🗓️", "⟳", "✓", "✗", "○", "⚡", "⚙️"]
        emoji_extra_width = sum(left_content.count(e) for e in emojis)
        padding = width - raw_len - emoji_extra_width
        if padding < 0: padding = 0
        return f"  │ {left_content}" + " " * padding + "│"

def log_step(message, dashboard=None, is_success=False):
    if dashboard:
        dashboard.current_job["activity"] = ("✓ " if is_success else "") + message
        dashboard.render()
    else:
        prefix = "[✓]" if is_success else "[i]"
        print(f"    {prefix} {message}")

def run_fb_scheduled_task(driver, profile_name, post_path, schedule_time=None, preview=False, pre_caption=None, custom_media=None, dashboard=None):
    wait = WebDriverWait(driver, 30)
    item_name = os.path.basename(post_path)
    is_file = os.path.isfile(post_path)
    
    media_files = custom_media if custom_media else get_media_files(post_path)
    if not media_files:
        print(f"    {TAG_WARNING} Skip: Tidak ada media di {item_name}")
        return False

    caption_text = pre_caption if pre_caption else get_caption_text(post_path)

    if dashboard:
        dashboard.current_job["name"] = item_name
        dashboard.current_job["date"] = schedule_time if schedule_time else "🚀 Posting SEKARANG"
        dashboard.current_job["upload"] = "Pending"
        dashboard.current_job["caption"] = "Pending"
        dashboard.current_job["scheduling"] = "Pending"
        dashboard.render()

    # --- CHECK FOR 28 DAYS FUTURE SCHEDULING LIMIT ---
    if schedule_time:
        try:
            sched_dt = datetime.strptime(schedule_time, "%Y-%m-%d %H:%M")
            limit_dt = datetime.now() + timedelta(days=28)
            if sched_dt > limit_dt:
                post_num = (dashboard.current_idx + 1) if dashboard else "?"
                error_msg = f"Postingan ke-{post_num} dibatalkan karena lebih dari 28 hari ke depan."
                update_post_status(post_path, f"Gagal: {error_msg}", 0)
                
                already_shown = False
                if dashboard:
                    already_shown = getattr(dashboard, '_has_shown_limit_warning', False)
                    dashboard._has_shown_limit_warning = True
                    
                if dashboard:
                    dashboard.current_job["upload"] = "Failed"
                    dashboard.current_job["caption"] = "Failed"
                    dashboard.current_job["scheduling"] = "Failed"
                    dashboard.current_job["activity"] = error_msg
                    dashboard.statuses[post_path] = "failed"
                    dashboard.failed_count += 1
                    dashboard.render()
                else:
                    print(f"    {TAG_ERROR} {error_msg}")
                    
                if not already_shown:
                    time.sleep(3)
                return False
        except Exception as ex:
            pass

    # --- PRATINJAU POSTINGAN (Style ala auto_poster_album.py) ---
    if preview:
        print(f"\n{CLR_BOLD}{CLR_WHITE}👀 === PRATINJAU POSTINGAN FB ==={CLR_RESET}")
        print(f"  {CLR_BOLD}📁 Item{CLR_RESET}    : {CLR_CYAN}{item_name}{CLR_RESET}")
        sched_time_str = schedule_time if schedule_time else '🚀 Posting SEKARANG'
        print(f"  {CLR_BOLD}🕒 Jadwal{CLR_RESET}  : {CLR_YELLOW}{sched_time_str}{CLR_RESET}")
        print(f"  {CLR_BOLD}🖼️  Media{CLR_RESET}   : {CLR_GREEN}{len(media_files)} file{CLR_RESET}")
        for i, m in enumerate(media_files[:3]):
            print(f"    {i+1}. {CLR_DIM}{os.path.basename(m)}{CLR_RESET}")
        if len(media_files) > 3:
            print(f"    ... dan {len(media_files)-3} lainnya.")
        print(f"  {CLR_BOLD}📝 Caption{CLR_RESET} :")
        for line in caption_text.splitlines():
            print(f"    {line}")
        print(f"{CLR_BOLD}{CLR_WHITE}================================={CLR_RESET}\n")
        
        # Cek apakah stdin adalah TTY sebelum meminta input
        if sys.stdin.isatty():
            confirm = input(f"\n{TAG_INPUT} Lanjut upload? (y/n, default y): ").lower()
            if confirm == 'n':
                print(f"{TAG_ERROR} Upload dibatalkan oleh pengguna.")
                return False
        else:
            print(f"{TAG_WARNING} Mode non-interaktif, melewati konfirmasi pratinjau.")

    try:
        update_post_status(post_path, "Membuka Facebook...", 10)
        print(f"{TAG_INFO} Memproses {CLR_BOLD}{item_name}{CLR_RESET} -> Jadwal: {CLR_YELLOW}{schedule_time if schedule_time else 'Posting SEKARANG'}{CLR_RESET}")
        if dashboard:
            dashboard.current_job["upload"] = "Membuka Facebook..."
            dashboard.render()
        driver.get("https://www.facebook.com/")
        time.sleep(5)

        # 1. Buka Dialog Post
        update_post_status(post_path, "Membuka dialog posting...", 20)
        post_xpath = "//div[@role='button']//span[contains(text(), 'Apa yang Anda pikirkan')] | //div[@role='button']//span[contains(text(), \"What's on your mind\")]"
        post_btn = wait.until(EC.presence_of_element_located((By.XPATH, post_xpath)))
        try:
            post_btn.click()
        except:
            driver.execute_script("arguments[0].click();", post_btn)
        wait.until(EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']")))
        human_delay(1, 1.5)

        # 2. Upload Media & Caption
        update_post_status(post_path, f"Mengunggah {len(media_files)} media...", 40)
        print(f"    {TAG_INFO} Mengunggah {CLR_GREEN}{len(media_files)}{CLR_RESET} media & Menyuntikkan caption...")
        if dashboard:
            dashboard.current_job["upload"] = "Mengunggah media..."
            dashboard.render()
        driver.execute_script("var t = arguments[0]; var a = document.createElement('textarea'); a.value = t; document.body.appendChild(a); a.select(); document.execCommand('copy'); document.body.removeChild(a);", caption_text)
        
        file_input = driver.find_element(By.XPATH, "//input[@type='file']")
        file_input.send_keys("\n".join(media_files))
        time.sleep(1)
        ActionChains(driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
        
        # 3. Deteksi Progress Upload
        print(f"    {TAG_INFO} Mendeteksi progress upload media...")
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
                            print(f"\r    {TAG_SUCCESS} Uploading: {CLR_GREEN}{percent}%{CLR_RESET}", end="")
                            last_percent = percent
                            if dashboard:
                                dashboard.current_job["upload"] = f"Mengunggah: {percent}% [" + "█" * (percent // 10) + "░" * (10 - (percent // 10)) + "]"
                                dashboard.render()
                        break
                
                # Jika indikator % hilang tapi sebelumnya ada, berarti selesai
                if not found_percent and last_percent >= 0:
                    print(f"\n    {TAG_SUCCESS} Indikator progress hilang, upload selesai.")
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
                        print(f"\n    {TAG_SUCCESS} Tombol navigasi/post terdeteksi aktif, upload selesai.")
                        break
            except: pass
            time.sleep(2)

        # 4. Posting / Penjadwalan
        if dashboard:
            dashboard.current_job["upload"] = "Completed"
            dashboard.current_job["caption"] = "Injected"
            dashboard.current_job["scheduling"] = "Menjadwalkan..." if schedule_time else "Memposting..."
            dashboard.render()
        update_post_status(post_path, "Tahap akhir (Post/Jadwalkan)...", 70)
        log_step("Tahap akhir posting...", dashboard)
        next_btn_xpath = (
            "//div[@role='dialog']//div[@aria-label='Berikutnya'][not(contains(@aria-label, 'Pemirsa'))]"
            "| //div[@role='dialog']//div[@aria-label='Next']"
            "| //div[@role='dialog']//div[@role='button']//span[text()='Berikutnya' or text()='Next']"
        )
        
        try:
            if not schedule_time:
                log_step("Mode: Posting SEKARANG", dashboard)
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
                        log_step("Tombol Kirim/Post diklik.", dashboard, is_success=True)
                        break
                    
                    btns_next = driver.find_elements(By.XPATH, next_btn_xpath)
                    visible_next = [b for b in btns_next if b.is_displayed()]
                    if visible_next:
                        log_step(f"Mengklik tombol 'Berikutnya' (Langkah {i+1})...", dashboard)
                        driver.execute_script("arguments[0].click();", visible_next[-1])
                    else:
                        if i == 3: print(f"    {TAG_ERROR} Tombol Post tidak ditemukan."); return False
            else:
                log_step(f"Mode: Penjadwalan -> {schedule_time}", dashboard)
                next_btn_xpath = (
                    "//div[@role='dialog']//div[@aria-label='Berikutnya'][not(contains(@aria-label, 'Pemirsa'))]"
                    "| //div[@role='dialog']//div[@aria-label='Next']"
                    "| //div[@role='dialog']//div[@role='button']//span[text()='Berikutnya' or text()='Next']"
                )
                opt_xpath = "//div[@role='dialog']//span[contains(text(), 'Opsi penjadwalan')] | //div[@role='dialog']//div[@aria-label='Opsi penjadwalan']"
                
                # Loop untuk menangani tombol 'Berikutnya' (Next) yang muncul berkali-kali sampai menu Opsi penjadwalan ditemukan
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
                        log_step(f"Mengklik tombol 'Berikutnya' (Langkah {i+1})...", dashboard)
                        driver.execute_script("arguments[0].click();", visible_next[-1])
                        time.sleep(3)
                    else:
                        break
                
                if not form_found:
                    log_step("Mencari menu 'Opsi penjadwalan' intensif (60s)...", dashboard)
                    target_opt = WebDriverWait(driver, 60).until(EC.element_to_be_clickable((By.XPATH, opt_xpath)))

                driver.execute_script("arguments[0].click();", target_opt)
                log_step("Menu 'Opsi penjadwalan' terbuka.", dashboard, is_success=True)
                time.sleep(5)

                # --- PENGATURAN OTOMATIS (SPECIFIC TAB SEQUENCE) ---
                log_step(f"Menyiapkan waktu posting: {schedule_time}", dashboard)
                
                dt_obj = datetime.strptime(schedule_time, "%Y-%m-%d %H:%M")
                date_val = dt_obj.strftime("%d/%m/%Y") 
                time_val = dt_obj.strftime("%H:%M")

                actions = ActionChains(driver)
                
                try:
                    # 1. TAB Pertama (Abaikan)
                    log_step("Navigasi TAB 1 (Abaikan)...", dashboard)
                    actions.send_keys(Keys.TAB).perform()
                    time.sleep(1.2)

                    # 2. Navigasi ke kotak Tanggal (TAB 2)
                    log_step("Navigasi TAB 2 (Tanggal)...", dashboard)
                    actions.send_keys(Keys.TAB).perform()
                    time.sleep(1.2)
                    
                    active_el = driver.switch_to.active_element
                    active_el.send_keys(Keys.CONTROL + "a")
                    active_el.send_keys(Keys.BACKSPACE)
                    active_el.send_keys(date_val)
                    time.sleep(0.5)
                    active_el.send_keys(Keys.ENTER)
                    log_step("Tanggal di-ENTER.", dashboard, is_success=True)
                    time.sleep(1.2)

                    # 3. Navigasi ke kotak Waktu (TAB 3)
                    log_step("Navigasi TAB 3 (Waktu)...", dashboard)
                    actions.send_keys(Keys.TAB).perform()
                    time.sleep(1.2)
                    
                    active_el = driver.switch_to.active_element
                    active_el.send_keys(Keys.CONTROL + "a")
                    active_el.send_keys(Keys.BACKSPACE)
                    active_el.send_keys(time_val)
                    time.sleep(0.5)
                    active_el.send_keys(Keys.ENTER)
                    log_step("Jam di-ENTER.", dashboard, is_success=True)
                    time.sleep(1.2)

                    # 4. Navigasi ke tombol Konfirmasi (TAB 4)
                    log_step("Navigasi TAB 4 (Konfirmasi)...", dashboard)
                    actions.send_keys(Keys.TAB).perform()
                    time.sleep(1.5)
                    
                    active_el = driver.switch_to.active_element
                    log_step(f"Menekan ENTER pada: {active_el.text or 'Tombol Biru'}", dashboard)
                    active_el.send_keys(Keys.ENTER)
                    time.sleep(2)

                    # 4. Klik Jadwalkan FINAL
                    log_step("Mengklik tombol 'Jadwalkan' final...", dashboard)
                    final_xpath = (
                        "//div[@role='dialog']//div[@role='button']//span[text()='Jadwalkan' or text()='Schedule' or text()='Posting' or text()='Post' or text()='Kirim']"
                        "| //div[@role='dialog']//div[@aria-label='Jadwalkan' or @aria-label='Schedule' or @aria-label='Posting' or @aria-label='Post']"
                    )
                    try:
                        final_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, final_xpath)))
                        driver.execute_script("arguments[0].click();", final_btn)
                    except:
                        ActionChains(driver).send_keys(Keys.ENTER).perform()
                except Exception as e:
                    log_step(f"Proses klik jadwal selesai/dilewati...", dashboard)

            log_step("Menunggu Facebook memproses & mengeluarkan notifikasi (1-5 detik)...", dashboard)
            time.sleep(3) # Beri jeda 3 detik agar Facebook sempat memunculkan popup
            
            # Deteksi Toast / Popup / Notifikasi "Postingan Anda dijadwalkan" / "Lihat"
            success_detected = False
            start_check = time.time()
            while time.time() - start_check < 20:
                try:
                    # 1. Cari elemen teks toast Facebook "dijadwalkan", "scheduled", "Lihat", "View"
                    toast_els = driver.find_elements(By.XPATH, "//*[contains(text(), 'dijadwalkan') or contains(text(), 'scheduled') or contains(text(), 'Lihat') or contains(text(), 'View') or contains(text(), 'diterbitkan') or contains(text(), 'published')]")
                    if toast_els:
                        log_step("Notifikasi konfirmasi Facebook terdeteksi!", dashboard)
                        success_detected = True
                        break
                    
                    # 2. Cek apakah dialog postingan sudah tertutup (tanda sukses)
                    dialogs = driver.find_elements(By.XPATH, "//div[@role='dialog']")
                    if not dialogs:
                        success_detected = True
                        break
                except:
                    pass
                time.sleep(1)

            if success_detected:
                marker_file = post_path + ".uploadedfb" if is_file else os.path.join(post_path, "uploadedfb.txt")
                with open(marker_file, "w") as f:
                    if schedule_time:
                        f.write(f"Dijadwalkan: {schedule_time}")
                    else:
                        f.write(f"Diposting: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
                
                log_step(f"Postingan BERHASIL {'dijadwalkan' if schedule_time else 'diposting'}.", dashboard, is_success=True)
                update_post_status(post_path, "SELESAI!", 100)
                if dashboard:
                    dashboard.current_job["upload"] = "Completed"
                    dashboard.current_job["caption"] = "Injected"
                    dashboard.current_job["scheduling"] = "Completed"
                    if dashboard.statuses.get(post_path) != "success":
                        dashboard.statuses[post_path] = "success"
                        dashboard.success_count += 1
                    dashboard.render()
                
                status_file = (post_path + ".status") if is_file else os.path.join(post_path, "upload_status.json")
                if os.path.exists(status_file): os.remove(status_file)
                
                try:
                    log_step("Merefresh halaman Facebook...", dashboard)
                    driver.refresh()
                    time.sleep(5)
                except: pass
                
                return True
            # Hapus file status setelah sukses
            status_file = (post_path + ".status") if is_file else os.path.join(post_path, "upload_status.json")
            if os.path.exists(status_file): os.remove(status_file)
            
            # Refresh halaman sebelum posting selanjutnya
            try:
                log_step("Merefresh halaman Facebook...", dashboard)
                driver.refresh()
                time.sleep(5)
            except: pass
            
            return True

        except Exception as e:
            # Jika notifikasi konfirmasi terdeteksi, abaikan exception kecil dan anggap SUKSES!
            if 'success_detected' in locals() and success_detected:
                log_step(f"Postingan BERHASIL dijadwalkan (terdeteksi via notifikasi).", dashboard, is_success=True)
                update_post_status(post_path, "SELESAI!", 100)
                if dashboard:
                    dashboard.current_job["upload"] = "Completed"
                    dashboard.current_job["caption"] = "Injected"
                    dashboard.current_job["scheduling"] = "Completed"
                    if dashboard.statuses.get(post_path) != "success":
                        dashboard.statuses[post_path] = "success"
                        dashboard.success_count += 1
                    dashboard.render()
                marker_file = post_path + ".uploadedfb" if is_file else os.path.join(post_path, "uploadedfb.txt")
                with open(marker_file, "w") as f:
                    f.write(f"Dijadwalkan: {schedule_time}")
                try:
                    driver.refresh()
                    time.sleep(5)
                except: pass
                return True

            update_post_status(post_path, f"Gagal: {str(e)}", 0)
            print(f"    {TAG_ERROR} Gagal: {e}")
            if dashboard:
                dashboard.current_job["upload"] = "Failed" if dashboard.current_job["upload"] != "Completed" else "Completed"
                dashboard.current_job["caption"] = "Failed" if dashboard.current_job["caption"] != "Injected" else "Injected"
                dashboard.current_job["scheduling"] = "Failed"
                dashboard.statuses[post_path] = "failed"
                dashboard.failed_count += 1
                dashboard.render()
            manual_fallback(driver, "Selesaikan manual di VNC.")
            return False

    except Exception as e:
        if 'success_detected' in locals() and success_detected:
            return True
        update_post_status(post_path, f"Error: {str(e)}", 0)
        print(f"    {TAG_ERROR} Error: {e}")
        if dashboard:
            dashboard.current_job["upload"] = "Failed" if dashboard.current_job["upload"] != "Completed" else "Completed"
            dashboard.current_job["caption"] = "Failed" if dashboard.current_job["caption"] != "Injected" else "Injected"
            dashboard.current_job["scheduling"] = "Failed"
            dashboard.statuses[post_path] = "failed"
            dashboard.failed_count += 1
            dashboard.render()
        return False

def run_draft_mode():
    clear_screen()
    print_header("🗓️  KELOLA DRAF TERSIMPAN")
    drafts = load_drafts()
    if not drafts:
        print(f"{TAG_WARNING} Tidak ada draf tersimpan.")
        return

    draft_list = list(drafts.items())
    draft_options = [f"{i+1}. {os.path.basename(path)} (Profil: {data.get('profile', 'Default')})" for i, (path, data) in enumerate(draft_list)] + ["0. Batal"]
    idx = select_menu_option("DAFTAR DRAF TERSIMPAN", draft_options)
    if idx == len(draft_list): # "0. Batal"
        return
    
    sel_path, sel_data = draft_list[idx]
    
    draft_opts = [
        "1. Posting / Jadwalkan Sekarang",
        "2. Hapus Draf",
        "3. Batal"
    ]
    opt_idx = select_menu_option(f"OPSI: {os.path.basename(sel_path)}", draft_opts)
    opt = str(opt_idx + 1)
    
    if opt == '1':
        res = get_datetime_input("Jadwal")
        sched_str = None if res == 'now' else res.strftime("%Y-%m-%d %H:%M")
        
        is_headless = input(f"\n{TAG_INPUT} Gunakan Mode Headless (n VNC)? (y/n, default n): ").lower() == 'y'
        profile = sel_data.get('profile', 'Default')
        os.system('cls' if os.name == 'nt' else 'clear')
        setup_sticky_footer()
        dashboard = UploadDashboard([sel_path], {sel_path: {'schedule_time': sched_str}})
        driver = setup_driver(os.path.join(os.getcwd(), "fb_profiles", profile), headless=is_headless)
        try:
            print_progress_bar(0, 1)
            media_files = sel_data.get('media_files')
            if run_fb_scheduled_task(driver, profile, sel_path, sched_str, pre_caption=sel_data.get('caption'), custom_media=media_files, dashboard=dashboard):
                del drafts[sel_path]
                save_drafts(drafts)
                print_progress_bar(1, 1)
                reset_scroll_region()
                print(f"\n{TAG_SUCCESS} {CLR_BOLD}{CLR_GREEN}DRAF BERHASIL DIPOSTING.{CLR_RESET}")
        finally: driver.quit()
    elif opt == '2':
        del drafts[sel_path]
        save_drafts(drafts)
        print(f"\n{TAG_SUCCESS} Draf berhasil dihapus.")

def run_profile_mode():
    clear_screen()
    print_header("🔄 KELOLA PROFIL BROWSER")
    profile_dir = os.path.join(os.getcwd(), "fb_profiles")
    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir, exist_ok=True)
        
    profiles = sorted([d for d in os.listdir(profile_dir) if os.path.isdir(os.path.join(profile_dir, d))])
    
    if not profiles:
        print(f"{TAG_WARNING} Tidak ada profil browser yang ditemukan.")
        create = input(f"\n{TAG_INPUT} Ingin membuat profil & login akun baru sekarang? (y/n, default y): ").strip().lower()
        if create != 'n':
            import subprocess
            fb_login_script = os.path.join(os.path.dirname(__file__), "fb_login.py")
            subprocess.run([sys.executable, fb_login_script])
        return

    profile_options = [f"{i+1}. {p}" for i, p in enumerate(profiles)] + [f"{len(profiles)+1}. ➕ Tambah / Login Profil Baru", "0. Batal"]
    p_idx = select_menu_option("DAFTAR PROFIL", profile_options)
    
    if p_idx == len(profiles) + 1: # "0. Batal"
        return
    elif p_idx == len(profiles): # "➕ Tambah / Login Profil Baru"
        import subprocess
        fb_login_script = os.path.join(os.path.dirname(__file__), "fb_login.py")
        subprocess.run([sys.executable, fb_login_script])
        return
        
    sel_profile = profiles[p_idx]
    print(f"\n{TAG_INFO} Membuka browser untuk profil '{CLR_BOLD}{sel_profile}{CLR_RESET}'...")
    driver = setup_driver(os.path.join(os.getcwd(), "fb_profiles", sel_profile), headless=False)
    input(f"\n{TAG_WARNING} Tekan ENTER di sini jika sudah selesai mengecek browser untuk menutup...")
    driver.quit()

def run_single_post_mode():
    print("\n🖼️ Mode Postingan Tunggal (WIP)")
    print("Fitur ini akan segera hadir.")
    time.sleep(2)

def main_menu():
    while True:
        clear_screen()
        story_script = os.path.join(os.path.dirname(__file__), "fb_story_scheduled.py")
        story_script_exists = os.path.exists(story_script)
        
        options = [
            "1. 📚 Mode Postingan Album",
            "2. 🗓️  Kelola Draf Tersimpan",
            "3. 🔄 Lanjutkan Upload Part Sisa"
        ]
        
        if story_script_exists:
            options.append("4. 📖 Mode Upload Story Facebook")
            options.append("5. 🔄 Kelola Profil Browser")
        else:
            options.append("4. 🔄 Kelola Profil Browser")
            
        options.append("0. 🚪 Keluar")
        
        choice_idx = select_menu_option("🚀 FACEBOOK AUTO-POSTER TERPADU 🚀", options)
        choice = options[choice_idx].split('.')[0].strip()
        
        if choice == '1': 
            run_album_post_mode()
        elif choice == '2': 
            run_draft_mode()
        elif choice == '3': 
            run_pending_parts_mode()
        elif choice == '4':
            if story_script_exists:
                import subprocess
                subprocess.run([sys.executable, story_script])
            else:
                run_profile_mode()
        elif choice == '5' and story_script_exists:
            run_profile_mode()
        elif choice == '0': 
            break
        
        if choice != '0': input(f"\n{TAG_INPUT} Tekan Enter untuk kembali ke menu utama...")

if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
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

    print_header("FB SMART SCHEDULED UPLOADER (CLI MODE)")
    
    # --- LOGIKA MULTI AKUN (NON-INTERAKTIF / AUTO SCAN) ---
    if args.multi:
        interval_mins = args.interval if args.interval is not None else 30
        is_headless = args.headless
        is_preview = args.preview
        is_web_preview = args.web_preview
        print(f"{TAG_INFO} Memulai mode MULTI-ACCOUNT Auto Scan (Jeda: {interval_mins}m)")
        
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
                    print(f"\n{TAG_SUCCESS} Akun: {CLR_BOLD}{profile}{CLR_RESET} -> Folder: {CLR_CYAN}{os.path.basename(next_post)}{CLR_RESET}")
                    
                    profile_path = os.path.join(os.getcwd(), "fb_profiles", profile)
                    cleanup_profile(profile_path)
                    driver = setup_driver(profile_path, headless=is_headless)
                    try:
                        # Web preview biasanya tidak cocok untuk mode multi-scan, tapi kita support jika flag ada
                        if is_web_preview:
                            item_data_map = {next_post: {'caption': get_caption_text(next_post), 'media_files': get_media_files(next_post), 'schedule_time': None, 'photo_captions': load_photo_captions(next_post)}}
                            pending_items, item_data_map = run_interactive_preview_web([next_post], item_data_map)
                            if not pending_items: continue
                            next_post = pending_items[0]
                            data = item_data_map[next_post]
                            run_fb_scheduled_task(driver, profile, next_post, None, preview=is_preview, pre_caption=data['caption'], custom_media=data['media_files'])
                        else:
                            run_fb_scheduled_task(driver, profile, next_post, None, preview=is_preview)
                    finally:
                        driver.quit()
                    
                    print(f"   {TAG_INFO} Selesai. Menunggu {interval_mins} menit...")
                    time.sleep(interval_mins * 60)
            
            if not found_any:
                sys.stdout.write(f"\r{TAG_INFO} Tidak ada konten di semua akun. Menunggu 5 menit... ")
                sys.stdout.flush()
                time.sleep(300)
        sys.exit()

    profile_dir = os.path.join(os.getcwd(), "fb_profiles")
    profiles = sorted([d for d in os.listdir(profile_dir) if os.path.isdir(os.path.join(profile_dir, d))])
    if not profiles:
        print(f"{TAG_ERROR} Profil kosong.")
        sys.exit()

    if args.profile:
        sel_profile = args.profile
    else:
        print_menu_box("PILIH PROFIL FACEBOOK", [f"{i+1}. {p}" for i, p in enumerate(profiles)])
        try:
            sel_idx = int(input(f"\n{TAG_INPUT} Pilih Profil (1-{len(profiles)}): ").strip()) - 1
            sel_profile = profiles[sel_idx]
        except (ValueError, IndexError):
            print(f"{TAG_ERROR} Pilihan profil tidak valid!")
            sys.exit()

    if args.path:
        parent_folder = args.path
    else:
        parent_folder = input(f"\n{TAG_INPUT} Masukkan Path Folder Utama: ").strip().replace('"', '').replace("'", "")
    
    if not os.path.isdir(parent_folder):
        print(f"{TAG_ERROR} Folder tidak valid!")
        sys.exit()

    # DETEKSI SMART: Sub-folder vs Direct Files
    if any(f.lower().endswith((".mp4", ".jpg", ".png", ".jpeg", ".webp")) for f in os.listdir(parent_folder)):
        pending_items = [parent_folder]
    else:
        items = sorted([os.path.join(parent_folder, f) for f in os.listdir(parent_folder)], key=natural_sort_key)
        pending_items = []
        for item in items:
            if os.path.isdir(item):
                if not os.path.exists(os.path.join(item, "uploadedfb.txt")):
                    pending_items.append(item)
            elif os.path.isfile(item) and item.lower().endswith((".mp4", ".jpg", ".png", ".jpeg", ".webp")):
                if not os.path.exists(item + ".uploadedfb"):
                    pending_items.append(item)

    if not pending_items:
        print(f"\n{TAG_WARNING} Tidak ada konten baru.")
        sys.exit()
    
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
                print(f"{TAG_INFO} Menggunakan urutan Dashboard.")
            except: pass

    if args.limit is not None and args.profile: # Jika via CLI
        limit = args.limit
    else:
        num_post = input(f"\n{TAG_INPUT} Jumlah postingan (Enter = Semua): ").strip()
        limit = int(num_post) if num_post.isdigit() else 0
    
    if not args.profile:
        if input(f"\n{TAG_INPUT} Acak urutan? (y/n, default n): ").lower() == 'y':
            random.shuffle(pending_items)
    
    if limit > 0: pending_items = pending_items[:limit]

    if args.mode:
        is_post_now = (args.mode == 2)
    else:
        print_menu_box("PILIH MODE POSTING", [
            "1. Jadwalkan (Scheduled)",
            "2. Posting Sekarang (Post Now)"
        ])
        mode_choice = input(f"\n{TAG_INPUT} Pilih [1/2, default 1]: ").strip()
        is_post_now = (mode_choice == '2')

    if is_post_now:
        current_time_obj = None
        if args.profile:
            interval_mins = args.interval if args.interval is not None else 0
        else:
            try:
                interval_mins = int(input(f"\n{TAG_INPUT} Jeda antar posting (menit) [Enter=0]: ") or 0)
            except ValueError:
                interval_mins = 0
    else:
        if args.start:
            start_str = args.start
        elif args.profile:
            start_str = "" # Default to 30m if profile given but no start
        else:
            start_str = input(f"\n{TAG_INPUT} Waktu Mulai (YYYY-MM-DD HH:MM) [Enter = 30m lagi]: ").strip()
        
        current_time_obj = datetime.now() + timedelta(minutes=30) if not start_str else datetime.strptime(start_str, "%Y-%m-%d %H:%M")
        
        if args.profile:
            interval_mins = args.interval if args.interval is not None else 60
        else:
            try:
                interval_mins = int(input(f"\n{TAG_INPUT} Jeda antar jadwal (menit): ").strip())
            except ValueError:
                interval_mins = 60

    if args.profile:
        is_headless = args.headless
        is_preview = args.preview
        is_web_preview = args.web_preview
    else:
        is_headless = input(f"\n{TAG_INPUT} Gunakan Mode Headless (n VNC)? (y/n, default n): ").lower() == 'y'
        print_menu_box("PILIHAN PRATINJAU", [
            "1. Tanpa Pratinjau",
            "2. Pratinjau Terminal (Ringkas)",
            "3. Pratinjau Web Interaktif (Full - Bisa Edit/Urut)"
        ])
        preview_choice = input(f"\n{TAG_INPUT} Pilih [1/2/3, default 1]: ").strip()
        is_preview = (preview_choice == '2')
        is_web_preview = (preview_choice == '3')

    # --- TAHAP PREVIEW WEB (JIKA DIPILIH) ---
    item_data_map = {}
    temp_time = current_time_obj
    
    # Custom mapping for target dates
    target_dates_map = {
        "aku-yang-orangnyaa-gak-enakan-be-like": "2026-08-18 18:55",
        "ya-maap-mungkin-itu-si-martin-malaikat-magang-lagi-gak-fokus": "2026-08-22 18:55",
        "anak-kesayangan-berulah": "2026-08-23 18:55",
        "kegagalan-di-bengkel": "2026-08-26 18:55",
        "itu-kenapa-sih": "2026-09-04 18:55",
        "orang-yang-suka-dengan-sepur": "2026-09-06 18:55",
        "momen-lucu-saat-di-wahana-taman-bermain": "2026-09-09 18:55",
        "namanya-juga-cowok-sih": "2026-09-11 18:55",
        "yakin-dah-itu-pasti-banteng-betina": "2026-09-12 18:55"
    }

    for p in pending_items:
        item_name = os.path.basename(p)
        if item_name in target_dates_map:
            sched_str = target_dates_map[item_name]
        else:
            sched_str = temp_time.strftime("%Y-%m-%d %H:%M") if temp_time else None
            
        item_data_map[p] = {
            'caption': get_caption_text(p),
            'media_files': get_media_files(p),
            'schedule_time': sched_str,
            'photo_captions': load_photo_captions(p)
        }
        if temp_time: temp_time += timedelta(minutes=interval_mins)

    if is_web_preview:
        pending_items, item_data_map = run_interactive_preview_web(pending_items, item_data_map)
        if not pending_items:
            print(f"{TAG_ERROR} Semua postingan dibatalkan. Keluar.")
            sys.exit()

    if args.profile and pending_items:
        update_post_status(pending_items[0], "Inisialisasi bot...", 5)

    setup_sticky_footer()
    dashboard = UploadDashboard(pending_items, item_data_map)
    driver = setup_driver(os.path.join(os.getcwd(), "fb_profiles", sel_profile), headless=is_headless)
    try:
        for i, item in enumerate(pending_items):
            dashboard.current_idx = i
            print_progress_bar(i, len(pending_items))
            update_post_status(item, "Browser siap, memulai...", 8)
            data = item_data_map.get(item, {})
            sched_str = data.get('schedule_time')
            caption = data.get('caption')
            media_files = data.get('media_files', [])
            
            if run_fb_scheduled_task(driver, sel_profile, item, sched_str, preview=is_preview, pre_caption=caption, custom_media=media_files, dashboard=dashboard):
                # Jeda antar posting jika bukan terjadwal
                if not sched_str and interval_mins > 0 and item != pending_items[-1]:
                    print(f"   {TAG_INFO} Menunggu {interval_mins} menit sebelum posting berikutnya...")
                    time.sleep(interval_mins * 60)
            else:
                if input(f"\n{TAG_INPUT} Lanjut? (y/n, default y): ").lower() == 'n': break
        
        print_progress_bar(len(pending_items), len(pending_items))
        reset_scroll_region()
        print(f"\n{TAG_SUCCESS} {CLR_BOLD}{CLR_GREEN}PROSES CLI SELESAI.{CLR_RESET}")
    finally: driver.quit()
