import os
import json
import requests
import time
import itertools
import threading
import random
import html
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Set, List, Dict, Any, Optional, Union
import webbrowser
import base64
import http.server
import socketserver
import shutil
from functools import partial

# === KONFIGURASI & KONSTANTA ===
APP_ID = '711789318597819'
APP_SECRET = 'dca6d9124c712e505c18a31153e61475'
BASE_DIR = Path(__file__).resolve().parent
UPLOADED_ALBUMS_LOG = BASE_DIR / "uploaded_albums.txt"
DRAFT_POSTS_LOG = BASE_DIR / "draft_posts.json"
PENDING_FILE = BASE_DIR / "pending_parts.json"
TOKENS_FILE = BASE_DIR / "tokens.json"
GRAPH_URL = "https://graph.facebook.com/v19.0"
MIN_SCHEDULE_TIME = 600  # 10 menit
MAX_SCHEDULE_TIME = 75 * 24 * 60 * 60  # 75 hari
error_log = []

# --- FUNGSI-FUNGSI BANTUAN ---

def clear_screen():
    """Membersihkan layar terminal."""
    os.system('cls' if os.name == 'nt' else 'clear')

def log_message(message: str, is_error: bool = False):
    """Mencetak pesan ke konsol dengan awalan emoji."""
    prefix = "❌" if is_error else "✅"
    print(f"{prefix} {message}")

def log_error(message):
    """Mencatat pesan error ke variabel global dan menampilkannya."""
    log_message(message, is_error=True)
    error_log.append(message)

def animate_spinner(status_text, stop_event):
    """Menampilkan animasi spinner di terminal."""
    for c in itertools.cycle(['|', '/', '-', '\\']):
        if stop_event.is_set():
            break
        print(f'\r{status_text} {c}  ', end='', flush=True)
    print(f'\r{" " * (len(status_text) + 5)}\r', end='', flush=True)

# --- FUNGSI MANAJEMEN TOKEN ---

def load_tokens():
    if not os.path.exists(TOKENS_FILE):
        return {}
    try:
        with open(TOKENS_FILE, 'r') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        log_error(f"Gagal memuat atau file token rusak ({e}).")
        return {}

def save_tokens(tokens):
    with open(TOKENS_FILE, 'w') as f:
        json.dump(tokens, f, indent=2)

def is_token_old(timestamp_str):
    try:
        if not isinstance(timestamp_str, str):
            return True
        last_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return True
    
    age = datetime.now(timezone.utc) - last_time
    return age > timedelta(days=60)

def debug_token(token):
    url = 'https://graph.facebook.com/debug_token'
    params = {'input_token': token, 'access_token': f'{APP_ID}|{APP_SECRET}'}
    r = requests.get(url, params=params).json()
    return r.get('data', {})

def refresh_user_token(short_lived_token):
    url = 'https://graph.facebook.com/v23.0/oauth/access_token'
    params = {
        'grant_type': 'fb_exchange_token',
        'client_id': APP_ID,
        'client_secret': APP_SECRET,
        'fb_exchange_token': short_lived_token,
    }
    r = requests.get(url, params=params).json()
    return r.get('access_token')

def get_page_tokens(long_lived_user_token):
    url = 'https://graph.facebook.com/v23.0/me/accounts'
    params = {'access_token': long_lived_user_token}
    r = requests.get(url, params=params).json()
    return r.get('data', [])

def check_and_refresh_tokens():
    tokens = load_tokens()
    updated = False
    
    for page_id, data in list(tokens.items()):
        token = data.get('access_token')
        timestamp = data.get('timestamp')

        if is_token_old(timestamp):
            print(f'⚠️ Token untuk Page {page_id} sudah lebih dari 60 hari, mencoba refresh...')
            info = debug_token(token)
            if not info.get('is_valid'):
                print(f'❌ Token Page {page_id} tidak valid, dihapus.')
                tokens.pop(page_id, None)
                updated = True
                continue

        if data.get('type') == 'user':
            long_token = refresh_user_token(token)
            if long_token:
                pages = get_page_tokens(long_token)
                for p in pages:
                    tokens[p['id']] = {
                        'access_token': p['access_token'],
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'type': 'page'
                    }
                print('✅ Token user berhasil direfresh & Page token diperbarui.')
                updated = True
            else:
                print('❌ Gagal refresh token user, hapus dari list.')
                tokens.pop(page_id, None)
                updated = True

    if updated:
        save_tokens(tokens)
        print('💾 tokens.json sudah diperbarui.')

    return tokens

def get_country_codes() -> List[str]:
    """Meminta pengguna memasukkan kode negara untuk pembatasan."""
    print("\n🔒 Masukkan Kode Negara untuk mengunci jangkauan postingan (opsional).")
    print("   - Gunakan kode negara ISO 3166-1 alpha-2 (contoh: ID, US, MY, SG).")
    print("   - Pisahkan beberapa negara dengan koma (contoh: ID,MY).")
    print("   - Kosongkan jika ingin postingan bersifat publik (tanpa batasan).")
    
    countries_input = input("Kode Negara: ").strip().upper()
    if not countries_input:
        return []
    
    return [code.strip() for code in countries_input.split(',')]

# --- KELAS API FACEBOOK ---

class FacebookAPI:
    def __init__(self):
        self.user_token = None
        self.page_token = None
        self.page_id = None

    def set_user_token(self, user_token):
        self.user_token = user_token

    def get_managed_pages(self):
        if not self.user_token:
            log_error("User Access Token belum diatur.")
            return None
        stop_event = threading.Event()
        animation_thread = threading.Thread(target=animate_spinner, args=("Mendapatkan daftar halaman...", stop_event))
        animation_thread.start()
        
        endpoint = f"{GRAPH_URL}/me/accounts"
        params = {'access_token': self.user_token, 'limit': 100, 'fields': 'id,name,access_token,picture'}
        try:
            response = requests.get(endpoint, params=params)
            response.raise_for_status()
            stop_event.set()
            animation_thread.join()
            return response.json().get('data', [])
        except requests.exceptions.RequestException as e:
            stop_event.set()
            animation_thread.join()
            err_data = e.response.json() if e.response else {}
            error_message = err_data.get("error", {}).get("message", str(e))
            log_error(f"Gagal mendapatkan halaman: {error_message}")
            if "expired" in error_message:
                log_error("-> Token Anda kemungkinan besar sudah tidak valid atau kedaluwarsa.")
            return None

    def set_page(self, page_id, page_access_token):
        self.page_id = page_id
        self.page_token = page_access_token

    def upload_photo(self, image_path: Path, caption: str = "", current: int = 0, total: int = 0) -> Optional[str]:
        """Mengunggah satu foto sebagai unpublished, dengan caption, dan mengembalikan photo ID."""
        if total > 0 and current > 0:
            progress = current / total
            bar_length = 20
            filled_len = int(bar_length * progress)
            bar = '█' * filled_len + '-' * (bar_length - filled_len)
            print(f'\r    "{image_path.name}" ({current}/{total}) [{bar}] {progress*100:.1f}%  ', end='', flush=True)
        else:
            # Fallback jika total tidak disediakan
            print(f"    - Mengunggah foto: {image_path.name}...")

        endpoint = f"{GRAPH_URL}/{self.page_id}/photos"
        params = {
            'access_token': self.page_token,
            'published': False
        }
        if caption:
            params['caption'] = caption
            
        try:
            with image_path.open('rb') as f:
                files = {'source': f}
                response = requests.post(endpoint, params=params, files=files, timeout=300)
                response.raise_for_status()
            
            if total > 0 and current == total:
                print()  # Baris baru di akhir progress

            return response.json().get('id')
        except requests.exceptions.RequestException as e:
            if total > 0:
                print()  # Baris baru jika ada error juga
            error_msg = f"Unggah gagal untuk {image_path.name}: {e}"
            try:
                error_details = e.response.json()['error']['message']
                error_msg += f" ({error_details})"
            except:
                pass
            log_error(error_msg)
            return None

    def _post_album(self, caption: str, photo_ids: List[str], schedule_time: Optional[int] = None, published: bool = True, countries: Optional[List[str]] = None) -> Optional[str]:
        """Fungsi dasar untuk mempublikasikan, menjadwalkan, atau membuat draf post album."""
        action_text = "Mempublikasikan"
        if not published and schedule_time:
            action_text = "Menjadwalkan"
        elif not published:
            action_text = "Menyimpan draf"

        print(f"  - {action_text} album...")
        
        endpoint = f"{GRAPH_URL}/{self.page_id}/feed"
        attached_media = [f'{{"media_fbid": "{pid}"}}' for pid in photo_ids]
        
        params = {
            'access_token': self.page_token,
            'message': caption,
            'attached_media': f'[{ ", ".join(attached_media) }]',
            'published': published
        }
        if schedule_time:
            params['scheduled_publish_time'] = schedule_time
        
        if countries:
            targeting = {'geo_locations': {'countries': countries}}
            params['targeting'] = json.dumps(targeting)
            print(f"    - 🔒 Postingan ini dikunci untuk negara: {', '.join(countries)}")

        try:
            response = requests.post(endpoint, data=params, timeout=120)
            response.raise_for_status()
            return response.json().get('id')
        except requests.exceptions.RequestException as e:
            error_msg = f"{action_text} album gagal: {e}"
            try:
                error_details = e.response.json()['error']['message']
                error_msg += f" ({error_details})"
            except:
                pass
            log_error(error_msg)
            return None

    def schedule_album_post(self, caption: str, photo_ids: List[str], unix_time: int, countries: Optional[List[str]] = None) -> Optional[str]:
        return self._post_album(caption, photo_ids, schedule_time=unix_time, published=False, countries=countries)

    def publish_album_post(self, caption: str, photo_ids: List[str], countries: Optional[List[str]] = None) -> Optional[str]:
        return self._post_album(caption, photo_ids, published=True, countries=countries)

    def create_draft_album_post(self, caption: str, photo_ids: List[str], countries: Optional[List[str]] = None) -> Optional[str]:
        return self._post_album(caption, photo_ids, published=False, countries=countries)

    def schedule_existing_post(self, post_id: str, unix_time: int) -> bool:
        """Memperbarui post yang ada (draf) untuk dijadwalkan."""
        print(f"  - Menjadwalkan draf post ID: {post_id}...")
        endpoint = f"{GRAPH_URL}/{post_id}"
        params = {
            'access_token': self.page_token,
            'is_published': True,
            'scheduled_publish_time': unix_time
        }
        try:
            response = requests.post(endpoint, data=params, timeout=120)
            response.raise_for_status()
            return response.json().get('success', False)
        except requests.exceptions.RequestException as e:
            error_msg = f"Gagal menjadwalkan draf {post_id}: {e}"
            try:
                error_details = e.response.json()['error']['message']
                error_msg += f" ({error_details})"
            except:
                pass
            log_error(error_msg)
            return False

    def publish_existing_post(self, post_id: str) -> bool:
        """Memperbarui post yang ada (draf) untuk dipublikasikan segera."""
        print(f"  - Menerbitkan draf post ID: {post_id} sekarang...")
        endpoint = f"{GRAPH_URL}/{post_id}"
        params = {
            'access_token': self.page_token,
            'is_published': True
        }
        try:
            response = requests.post(endpoint, data=params, timeout=120)
            response.raise_for_status()
            return response.json().get('success', False)
        except requests.exceptions.RequestException as e:
            error_msg = f"Gagal menerbitkan draf {post_id}: {e}"
            try:
                error_details = e.response.json()['error']['message']
                error_msg += f" ({error_details})"
            except:
                pass
            log_error(error_msg)
            return False

    def delete_post(self, post_id: str) -> bool:
        """Menghapus post berdasarkan ID."""
        print(f"  - Menghapus post ID: {post_id}...")
        endpoint = f"{GRAPH_URL}/{post_id}"
        params = {
            'access_token': self.page_token
        }
        try:
            response = requests.delete(endpoint, params=params, timeout=120)
            response.raise_for_status()
            return response.json().get('success', False)
        except requests.exceptions.RequestException as e:
            error_msg = f"Gagal menghapus post {post_id}: {e}"
            try:
                err_json = e.response.json()['error']
                error_details = err_json.get('message', '')
                error_code = err_json.get('code')
                error_msg += f" ({error_details})"

                if error_code == 100 or "does not exist" in error_details or "Unsupported delete request" in error_details:
                    log_message(f"Info: Post {post_id} tidak ditemukan di Facebook (kemungkinan sudah dihapus). Tetap dihapus dari log lokal.", is_error=False)
                    return True

            except (KeyError, json.JSONDecodeError):
                pass
            
            log_error(error_msg)
            return False

# --- ALUR REFRESH TOKEN (Sama seperti skrip tunggal) ---

def refresh_page_list_flow():
    pages = None
    print("\n" + "="*50)
    print("--- Memperbarui Daftar Halaman Facebook ---")
    print("1. Masukkan User Access Token")
    print("2. Tempel (Paste) seluruh output dari Graph API Explorer")
    print("="*50)
    choice = input("Pilih metode (1/2): ").strip()
    if choice == '1':
        user_token = input("Masukkan User Access Token Anda: ").strip()
        api = FacebookAPI()
        api.set_user_token(user_token)
        pages = api.get_managed_pages()
    elif choice == '2':
        print("\n✅ Tempel seluruh teks dari Facebook, ketik 'SELESAI' & Enter jika sudah.")
        input_lines = []
        while True:
            line = input()
            if line.strip().upper() == 'SELESAI':
                break
            input_lines.append(line)
        full_pasted_text = "\n".join(input_lines)
        try:
            response_header = "==== Response"
            start_index = full_pasted_text.find(response_header)
            if start_index == -1:
                log_error("Gagal: Header '==== Response' tidak ditemukan.")
                return None
            json_start_index = full_pasted_text.find('{', start_index)
            json_end_index = full_pasted_text.rfind('}')
            if json_start_index == -1 or json_end_index == -1 or json_end_index < json_start_index:
                log_error("Gagal: Blok JSON '{...}' tidak ditemukan.")
                return None
            json_string_to_parse = full_pasted_text[json_start_index : json_end_index + 1]
            response_data = json.loads(json_string_to_parse)
            pages = response_data.get('data')
            if pages is None:
                log_error("Gagal: Kunci 'data' tidak ada dalam JSON.")
                return None
        except json.JSONDecodeError:
            log_error("Gagal: Format JSON tidak valid.")
            return None
    else:
        log_error("Pilihan tidak valid.")
        return None
    if pages:
        new_pages_data = {}
        for page in pages:
            if all(k in page for k in ['id', 'name', 'access_token']):
                page['timestamp'] = datetime.now().isoformat()
                new_pages_data[page['id']] = page
            else:
                log_error(f"Melewatkan entri data tidak lengkap: {page.get('name', 'Tanpa Nama')}")
        if not new_pages_data:
            log_error("Tidak ada data halaman valid yang diproses.")
            return None
        save_tokens(new_pages_data)
        print(f"\n✅ Berhasil! Ditemukan dan disimpan {len(new_pages_data)} halaman.")
        return new_pages_data
    else:
        log_error("Gagal mendapatkan atau memproses daftar halaman.")
        return None

# --- FUNGSI-FUNGSI BANTUAN LAINNYA ---

def load_uploaded_log(album_folder_path: Path) -> Set[str]:
    """Membaca dan menggabungkan log dari folder album dan folder skrip."""
    script_dir_log = BASE_DIR / "uploaded_albums.txt"
    target_dir = album_folder_path.parent if album_folder_path.is_file() else album_folder_path
    album_dir_log = target_dir / "uploaded_albums.txt"
    
    combined_log = set()

    if script_dir_log.exists():
        try:
            with script_dir_log.open("r") as f:
                combined_log.update(line.strip() for line in f if line.strip())
        except IOError:
            log_message(f"Gagal membaca log di folder skrip.", is_error=True)

    if album_dir_log.exists():
        try:
            with album_dir_log.open("r") as f:
                combined_log.update(line.strip() for line in f if line.strip())
        except IOError:
            log_message(f"Gagal membaca log di folder album.", is_error=True)
    
    if combined_log:
        print(f"ℹ️  Total {len(combined_log)} album unik ditemukan di riwayat gabungan.")

    return combined_log

def save_to_uploaded_log(album_name: str, album_folder_path: Optional[Path] = None):
    """Menyimpan log ke folder album (jika ada) dan folder skrip."""
    log_paths = [BASE_DIR / "uploaded_albums.txt"]
    if album_folder_path:
        target_dir = album_folder_path.parent if album_folder_path.is_file() else album_folder_path
        log_paths.append(target_dir / "uploaded_albums.txt")

    print(f"  - Menyimpan riwayat '{album_name}' ke {len(log_paths)} lokasi...")
    for path in log_paths:
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(album_name + "\n")
        except IOError as e:
            log_error(f"GAGAL menyimpan riwayat ke {path}: {e}")

def load_draft_log() -> Dict[str, Dict]:
    if not DRAFT_POSTS_LOG.exists():
        return {}
    try:
        with DRAFT_POSTS_LOG.open("r") as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return {}

def save_to_draft_log(album_name: str, post_id: str, album_path: Path):
    drafts = load_draft_log()
    drafts[post_id] = {
        "album_name": album_name,
        "album_path": str(album_path),
        "saved_at": datetime.now().isoformat()
    }
    try:
        with DRAFT_POSTS_LOG.open("w") as f:
            json.dump(drafts, f, indent=4)
    except IOError as e:
        log_message(f"Gagal menyimpan ke file log draf: {e}", is_error=True)

def remove_from_draft_log(post_id: str):
    drafts = load_draft_log()
    if post_id in drafts:
        del drafts[post_id]
        try:
            with DRAFT_POSTS_LOG.open("w") as f:
                json.dump(drafts, f, indent=4)
        except IOError as e:
            log_message(f"Gagal memperbarui file log draf: {e}", is_error=True)

def load_pending_parts():
    if not PENDING_FILE.exists():
        return {}
    try:
        with PENDING_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return {}

def save_pending_parts(data):
    try:
        with PENDING_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except IOError as e:
        log_message(f"Gagal menyimpan pending parts: {e}", is_error=True)

def ask_strategy_choice():
    print("\nPilih penjadwalan:")
    print("1. Per jam")
    print("2. Per hari")
    print("3. Manual per album")
    print("4. Langsung publish")
    print("5. Simpan sebagai draf")
    choice = input("Pilihan: ").strip()
    return choice

def post_with_strategy(api, strategy, caption, photo_ids, precalculated_time: Optional[datetime] = None, countries: Optional[List[str]] = None):
    if not photo_ids:
        log_error("❌ Tidak ada photo_id untuk diposting.")
        return None

    strategy = str(strategy).strip()

    if strategy == '4':
        print("🔔 Langsung publish sekarang...")
        return api.publish_album_post(caption, photo_ids, countries=countries)

    if strategy == '5':
        print("🔔 Simpan sebagai draf...")
        return api.create_draft_album_post(caption, photo_ids, countries=countries)

    if strategy in ['1', '2', '3']:
        schedule_time_obj = None
        
        if precalculated_time:
            schedule_time_obj = precalculated_time
        else:
            print("🔔 Mode: Manual per album → masukkan waktu posting ini")
            schedule_time_obj = get_datetime_input("⏰ Masukkan waktu jadwal posting (YYYY-MM-DD HH:MM)")

        if not schedule_time_obj:
            log_error("Waktu jadwal tidak valid, proses dibatalkan.", is_error=True)
            return None

        # Tambahkan variasi waktu acak 1-5 menit
        acak_menit = random.randint(1, 5)
        schedule_time_obj += timedelta(minutes=acak_menit)
        print(f"🎲 Waktu diacak: ditambah {acak_menit} menit.")

        unix_time = int(schedule_time_obj.timestamp())
        
        current_timestamp = time.time()
        if unix_time < current_timestamp + MIN_SCHEDULE_TIME:
            print(f"⚠️ Jadwal untuk {schedule_time_obj.strftime('%Y-%m-%d %H:%M')} terlalu cepat (kurang dari 10 menit dari sekarang).")
            log_error(f"Penjadwalan untuk album ini dibatalkan karena waktunya tidak valid.")
            return None
        elif unix_time > current_timestamp + MAX_SCHEDULE_TIME:
            log_error(f"Jadwal untuk album ini ({schedule_time_obj.strftime('%Y-%m-%d %H:%M')}) terlalu jauh (lebih dari 75 hari). Dibatalkan.")
            return None

        print(f"⏱  Akan dijadwalkan pada: {schedule_time_obj.strftime('%Y-%m-%d %H:%M')}")
        return api.schedule_album_post(caption, photo_ids, unix_time, countries=countries)

    log_message("❌ Strategi tidak dikenali, tidak ada tindakan yang diambil.", is_error=True)
    return None

def get_datetime_input(prompt: str) -> Union[datetime, str]:
    """Meminta input waktu dari pengguna. Bisa mengembalikan datetime atau 'now'."""
    while True:
        val = input(f"⏰ {prompt} (format: YYYY-MM-DD HH:MM atau ketik 'now'/'y'): ").strip().lower()
        if val in ['now', 'sekarang', 'y']:
            return 'now'
        try:
            dt_object = datetime.strptime(val, "%Y-%m-%d %H:%M")
            current_timestamp = time.time()
            if dt_object.timestamp() < current_timestamp + MIN_SCHEDULE_TIME:
                print("⚠️ Jadwal harus minimal 10 menit dari sekarang.")
            elif dt_object.timestamp() > current_timestamp + MAX_SCHEDULE_TIME:
                print("⚠️ Jadwal tidak boleh lebih dari 75 hari dari sekarang.")
            else:
                return dt_object
        except ValueError:
            print("❌ Format salah. Mohon ulangi.")

def generate_main_caption(album_dir: Path) -> str:
    """Membangun caption utama album dari post_meta.json."""
    if album_dir.is_file():
        # Ambil nama file tanpa ekstensi dan ganti _ dengan spasi
        return album_dir.stem.replace('_', ' ').strip()

    post_meta_path = album_dir / "post_meta.json"
    if not post_meta_path.exists():
        # Ganti _ dengan spasi untuk nama folder
        return album_dir.name.replace('_', ' ').strip()

    try:
        with post_meta_path.open("r", encoding="utf-8") as f:
            meta = json.load(f)

        parts = []
        if title := meta.get("post_title"):
            parts.append(title)
        if summary := meta.get("summary"):
            parts.append(f"\n\n{summary}")
        if cta := meta.get("cta"):
            parts.append(f"\n\n{cta}")
        if hashtags := meta.get("hashtags"):
            if isinstance(hashtags, list):
                formatted_tags = [f"#{tag.lstrip('#').strip()}" for tag in hashtags]
                parts.append(f"\n\n{' '.join(formatted_tags)}")
        
        return "".join(parts).strip()
    except (json.JSONDecodeError, IOError) as e:
        log_error(f"Gagal membaca post_meta.json di {album_dir.name}: {e}. Menggunakan nama folder.")
        return album_dir.name

def load_photo_captions(album_dir: Path) -> Dict[str, Dict[str, str]]:
    """Memuat 'description' dan 'description2' dari content_manifest.json."""
    captions_data = {}
    if album_dir.is_file():
        return captions_data
    manifest_path = album_dir / "content_manifest.json"
    if not manifest_path.exists():
        return captions_data

    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            manifest = json.load(f)
        
        for filename, data in manifest.items():
            captions_data[filename] = {
                "description": data.get("description", "").strip(),
                "description2": data.get("description2", "").strip()
            }
        return captions_data
    except (json.JSONDecodeError, IOError) as e:
        log_error(f"Gagal membaca content_manifest.json di {album_dir.name}: {e}.")
        return {}

# --- FUNGSI PREVIEW INTERAKTIF ---

class AlbumPreviewState:
    def __init__(self, pending_albums, album_captions, album_images_map, all_photo_captions, product_link, templates=None):
        self.pending_albums = pending_albums
        self.album_captions = album_captions
        self.album_images_map = album_images_map
        self.all_photo_captions = all_photo_captions
        self.product_link = product_link
        self.templates = templates or []
        self.lock = threading.Lock()
        self.server_should_shutdown = False

class AlbumPreviewRequestHandler(http.server.BaseHTTPRequestHandler):
    def __init__(self, state, *args, **kwargs):
        self.state = state
        http.server.BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            html = self.generate_html()
            self.wfile.write(html.encode('utf-8'))
        else:
            self.send_error(404, "File not found")

    def do_POST(self):
        try:
            if self.path == '/shutdown':
                self.send_response(200, "OK")
                self.end_headers()
                self.state.server_should_shutdown = True
                return

            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error(400, "Bad Request: Missing POST data")
                return
            
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)

            with self.state.lock:
                if self.path == '/edit_caption':
                    self.state.album_captions[data['album_name']] = data['caption']
                elif self.path == '/delete_album':
                    album_name = data['album_name']
                    self.state.pending_albums[:] = [a for a in self.state.pending_albums if a.name != album_name]
                elif self.path == '/delete_photo':
                    album_name = data['album_name']
                    photo_name = data['photo_name']
                    if album_name in self.state.album_images_map:
                        self.state.album_images_map[album_name][:] = [p for p in self.state.album_images_map[album_name] if p.name != photo_name]
                elif self.path == '/reorder_photos':
                    album_name = data['album_name']
                    new_order_filenames = data['photo_order']
                    if album_name in self.state.album_images_map:
                        current_photos = self.state.album_images_map[album_name]
                        photo_map = {p.name: p for p in current_photos}
                        new_photo_list = [photo_map[name] for name in new_order_filenames if name in photo_map]
                        self.state.album_images_map[album_name][:] = new_photo_list
                elif self.path == '/add_photo':
                    album_name = data['album_name']
                    photo_name = data['photo_name']
                    photo_data = data['photo_data']
                    
                    album_dir = next((alb for alb in self.state.pending_albums if alb.name == album_name), None)
                    if not album_dir:
                        self.send_error(404, "Album not found")
                        return

                    try:
                        header, encoded = photo_data.split(",", 1)
                        file_data = base64.b64decode(encoded)
                        target_dir = album_dir.parent if album_dir.is_file() else album_dir
                        new_photo_path = target_dir / photo_name
                        with open(new_photo_path, "wb") as f:
                            f.write(file_data)
                        
                        self.state.album_images_map[album_name].append(new_photo_path)
                        if album_name not in self.state.all_photo_captions:
                            self.state.all_photo_captions[album_name] = {}
                        self.state.all_photo_captions[album_name][photo_name] = {'description': '', 'description2': ''}

                    except Exception as e:
                        log_error(f"Failed to save new photo: {e}")
                        self.send_error(500, "Failed to save photo")
                        return

                elif self.path == '/edit_photo_caption':
                    album_name = data['album_name']
                    photo_name = data['photo_name']
                    new_caption = data['caption']
                    if album_name in self.state.all_photo_captions and photo_name in self.state.all_photo_captions[album_name]:
                        self.state.all_photo_captions[album_name][photo_name]['description2'] = new_caption
                    else:
                        self.state.all_photo_captions[album_name] = {}
                        self.state.all_photo_captions[album_name][photo_name] = {'description': '', 'description2': new_caption}
                elif self.path == '/add_connector':
                    album_name = data['album_name']
                    template_name = data['template_name']
                    
                    template_path = next((p for p in self.state.templates if p.name == template_name), None)
                    album_dir = next((alb for alb in self.state.pending_albums if alb.name == album_name), None)
                    
                    if template_path and album_dir:
                        try:
                            timestamp = int(time.time() * 1000)
                            ext = template_path.suffix
                            new_filename = f"connector_{timestamp}{ext}"
                            
                            # Ensure paths are absolute
                            abs_template_path = template_path.resolve()
                            abs_album_dir = album_dir.resolve()
                            target_dir = abs_album_dir.parent if abs_album_dir.is_file() else abs_album_dir
                            new_path = target_dir / new_filename
                            
                            shutil.copyfile(abs_template_path, new_path)
                            
                            # Update state with the original album_dir relative logic (or just path)
                            # to be consistent with how other photos are stored in the list.
                            # But since we resolved it, let's just append the new path object.
                            self.state.album_images_map[album_name].append(new_path)
                            
                            if album_name not in self.state.all_photo_captions:
                                self.state.all_photo_captions[album_name] = {}
                            self.state.all_photo_captions[album_name][new_filename] = {'description': '', 'description2': ''}
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                            log_error(f"Failed to add connector. Src: {template_path}, Dst: {album_dir}. Error: {e}")
                            self.send_error(500, f"Failed to add connector: {e}")
                            return
                    else:
                        self.send_error(404, "Template or Album not found")
                        return
                else:
                    self.send_error(404, "Endpoint not found")
                    return
            
            self.send_response(200, "OK")
            self.end_headers()

        except Exception as e:
            log_error(f"Server error: {e}")
            self.send_error(500, "Server Error")

    def generate_html(self):
        with self.state.lock:
            albums = list(self.state.pending_albums)
            all_photo_captions = self.state.all_photo_captions
        
        albums_html = ""
        for album_dir in albums:
            album_name = album_dir.name
            caption = self.state.album_captions.get(album_name, album_name)
            images = self.state.album_images_map.get(album_name, [])
            photo_captions_for_album = all_photo_captions.get(album_name, {})
            
            images_html = ""
            for img_path in images:
                try:
                    with open(img_path, "rb") as f:
                        encoded_string = base64.b64encode(f.read()).decode("utf-8")
                    ext = img_path.suffix.lower()
                    mime_type = f"image/{'jpeg' if ext == '.jpg' else ext[1:]}"
                    image_uri = f"data:{mime_type};base64,{encoded_string}"
                    
                    caption_data = photo_captions_for_album.get(img_path.name, {'description': '', 'description2': ''})
                    desc2 = caption_data.get('description2', '')
                    desc1 = caption_data.get('description', '')

                    photo_card_content = ''
                    if desc2:
                        photo_card_content = f'''
                            <p class="photo-description" id="caption-{album_name}-{img_path.name}">{html.escape(desc2)}</p>
                            <button class="edit-button" onclick="togglePhotoEdit(this, \'{album_name}\', \'{img_path.name}\')">Edit Caption</button>
                        '''
                    else:
                        photo_card_content = f'''
                            <div class="caption-choice-container" id="choice-container-{album_name}-{img_path.name}">
                                <p class="choice-prompt">'description2' kosong. Pilih aksi:</p>
                                <select class="caption-choice-select" onchange="handleCaptionChoice(this, \'{album_name}\', \'{img_path.name}\', \'{html.escape(desc1)}\')">
                                    <option value="use_desc">Gunakan 'description'</option>
                                    <option value="empty" selected>Biarkan Kosong</option>
                                </select>
                                <p class="fallback-preview"><b>Preview 'description':</b> {html.escape(desc1)}</p>
                            </div>
                            <p class="photo-description" id="caption-{album_name}-{img_path.name}" style="display:none;"></p>
                            <button class="edit-button" onclick="togglePhotoEdit(this, \'{album_name}\', \'{img_path.name}\')" style="display:none;">Edit Caption</button>
                        '''

                    images_html += f'''
                    <div class="photo-card" id="photo-{album_name}-{img_path.name}" data-filename="{img_path.name}">
                        <img src="{image_uri}" alt="{img_path.name}">
                        <div class="photo-info">
                            <p class="photo-filename">{img_path.name}</p>
                            {photo_card_content}
                        </div>
                        <button class="delete-photo-btn" onclick="deletePhoto(\'{album_name}\', \'{img_path.name}\')">×</button>
                    </div>
                    '''
                except Exception: pass

            images_html += f'''
            <div class="add-photo-card" onclick="document.getElementById('add-photo-input-{album_name}').click()">
                <input type="file" id="add-photo-input-{album_name}" multiple accept="image/jpeg,image/png" style="display: none;" onchange="handlePhotoAdd('{album_name}')">
                <span>+</span>
                <p>Tambah Foto</p>
            </div>
            '''

            templates_html = ""
            if self.state.templates:
                template_opts = ""
                for t in self.state.templates:
                    try:
                        with open(t, "rb") as f:
                            t_b64 = base64.b64encode(f.read()).decode("utf-8")
                        t_src = f"data:image/{t.suffix[1:]};base64,{t_b64}"
                        safe_album_name = album_name.replace("'", "\\'")
                        template_opts += f'''
                        <div class="template-item" onclick="addConnector('{safe_album_name}', '{t.name}')">
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

            albums_html += f'''
            <div class="album-post" id="album-{album_name}">
                <div class="album-header">
                    <pre class="album-title" id="caption-{album_name}">{caption}</pre>
                    <div class="album-controls">
                        <button onclick="toggleEdit(this, \'{album_name}\')">Edit Judul</button>
                        <button class="delete-album-btn" onclick="deleteAlbum(\'{album_name}\')">Hapus Album</button>
                    </div>
                </div>
                <div class="photos-container" id="photos-container-{album_name}">{images_html}</div>
                {templates_html}
            </div>
            '''

        return f'''
        <!DOCTYPE html><html lang="id"><head>
            <meta charset="UTF-8"><title>Pratinjau Album Interaktif</title>
            <script src="https://cdn.jsdelivr.net/npm/sortablejs@latest/Sortable.min.js"></script>
            <style>
                body {{ font-family: sans-serif; margin: 0; background: #f0f2f5; }}
                .header {{ background: #1877f2; color: white; padding: 1em; text-align: center; position: sticky; top: 0; z-index: 100; }}
                .container {{ max-width: 1000px; margin: auto; padding: 1em; }}
                .album-post {{ border: 1px solid #ddd; margin-bottom: 2em; background: #fff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .album-header {{ padding: 1em; border-bottom: 1px solid #ddd; display: flex; justify-content: space-between; align-items: center; gap: 1em; }}
                .album-title {{ flex-grow: 1; margin: 0; white-space: pre-wrap; padding: 0.5em; border-radius: 6px; }}
                .album-title[contenteditable="true"] {{ background: #e4e6eb; outline: 2px solid #1877f2; }}
                .photos-container {{ display: flex; flex-wrap: wrap; gap: 1em; padding: 1em; align-items: flex-start; }}
                .photo-card {{ position: relative; border: 1px solid #ccc; border-radius: 8px; overflow: hidden; width: 220px; background: #f9f9f9; box-shadow: 0 1px 2px rgba(0,0,0,0.1); display: flex; flex-direction: column; cursor: grab; }}
                .photo-card:active {{ cursor: grabbing; }}
                .photo-card img {{ width: 100%; height: 220px; object-fit: contain; background: #000; display: block; }}
                .photo-info {{ padding: 10px; flex-grow: 1; display: flex; flex-direction: column; justify-content: space-between; }}
                .photo-filename {{ font-weight: bold; font-size: 0.9em; margin: 0 0 8px 0; word-wrap: break-word; }}
                .photo-description {{ font-size: 0.85em; color: #333; margin: 0; white-space: pre-wrap; word-wrap: break-word; }}
                .delete-photo-btn {{ z-index: 10; position: absolute; top: 5px; right: 5px; background: rgba(0,0,0,0.7); color: white; border: none; border-radius: 50%; cursor: pointer; width: 24px; height: 24px; font-size: 16px; line-height: 24px; text-align: center; padding: 0; }}
                .add-photo-card {{ width: 220px; height: 100%; min-height: 300px; border: 2px dashed #ccc; border-radius: 8px; display: flex; flex-direction: column; justify-content: center; align-items: center; cursor: pointer; background: #f9f9f9; color: #555; transition: all 0.2s; }}
                .add-photo-card:hover {{ background: #e9e9e9; border-color: #999; }}
                .add-photo-card span {{ font-size: 48px; line-height: 1; }}
                .add-photo-card p {{ margin-top: 8px; font-weight: bold; text-align: center; }}
                .main-controls {{ text-align: center; padding: 2em; }}
                .main-controls button {{ background: #28a745; color: white; font-size: 1.2em; padding: 0.8em 1.5em; border: none; border-radius: 8px; cursor: pointer; }}
                .sortable-ghost {{ opacity: 0.4; background: #c8ebfb; }}
                .choice-prompt {{ font-weight: bold; font-size: 0.9em; margin-bottom: 5px; }}
                .caption-choice-select {{ width: 100%; padding: 5px; border-radius: 4px; margin-bottom: 5px; }}
                .fallback-preview {{ font-size: 0.8em; color: #555; margin: 0; padding: 5px; background: #f0f0f0; border-radius: 4px; }}
                .edit-button {{ /* No custom style needed, inherits from default button */ }}
                .connector-container {{ padding: 0 1em 1em 1em; border-top: 1px solid #eee; background: #fafafa; }}
                .connector-label {{ font-weight: bold; margin: 10px 0 5px; font-size: 0.9em; color: #555; }}
                .template-list {{ display: flex; gap: 10px; overflow-x: auto; padding-bottom: 5px; }}
                .template-item {{ border: 1px solid #ddd; border-radius: 4px; padding: 4px; background: white; cursor: pointer; text-align: center; width: 80px; flex-shrink: 0; transition: all 0.2s; }}
                .template-item:hover {{ border-color: #1877f2; background: #e7f3ff; }}
                .template-item img {{ width: 100%; height: 60px; object-fit: cover; border-radius: 2px; display: block; margin-bottom: 4px; }}
                .template-item span {{ font-size: 0.7em; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
            </style>
        </head><body>
            <div class="header"><h1>Pratinjau Album Interaktif</h1></div>
            <div class="container">
                {albums_html}
                <div class="main-controls" id="main-controls"><button onclick="continueUpload()">Lanjutkan Proses Unggah</button></div>
            </div>
            <script>
                function postAction(path, body) {{ return fetch(path, {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(body) }}); }}
                function addConnector(albumName, templateName) {{
                    postAction('/add_connector', {{ album_name: albumName, template_name: templateName }})
                    .then(r => {{
                        if (r.ok) location.reload();
                        else alert('Gagal menambahkan connector');
                    }});
                }}
                function toggleEdit(btn, name) {{
                    const el = document.getElementById('caption-' + name);
                    if (btn.textContent === 'Edit Judul') {{
                        el.contentEditable = true; el.focus(); btn.textContent = 'Simpan';
                    }} else {{
                        el.contentEditable = false; btn.textContent = 'Edit Judul';
                        postAction('/edit_caption', {{ album_name: name, caption: el.innerText }});
                    }}
                }}
                function togglePhotoEdit(btn, albumName, photoName) {{
                    const el = document.getElementById('caption-' + albumName + '-' + photoName);
                    if (btn.textContent === 'Edit Caption') {{
                        el.contentEditable = true;
                        el.focus();
                        btn.textContent = 'Simpan';
                    }} else {{
                        el.contentEditable = false;
                        btn.textContent = 'Edit Caption';
                        postAction('/edit_photo_caption', {{
                            album_name: albumName,
                            photo_name: photoName,
                            caption: el.innerText
                        }});
                    }}
                }}
                function deleteAlbum(name) {{
                    if (!confirm(`Yakin hapus album "` + name + `"?`)) return;
                    postAction('/delete_album', {{ album_name: name }}).then(r => r.ok && document.getElementById('album-' + name).remove());
                }}
                function deletePhoto(albumName, photoName) {{
                    postAction('/delete_photo', {{ album_name: albumName, photo_name: photoName }}).then(r => r.ok && document.getElementById('photo-' + albumName + '-' + photoName).remove());
                }}
                function continueUpload() {{
                    document.getElementById('main-controls').innerHTML = '<h2>✅ Berhasil! Silakan kembali ke terminal...</h2>';
                    postAction('/shutdown', {{}})
                }}
                function handlePhotoAdd(albumName) {{
                    const input = document.getElementById('add-photo-input-' + albumName);
                    const files = input.files;
                    if (files.length === 0) return;

                    const addPhotoCard = input.parentElement;

                    for (const file of files) {{
                        const reader = new FileReader();
                        reader.onload = function(e) {{
                            const photoData = e.target.result;
                            postAction('/add_photo', {{
                                album_name: albumName,
                                photo_name: file.name,
                                photo_data: photoData
                            }}).then(response => {{
                                if (response.ok) {{
                                    const newPhotoCardHTML = `
                                    <div class="photo-card" id="photo-${{albumName}}-${{file.name}}" data-filename="${{file.name}}">
                                        <img src="${{photoData}}" alt="${{file.name}}">
                                        <div class="photo-info">
                                            <p class="photo-filename">${{file.name}}</p>
                                            <p class="photo-description" id="caption-${{albumName}}-${{file.name}}"></p>
                                            <button onclick="togglePhotoEdit(this, 
'${{albumName}}
', 
'${{file.name}}
')">Edit Caption</button>
                                        </div>
                                        <button class="delete-photo-btn" onclick="deletePhoto('
${{albumName}}
', 
'${{file.name}}
')">×</button>
                                    </div>
                                    `;
                                    addPhotoCard.insertAdjacentHTML('beforebegin', newPhotoCardHTML);
                                    initSortable();
                                }} else {{
                                    alert('Gagal menambahkan foto: ' + file.name);
                                }}
                            }});
                        }};
                        reader.readAsDataURL(file);
                    }}
                    input.value = '';
                }}

                function handleCaptionChoice(selectElement, albumName, photoName, fallbackCaption) {{
                    const choice = selectElement.value;
                    let newCaption = '';
                    if (choice === 'use_desc') {{
                        newCaption = fallbackCaption;
                    }}
                    
                    const choiceContainer = document.getElementById('choice-container-' + albumName + '-' + photoName);
                    const descriptionEl = choiceContainer.nextElementSibling;
                    const editButton = descriptionEl.nextElementSibling;

                    descriptionEl.innerText = newCaption;
                    choiceContainer.style.display = 'none';
                    descriptionEl.style.display = 'block';
                    editButton.style.display = 'inline-block';

                    postAction('/edit_photo_caption', {{
                        album_name: albumName,
                        photo_name: photoName,
                        caption: newCaption
                    }});
                }}

                function initSortable() {{
                    document.querySelectorAll('.photos-container').forEach(container => {{
                        if (container.sortableInstance) {{
                            container.sortableInstance.destroy();
                        }}
                        container.sortableInstance = new Sortable(container, {{
                            animation: 150,
                            ghostClass: 'sortable-ghost',
                            filter: '.add-photo-card',
                            preventOnFilter: true,
                            onEnd: function (evt) {{
                                const albumName = evt.to.id.replace('photos-container-', '');
                                const newOrder = Array.from(evt.to.querySelectorAll('.photo-card')).map(card => card.dataset.filename);
                                postAction('/reorder_photos', {{ album_name: albumName, photo_order: newOrder }});
                            }}
                        }});
                    }});
                }}

                document.addEventListener('DOMContentLoaded', initSortable);
            </script>
        </body></html>
        '''

def run_interactive_preview(pending_albums, album_captions, album_images_map, all_photo_captions, product_link):
    templates = sorted(list(BASE_DIR.glob("bersambung.jpg")))
    state = AlbumPreviewState(list(pending_albums), dict(album_captions), dict(album_images_map), dict(all_photo_captions), product_link, templates=templates)
    PORT = 8080
    Handler = partial(AlbumPreviewRequestHandler, state)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(('', PORT), Handler)
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    url = f"http://127.0.0.1:{PORT}"
    log_message(f"Server pratinjau berjalan di {url}")
    
    print("  - Mencoba membuka browser secara otomatis...")
    try:
        opened = webbrowser.open(url)
        if not opened:
            print("  - Gagal membuka browser secara otomatis.")
            print(f"  - Silakan buka URL ini secara manual di browser Anda: {url}")
        else:
            print("  - Browser seharusnya terbuka. Jika tidak, silakan buka URL di atas secara manual.")
    except Exception as e:
        print(f"  - Terjadi error saat mencoba membuka browser: {e}")
        print(f"  - Silakan buka URL ini secara manual di browser Anda: {url}")

    try:
        while not state.server_should_shutdown: time.sleep(0.5)
    except KeyboardInterrupt:
        log_message("Server dihentikan.")
    httpd.shutdown()
    httpd.server_close()
    server_thread.join()
    log_message("Server pratinjau ditutup.")
    with state.lock:
        return state.pending_albums, state.album_captions, state.album_images_map, state.all_photo_captions

# --- FUNGSI UTAMA ---

def run_interactive():
    """Menjalankan skrip dalam mode interaktif."""
    clear_screen()
    print("📚 Mode Postingan Album\n")
    
    all_pages_data = check_and_refresh_tokens()
    chosen_page = None
    api = FacebookAPI()

    while not chosen_page:
        if not all_pages_data:
            all_pages_data = refresh_page_list_flow()
            if not all_pages_data:
                log_error("Gagal mendapatkan daftar halaman. Kembali ke menu utama.")
                time.sleep(2)
                return
            continue

        print("=== Pilih Halaman Facebook ===")
        page_list = list(all_pages_data.values())
        for i, page in enumerate(page_list):
            print(f"{i + 1}. {page['name']} (ID: {page['id']})")
        print("\n[B] Kembali ke Menu Utama")
        choice = input("Pilih nomor halaman atau opsi: ").strip().lower()

        if choice == 'b':
            return
        else:
            try:
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(page_list):
                    chosen_page = page_list[choice_idx]
                else:
                    print("❌ Pilihan tidak valid.")
            except (ValueError, KeyError):
                print("❌ Input tidak valid.")

    api.set_page(chosen_page['id'], chosen_page['access_token'])
    print(f"\n✅ Oke! Menggunakan Halaman: {chosen_page['name']}")

    main_folder_path = None
    pending_albums = []
    upload_choice = None

    while True:
        if main_folder_path is None:
            default_output_path = BASE_DIR / "output"
            if upload_choice is None and default_output_path.is_dir():
                print(f"📂 Folder 'output' terdeteksi secara otomatis.")
                main_folder_path = default_output_path
            else:
                main_folder_path = Path(input("📂 Masukkan path folder utama yang berisi album-album: ").strip())

            if not main_folder_path or not main_folder_path.is_dir():
                log_message("Folder utama tidak valid atau tidak ditemukan.", is_error=True)
                retry = input("Coba lagi? (y/n): ").strip().lower()
                if retry == 'y':
                    main_folder_path = None
                    clear_screen()
                    continue
                else:
                    return

        print(f"   -> Memindai album di: {main_folder_path}")
        uploaded_set = load_uploaded_log(main_folder_path)
        album_folders = sorted([d for d in main_folder_path.iterdir() if d.is_dir() or (d.is_file() and d.suffix.lower() in ['.jpg', '.jpeg', '.png'])])
        pending_albums_all = [d for d in album_folders if d.name not in uploaded_set and f"{d.name} (Part 1)" not in uploaded_set]
        
        print(f"\nℹ️  Ditemukan {len(album_folders)} total album/foto.")
        if not pending_albums_all:
            log_message("Tidak ada album baru untuk diunggah di folder ini.", is_error=False)
            print("\n--- Opsi ---")
            print("1. Ubah Folder Sumber Album")
            print("2. Keluar")
            choice = input("Pilih opsi: ").strip()
            if choice == '1':
                clear_screen()
                new_path = input("📂 Masukkan path folder utama yang berisi album-album: ").strip()
                if Path(new_path).is_dir():
                    main_folder_path = Path(new_path)
                    continue
                else:
                    log_message("Folder tidak valid atau tidak ditemukan.", is_error=True)
                    main_folder_path = None
                    continue
            else:
                return

        print(f"✅ {len(pending_albums_all)} album siap untuk diproses (belum diunggah).")

        while True:
            print("\n--- Pilih Mode Unggahan Album ---")
            print("1. Unggah Semua Album (sesuai urutan)")
            print("2. Unggah Sejumlah Album Secara Acak")
            print("3. Pilih Album Tertentu untuk Diunggah")
            print("4. Unggah Satu Album Acak")
            print("5. Ubah Folder Sumber Album")
            upload_choice = input("Pilih mode (1/2/3/4/5): ").strip()

            if upload_choice == '1':
                pending_albums = pending_albums_all
                break
            elif upload_choice == '2':
                while True:
                    try:
                        num_random = int(input(f"Berapa album acak yang ingin diunggah (maks: {len(pending_albums_all)})? ").strip())
                        if 0 < num_random <= len(pending_albums_all):
                            pending_albums = random.sample(pending_albums_all, num_random)
                            break
                        else: print("❌ Jumlah tidak valid.")
                    except ValueError: print("❌ Masukkan angka.")
                if pending_albums: break
            elif upload_choice == '3':
                print("\n--- Pilih Album yang Akan Diunggah ---")
                for i, f in enumerate(pending_albums_all): print(f"{i + 1}. {f.name}")
                while True:
                    try:
                        choices_str = input("Masukkan nomor album (pisahkan dengan koma, cth: 1,3,5): ").strip()
                        selected_indices = [int(i.strip()) - 1 for i in choices_str.split(',')]
                        if all(0 <= idx < len(pending_albums_all) for idx in selected_indices):
                            pending_albums = [pending_albums_all[i] for i in selected_indices]
                            break
                        else: print("❌ Ada nomor yang tidak valid.")
                    except (ValueError, IndexError): print("❌ Input tidak valid. Pastikan formatnya benar.")
                if pending_albums: break
            elif upload_choice == '4':
                pending_albums = random.sample(pending_albums_all, 1)
                break
            elif upload_choice == '5':
                clear_screen()
                print("🔄 Mengatur ulang folder sumber...")
                new_path = input("📂 Masukkan path folder utama yang berisi album-album: ").strip()
                if Path(new_path).is_dir():
                    main_folder_path = Path(new_path)
                    upload_choice = None
                    break
                else:
                    log_message("Folder tidak valid atau tidak ditemukan.", is_error=True)
                    main_folder_path = None
                    upload_choice = None
                    continue
            else:
                print("❌ Pilihan tidak valid.")
        
        if upload_choice == '5':
            continue
        
        if pending_albums:
            break

    print(f"\n✅ Oke! {len(pending_albums)} album akan diproses.")

    print("🔎 Memindai file gambar dan konten di setiap album...")
    
    album_captions = {a.name: generate_main_caption(a) for a in pending_albums}
    album_images_map = {
        a.name: [a] if a.is_file() else sorted([f for f in a.iterdir() if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.png']])
        for a in pending_albums
    }
    all_photo_captions = {a.name: load_photo_captions(a) for a in pending_albums}

    # --- Cek dan tanyakan soal fallback caption ---
    needs_fallback_check = False
    for album_name, photos_data in all_photo_captions.items():
        for photo_name, caption_data in photos_data.items():
            if not caption_data.get("description2") and caption_data.get("description"):
                needs_fallback_check = True
                break
        if needs_fallback_check:
            break

    if needs_fallback_check:
        print("\n⚠️ Ditemukan beberapa foto tanpa 'description2' namun memiliki 'description'.")
        fallback_choice = input("   Gunakan 'description' sebagai caption foto jika 'description2' kosong? (y/n): ").strip().lower()
        if fallback_choice == 'y':
            for album_name, photos_data in all_photo_captions.items():
                for photo_name, caption_data in photos_data.items():
                    if not caption_data.get("description2") and caption_data.get("description"):
                        all_photo_captions[album_name][photo_name]["description2"] = caption_data["description"]
            print("   ✅ Oke, 'description' akan digunakan jika 'description2' kosong.")
    
    original_count = len(pending_albums)
    pending_albums[:] = [a for a in pending_albums if album_images_map.get(a.name)]
    if len(pending_albums) < original_count:
        print(f"⚠️ Ditemukan {original_count - len(pending_albums)} album kosong atau tanpa gambar. Album tersebut akan dilewati.")

    if not pending_albums:
        log_message("Tidak ada album valid yang tersisa untuk diunggah.")
        return

    # --- INPUT CAPTION & LINK TAMBAHAN ---
    print("\n📝 Masukkan teks caption tambahan (opsional).")
    additional_caption = input("   Teks Caption: ").strip()

    print("\n🔗 Masukkan tautan produk/link (opsional).")
    product_link = input("   Tautan Produk: ").strip()

    # --- INPUT REGION LOCK ---
    region_lock_countries = get_country_codes()

    while True:
        preview_choice = input("\n👀 Buka pratinjau interaktif di browser (bisa edit/hapus)? (y/n): ").strip().lower()
        if preview_choice in ['y', 'n']: break
        print("❌ Pilihan tidak valid. Masukkan 'y' atau 'n'.")

    if preview_choice == 'y':
        try:
            pending_albums, album_captions, album_images_map, all_photo_captions = run_interactive_preview(
                pending_albums, album_captions, album_images_map, all_photo_captions, product_link
            )
            if not pending_albums:
                log_message("Semua album dibatalkan dari daftar unggah. Proses dihentikan.")
                return
            print(f"\n✅ Pratinjau selesai. {len(pending_albums)} album siap untuk diunggah.")
        except Exception as e:
            log_error(f"Gagal menjalankan pratinjau interaktif: {e}")
            while True:
                continue_anyway = input("Tetap lanjutkan proses unggah tanpa preview? (y/n): ").strip().lower()
                if continue_anyway == 'y': break
                elif continue_anyway == 'n':
                    print("Proses unggah dibatalkan."); return
                else: print("❌ Pilihan tidak valid. Masukkan 'y' atau 'n'.")

    # --- RESOLVE FINAL CAPTIONS AFTER PREVIEW ---
    final_captions_map = {}
    for album_name, photos_data in all_photo_captions.items():
        final_captions_map[album_name] = {}
        for photo_name, caption_data in photos_data.items():
            final_captions_map[album_name][photo_name] = caption_data.get("description2", "")

    # --- Blok Input Strategi Penjadwalan ---
    strategy = None
    start_time = None
    interval_value = 0
    interval_unit = 'hours'

    while not strategy:
        print("\nPilih strategi penjadwalan:")
        print("1. Jadwalkan dengan Interval Jam (Otomatis)")
        print("2. Jadwalkan dengan Interval Hari (Otomatis)")
        print("3. Manual per Album (Tanya setiap album)")
        print("4. Langsung Publish Semua")
        print("5. Simpan Semua sebagai Draf")
        choice = input("Pilihan: ").strip()

        if choice in ['1', '2']:
            start_time_input = get_datetime_input("Masukkan waktu mulai untuk album PERTAMA")
            if isinstance(start_time_input, datetime):
                start_time = start_time_input
            else: # 'now'
                start_time = datetime.now(timezone.utc).astimezone() + timedelta(minutes=11)
            
            while True:
                try:
                    unit_text = "jam" if choice == '1' else "hari"
                    interval_value = int(input(f"Masukkan interval per album (dalam {unit_text}): ").strip())
                    if interval_value > 0:
                        strategy = choice
                        interval_unit = 'hours' if choice == '1' else 'days'
                        break
                    else:
                        print("❌ Interval harus lebih besar dari 0.")
                except ValueError:
                    print("❌ Masukkan angka yang valid.")
        elif choice in ['3', '4', '5']:
            strategy = choice
        else:
            print("❌ Pilihan tidak valid.")

    print(f"\n🔄 Memulai proses untuk {len(pending_albums)} album...\n")
    for i, album_dir in enumerate(pending_albums):
        print(f"--- Proses album {i+1}/{len(pending_albums)}: {album_dir.name} ---")
        
        main_album_caption = album_captions.get(album_dir.name, album_dir.name)
        image_files = album_images_map.get(album_dir.name, [])
        photo_captions_map = final_captions_map.get(album_dir.name, {})

        final_caption = main_album_caption
        if additional_caption:
            final_caption += "\n\n" + additional_caption
        
        if not image_files:
            log_message(f"Tidak ada gambar ditemukan di album '{album_dir.name}'. Melewatkan.", is_error=True)
            continue

        print(f"  - Ditemukan {len(image_files)} gambar di album ini.")
        
        current_schedule_time = None
        if strategy in ['1', '2']:
            if interval_unit == 'hours':
                delta = timedelta(hours=interval_value * i)
            else: # days
                delta = timedelta(days=interval_value * i)
            current_schedule_time = start_time + delta

        if len(image_files) > 20:
            print(f"\n⚠️  Album '{album_dir.name}' punya {len(image_files)} foto (lebih dari 20).")
            print("1. Tetap upload semua sekaligus (mungkin gagal jika terlalu besar).")
            print("2. Upload Part 1 (20 foto), sisanya simpan untuk dilanjutkan nanti.")
            print("3. Upload sejumlah (n) foto, sisanya dicatat untuk belakangan.")
            choice = input("Pilih opsi (1/2/3): ").strip()

            if choice == '2':
                part1_images = image_files[:20]
                part2_images = image_files[20:]

                # Auto-include connector in Part 1
                connector = next((f for f in image_files if f.name.startswith("connector_")), None)
                if connector and connector not in part1_images:
                    print(f"  - Menyisipkan gambar penyambung '{connector.name}' ke Part 1")
                    part1_images.append(connector)

                print("  - Mengunggah Part 1...")
                photo_ids_part1 = []
                all_photos_uploaded_part1 = True
                total_part1_images = len(part1_images)
                for i, img_path in enumerate(part1_images):
                    if not img_path.exists():
                        log_message(f"File tidak ditemukan: {img_path.name}. Melewatkan.", is_error=True)
                        continue
                    photo_caption = photo_captions_map.get(img_path.name, "")
                    photo_id = api.upload_photo(img_path, caption=photo_caption, current=i + 1, total=total_part1_images)
                    if photo_id:
                        photo_ids_part1.append(photo_id)
                    else:
                        all_photos_uploaded_part1 = False
                        break
                
                if all_photos_uploaded_part1 and photo_ids_part1:
                    part1_log_name = f"{album_dir.name} (Part 1)"
                    part2_log_name = f"{album_dir.name} (Part 2)"

                    post_id = post_with_strategy(api, strategy, final_caption, photo_ids_part1, precalculated_time=current_schedule_time, countries=region_lock_countries)

                    if post_id:
                        if strategy == '5':
                            log_message(f"Berhasil disimpan sebagai draf: {part1_log_name} (Post ID: {post_id})")
                            save_to_draft_log(part1_log_name, post_id, album_dir)
                        else:
                            log_message(f"Berhasil unggah/jadwal: {part1_log_name}")
                            save_to_uploaded_log(part1_log_name, album_dir)

                        pending = load_pending_parts()
                        pending[part2_log_name] = {
                            "album_name": album_dir.name,
                            "dir": str(album_dir),
                            "remaining_photos": [f.name for f in part2_images],
                            "caption": final_caption,
                            "product_link": product_link
                        }
                        save_pending_parts(pending)
                        log_message(f"Part 2 dari '{album_dir.name}' disimpan untuk dilanjutkan nanti.")
                    else:
                        log_error(f"Gagal memproses Part 1 dari album '{album_dir.name}'.")
                else:
                    log_error(f"Gagal mengunggah foto untuk Part 1 dari album '{album_dir.name}'. Album ini akan dilewati.")

                continue
            
            elif choice == '3':
                while True:
                    try:
                        n = int(input(f"Masukkan jumlah foto yang mau diupload (1-{len(image_files)}): ").strip())
                        if 1 <= n < len(image_files): # n < total supaya ada sisa
                            break
                        else:
                            print(f"❌ Jumlah harus antara 1 dan {len(image_files) - 1}.")
                    except ValueError:
                        print("❌ Masukkan angka yang valid.")
                
                part1_images = image_files[:n]
                part2_images = image_files[n:]

                # Auto-include connector in Part 1
                connector = next((f for f in image_files if f.name.startswith("connector_")), None)
                if connector and connector not in part1_images:
                    print(f"  - Menyisipkan gambar penyambung '{connector.name}' ke Part 1")
                    part1_images.append(connector)

                print(f"  - Mengunggah {n} foto pertama...")
                photo_ids_part1 = []
                all_photos_uploaded_part1 = True
                total_part1_images = len(part1_images)
                for i, img_path in enumerate(part1_images):
                    if not img_path.exists():
                        log_message(f"File tidak ditemukan: {img_path.name}. Melewatkan.", is_error=True)
                        continue
                    photo_caption = photo_captions_map.get(img_path.name, "")
                    photo_id = api.upload_photo(img_path, caption=photo_caption, current=i + 1, total=total_part1_images)
                    if photo_id:
                        photo_ids_part1.append(photo_id)
                    else:
                        all_photos_uploaded_part1 = False
                        break

                if all_photos_uploaded_part1 and photo_ids_part1:
                    part1_log_name = f"{album_dir.name} (Part 1)"
                    part2_log_name = f"{album_dir.name} (Part 2)"
                    post_id = post_with_strategy(api, strategy, final_caption, photo_ids_part1,
                                                 precalculated_time=current_schedule_time, countries=region_lock_countries)
                    if post_id:
                        if strategy == '5':
                            save_to_draft_log(part1_log_name, post_id, album_dir)
                        else:
                            save_to_uploaded_log(part1_log_name, album_dir)

                        pending = load_pending_parts()
                        pending[part2_log_name] = {
                            "album_name": album_dir.name,
                            "dir": str(album_dir),
                            "remaining_photos": [f.name for f in part2_images],
                            "caption": final_caption,
                            "product_link": product_link
                        }
                        save_pending_parts(pending)
                        log_message(f"✅ Sisa {len(part2_images)} foto disimpan untuk dilanjutkan nanti.")
                else:
                    log_error(f"Gagal mengunggah foto untuk Part 1 dari album '{album_dir.name}'.")
                continue

        photo_ids = []
        all_photos_uploaded = True
        total_images = len(image_files)
        for i, img_path in enumerate(image_files):
            if not img_path.exists():
                log_message(f"File tidak ditemukan: {img_path.name}. Melewatkan.", is_error=True)
                continue
            photo_caption = photo_captions_map.get(img_path.name, "")
            photo_id = api.upload_photo(img_path, caption=photo_caption, current=i + 1, total=total_images)
            if photo_id:
                photo_ids.append(photo_id)
            else:
                log_error(f"Gagal mengunggah salah satu foto di album '{album_dir.name}'. Album ini akan dilewati.")
                all_photos_uploaded = False
                break
        
        if not all_photos_uploaded or not photo_ids:
            continue

        post_id = post_with_strategy(api, strategy, final_caption, photo_ids, precalculated_time=current_schedule_time, countries=region_lock_countries)

        if post_id:
            if strategy == '5':
                log_message(f"Berhasil disimpan sebagai draf: Album '{album_dir.name}' (Post ID: {post_id})")
                save_to_draft_log(album_dir.name, post_id, album_dir)
            else:
                log_message(f"Berhasil unggah/jadwal: Album '{album_dir.name}'")
                save_to_uploaded_log(album_dir.name)
        
        print("-" * (len(album_dir.name) + 24))
        time.sleep(2)

    print("\n\n📌 Ringkasan Sesi:")
    if error_log:
        print("Selesai dengan beberapa error:")
        for i, e in enumerate(error_log, 1):
            print(f"  {i}. {e}")
    else:
        log_message("Semua album berhasil diproses tanpa error.")

def run_schedule_from_draft_mode():
    """Menjalankan alur untuk menjadwalkan atau menghapus postingan dari draf yang ada."""
    clear_screen()
    print("🗓️  Kelola Draf Tersimpan")
    print("==================================================")
    
    all_pages_data = load_tokens()
    if not all_pages_data:
        log_error("File token tidak ditemukan. Jalankan 'Perbarui Token' dari menu utama.")
        return

    drafts = load_draft_log()
    if not drafts:
        log_message("Tidak ada draf yang tersimpan untuk dikelola.", is_error=False)
        return

    draft_list = list(drafts.items())

    print("--- Daftar Draf Tersimpan ---")
    for i, (post_id, data) in enumerate(draft_list):
        try:
            page_id_from_draft = post_id.split('_')[0]
            page_info = all_pages_data.get(page_id_from_draft)
            page_name_display = page_info['name'] if page_info else f"ID: {page_id_from_draft}"
        except IndexError:
            page_name_display = f"ID Invalid: {post_id}"
        print(f"{i + 1}. {data['album_name']} (Halaman: {page_name_display})")
    
    chosen_post_id, chosen_data = None, None

    if len(draft_list) == 1:
        print("\n✅ Hanya ada satu draf, memilih secara otomatis.")
        chosen_post_id, chosen_data = draft_list[0]
    else:
        try:
            choice_str = input("\nPilih nomor draf untuk dikelola: ").strip()
            choice_idx = int(choice_str) - 1
            if 0 <= choice_idx < len(draft_list):
                chosen_post_id, chosen_data = draft_list[choice_idx]
            else:
                log_error("Nomor tidak valid.")
        except (ValueError, IndexError):
            log_error("Input tidak valid.")

    if not chosen_post_id:
        return

    album_name = chosen_data['album_name']

    try:
        page_id_from_draft = chosen_post_id.split('_')[0]
    except IndexError:
        log_error(f"Format ID Draf '{chosen_post_id}' tidak valid. Tidak bisa mendeteksi ID Halaman.")
        return

    chosen_page = all_pages_data.get(page_id_from_draft)
    if not chosen_page:
        log_error(f"Token untuk Halaman dengan ID '{page_id_from_draft}' tidak ditemukan.")
        return

    api = FacebookAPI()
    api.set_page(chosen_page['id'], chosen_page['access_token'])
    print(f"\n✅ Halaman terdeteksi: {chosen_page['name']}")

    print(f"\nAnda memilih draf: '{album_name}'")
    print("Apa yang ingin Anda lakukan?")
    print("1. Jadwalkan atau terbitkan postingan ini")
    print("2. Hapus draf ini")
    print("3. Batal")
    action_choice = input("Pilihan (1/2/3): ").strip()

    if action_choice == '1':
        schedule_input = get_datetime_input(f"Jadwal untuk album '{album_name}'")
        if not schedule_input:
            return

        success = False
        if schedule_input == 'now':
            success = api.publish_existing_post(chosen_post_id)
            if success:
                log_message(f"Berhasil menerbitkan album '{album_name}' secara langsung.")
        else:
            schedule_time = schedule_input
            unix_time = int(schedule_time.timestamp())
            print("\n⚠️  PERINGATAN: Menurut dokumentasi API, unggahan foto untuk draf/jadwal")
            print("   berisiko dihapus oleh Facebook jika tidak dipublikasikan dalam 24 jam.")
            print("   Disarankan untuk menjadwalkan dalam kurun waktu tersebut.\n")
            success = api.schedule_existing_post(chosen_post_id, unix_time)
            if success:
                log_message(f"Berhasil menjadwalkan album '{album_name}' pada {schedule_time.strftime('%Y-%m-%d %H:%M')}")

        if success:
            album_path_str = chosen_data.get('album_path')
            album_folder_path = Path(album_path_str) if album_path_str else None
            save_to_uploaded_log(album_name, album_folder_path)
            remove_from_draft_log(chosen_post_id)
        else:
            log_error(f"Gagal memproses album '{album_name}'. Lihat pesan error di atas.")

    elif action_choice == '2':
        confirm = input(f"Yakin ingin menghapus draf '{album_name}' dari log DAN Facebook? (y/n): ").lower()
        if confirm == 'y':
            success = api.delete_post(chosen_post_id)
            if success:
                remove_from_draft_log(chosen_post_id)
                log_message(f"Draf '{album_name}' berhasil dihapus.")
            else:
                log_error(f"Gagal menghapus draf dari Facebook.")
        else:
            log_message("Penghapusan dibatalkan.")
    
    elif action_choice == '3':
        log_message("Aksi dibatalkan.")
        return
    else:
        log_error("Pilihan tidak valid.")

def run_pending_parts_mode():
    pending = load_pending_parts()
    if not pending:
        print("✅ Tidak ada Part Sisa yang pending.")
        return

    all_pages_data = load_tokens()
    if not all_pages_data:
        log_error("Token halaman tidak ditemukan.")
        return

    print("\n=== Pilih Halaman untuk Upload Pending ===")
    pages = list(all_pages_data.items())
    for idx, (pid, pdata) in enumerate(pages, 1):
        print(f"{idx}. {pdata['name']} (ID: {pid})")

    choice = input("Masukkan nomor halaman: ").strip()
    try:
        choice_idx = int(choice) - 1
        if not (0 <= choice_idx < len(pages)):
            raise ValueError
    except ValueError:
        log_error("Nomor halaman tidak valid.")
        return

    selected_pid, selected_pdata = pages[choice_idx]
    api = FacebookAPI()
    api.set_page(selected_pid, selected_pdata['access_token'])
    print(f"\n✅ Menggunakan halaman: {selected_pdata['name']}\n")

    print("--- Daftar Part Sisa ---")
    pending_list_for_display = list(pending.items())
    for i, (key, data) in enumerate(pending_list_for_display, 1):
        print(f"{i}. {key} → {len(data['remaining_photos'])} foto")
    print("\n[P] Proses semua Part Sisa satu per satu")
    print("[H] Hapus Part Sisa dari daftar")
    print("[Q] Batal")

    sel = input("Pilih nomor / P / H / Q: ").strip().lower()
    if sel == 'q':
        return
    elif sel == 'h':
        print("\n--- Pilih Part Sisa untuk Dihapus ---")
        pending_list_for_delete = list(pending.items())
        for i, (key, data) in enumerate(pending_list_for_delete, 1):
            print(f"{i}. {key}")
        print("\n[A] Hapus SEMUA Part Sisa")
        print("[B] Batal")
        
        delete_choice = input("Pilih nomor atau opsi: ").strip().lower()

        if delete_choice == 'b':
            return
        elif delete_choice == 'a':
            confirm = input(f"Yakin ingin menghapus SEMUA ({len(pending_list_for_delete)}) part sisa? (y/n): ").lower()
            if confirm == 'y':
                save_pending_parts({})
                log_message("Semua part sisa telah dihapus.")
            else:
                log_message("Penghapusan massal dibatalkan.")
        else:
            try:
                del_idx = int(delete_choice) - 1
                if 0 <= del_idx < len(pending_list_for_delete):
                    key_to_delete, _ = pending_list_for_delete[del_idx]
                    confirm = input(f"Yakin ingin menghapus '{key_to_delete}'? (y/n): ").lower()
                    if confirm == 'y':
                        del pending[key_to_delete]
                        save_pending_parts(pending)
                        log_message(f"'{key_to_delete}' telah dihapus.")
                    else:
                        log_message("Penghapusan dibatalkan.")
                else:
                    log_error("Nomor tidak valid.")
            except (ValueError, IndexError):
                log_error("Input tidak valid.")
        return

    elif sel == 'p':
        to_upload = list(pending.items())
    else:
        try:
            sel_idx = int(sel) - 1
            if not (0 <= sel_idx < len(pending)):
                raise ValueError
            to_upload = [list(pending.items())[sel_idx]]
        except ValueError:
            log_error("Pilihan tidak valid.")
            return

    # --- INPUT CAPTION & LINK TAMBAHAN ---
    print("\n📝 Masukkan teks caption tambahan (opsional).")
    additional_caption = input("   Teks Caption: ").strip()

    print("\n🔗 Masukkan tautan produk/link (opsional).")
    product_link_input = input("   Tautan Produk: ").strip()

    # --- INPUT REGION LOCK ---
    region_lock_countries = get_country_codes()

    while True:
        preview_choice = input("\n👀 Buka pratinjau interaktif di browser (bisa edit/hapus)? (y/n): ").strip().lower()
        if preview_choice in ['y', 'n']: break
        print("❌ Pilihan tidak valid. Masukkan 'y' atau 'n'.")

    # --- Blok Input Strategi Penjadwalan ---
    strategy = None
    start_time = None
    interval_value = 0
    interval_unit = 'hours'

    while not strategy:
        print("\nPilih strategi penjadwalan:")
        print("1. Jadwalkan dengan Interval Jam (Otomatis)")
        print("2. Jadwalkan dengan Interval Hari (Otomatis)")
        print("3. Manual per Album (Tanya setiap album)")
        print("4. Langsung Publish Semua")
        print("5. Simpan Semua sebagai Draf")
        choice = input("Pilihan: ").strip()

        if choice in ['1', '2']:
            start_time_input = get_datetime_input("Masukkan waktu mulai untuk album PERTAMA")
            if isinstance(start_time_input, datetime):
                start_time = start_time_input
            else: # 'now'
                start_time = datetime.now(timezone.utc).astimezone() + timedelta(minutes=11)
            
            while True:
                try:
                    unit_text = "jam" if choice == '1' else "hari"
                    interval_value = int(input(f"Masukkan interval per album (dalam {unit_text}): ").strip())
                    if interval_value > 0:
                        strategy = choice
                        interval_unit = 'hours' if choice == '1' else 'days'
                        break
                    else:
                        print("❌ Interval harus lebih besar dari 0.")
                except ValueError:
                    print("❌ Masukkan angka yang valid.")
        elif choice in ['3', '4', '5']:
            strategy = choice
        else:
            print("❌ Pilihan tidak valid.")

    print(f"\n🔄 Memulai proses untuk {len(to_upload)} part sisa...\n")

    for i, (key, data) in enumerate(to_upload):
        print(f"--- Proses part sisa {i+1}/{len(to_upload)}: {key} ---")
        album_dir = Path(data['dir'])
        album_name = data['album_name']
        photo_files = [album_dir / f for f in data['remaining_photos']]

        current_schedule_time = None
        if strategy in ['1', '2']:
            if interval_unit == 'hours':
                delta = timedelta(hours=interval_value * i)
            else: # days
                delta = timedelta(days=interval_value * i)
            current_schedule_time = start_time + delta

        new_photos = [f.name for f in photo_files]
        new_caption = data['caption']

        if preview_choice == 'y':
            product_link = product_link_input if product_link_input else data.get("product_link", "")
            templates = sorted(list(BASE_DIR.glob("bersambung.jpg")))
            state = AlbumPreviewState(
                pending_albums=[album_dir],
                album_captions={album_name: data['caption']},
                album_images_map={album_name: photo_files},
                all_photo_captions={album_name: {}},
                product_link=product_link,
                templates=templates
            )

            PORT = 8080
            Handler = partial(AlbumPreviewRequestHandler, state)
            socketserver.TCPServer.allow_reuse_address = True
            server = socketserver.TCPServer(('', PORT), Handler)
            thread = threading.Thread(target=server.serve_forever)
            thread.daemon = True
            thread.start()

            url = f"http://127.0.0.1:{PORT}"
            print(f"✅ Preview album pending di {url} ({key})")
            
            print("  - Mencoba membuka browser secara otomatis...")
            try:
                opened = webbrowser.open(url)
                if not opened:
                    print("  - Gagal membuka browser secara otomatis.")
                    print(f"  - Silakan buka URL ini secara manual di browser Anda: {url}")
                else:
                    print("  - Browser seharusnya terbuka. Jika tidak, silakan buka URL di atas secara manual.")
            except Exception as e:
                print(f"  - Terjadi error saat mencoba membuka browser: {e}")
                print(f"  - Silakan buka URL ini secara manual di browser Anda: {url}")

            input("Tekan Enter jika selesai preview...")
            
            try:
                requests.post(f"{url}/shutdown", timeout=2)
            except requests.RequestException:
                pass
            
            server.shutdown()
            thread.join()

            if not state.pending_albums:
                log_message(f"Album '{key}' dihapus saat preview. Menghapus dari daftar pending.")
                if key in pending:
                    del pending[key]
                save_pending_parts(pending)
                continue

            new_photos = [p.name for p in state.album_images_map.get(album_name, [])]
            new_caption = state.album_captions.get(album_name, data['caption'])
        
        if not new_photos:
            log_message(f"Tidak ada foto tersisa di '{key}' setelah preview. Menghapus dari daftar pending.")
            if key in pending:
                del pending[key]
            save_pending_parts(pending)
            continue

        data['remaining_photos'] = new_photos
        data['caption'] = new_caption
        pending[key] = data
        save_pending_parts(pending)

        final_caption = new_caption
        if additional_caption:
            final_caption += "\n\n" + additional_caption

        if len(new_photos) > 20:
            print(f"\nAlbum '{key}' masih punya {len(new_photos)} foto.")
            print("1. Upload semua sisa foto sekaligus.")
            print("2. Upload 20 foto dulu, sisanya simpan untuk nanti.")
            split_choice = input("Pilih opsi (1/2): ").strip()

            if split_choice == '2':
                part1 = new_photos[:20]
                part2 = new_photos[20:]

                # Auto-include connector in Part 1
                connector = next((fname for fname in new_photos if fname.startswith("connector_")), None)
                if connector and connector not in part1:
                    print(f"  - Menyisipkan gambar penyambung '{connector}' ke Part 1")
                    part1.append(connector)

                photo_ids = []
                total_part1 = len(part1)
                for idx_photo, fname in enumerate(part1):
                    img_path = album_dir / fname
                    if not img_path.exists():
                        log_message(f"File tidak ditemukan: {img_path.name}. Melewatkan.", is_error=True)
                        continue
                    photo_id = api.upload_photo(img_path, caption="", current=idx_photo + 1, total=total_part1)
                    if photo_id:
                        photo_ids.append(photo_id)

                if photo_ids:
                    # Gunakan strategy yang dipilih di awal
                    post_id = post_with_strategy(api, strategy, final_caption, photo_ids, precalculated_time=current_schedule_time, countries=region_lock_countries)
                    if post_id:
                        log_message(f"✅ Berhasil unggah {key} (Part 1)")
                        save_to_uploaded_log(f"{key} (Part 1)")
                        pending[f"{key} (Part 2)"] = {
                            "album_name": data['album_name'],
                            "dir": str(album_dir),
                            "remaining_photos": part2,
                            "caption": new_caption,
                            "product_link": product_link_input if product_link_input else data.get("product_link", "")
                        }
                        if key in pending:
                            del pending[key]
                        save_pending_parts(pending)
                continue

        photo_ids = []
        total_new = len(new_photos)
        for idx_photo, fname in enumerate(new_photos):
            img_path = album_dir / fname
            if not img_path.exists():
                log_message(f"File tidak ditemukan: {img_path.name}. Melewatkan.", is_error=True)
                continue
            photo_id = api.upload_photo(img_path, caption="", current=idx_photo + 1, total=total_new)
            if photo_id:
                photo_ids.append(photo_id)

        if photo_ids:
            # Gunakan strategy yang dipilih di awal
            post_id = post_with_strategy(api, strategy, final_caption, photo_ids, precalculated_time=current_schedule_time, countries=region_lock_countries)
            if post_id:
                log_message(f"✅ Berhasil unggah {key}")
                save_to_uploaded_log(key, album_dir)
                if key in pending:
                    del pending[key]
                save_pending_parts(pending)

def run_single_post_mode():

    print("\n🚧 Fitur ini sedang dalam tahap pengembangan. 🚧")
    print("Fungsi untuk mengunggah postingan tunggal akan ditambahkan di sini.")
    time.sleep(3)

def main():
    """Menampilkan menu utama dan mengarahkan ke mode yang dipilih."""
    while True:
        clear_screen()
        print("🚀 Facebook Auto-Poster Terpadu 🚀")
        print("=====================================")
        print("1. 📚 Mode Postingan Album")
        print("2. 🗓️  Kelola Draf Tersimpan")
        print("3. 🔄 Lanjutkan Upload Part Sisa")
        print("4. 🖼️  Mode Postingan Tunggal (WIP)")
        print("5. 🔄 Perbarui Token/Daftar Halaman")
        print("0. 🚪 Keluar")

        choice = input("\nMasukkan pilihan (1-5, 0): ").strip()

        if choice == '1':
            run_interactive()
        elif choice == '2':
            run_schedule_from_draft_mode()
        elif choice == '3':
            run_pending_parts_mode()
        elif choice == '4':
            run_single_post_mode()
        elif choice == '5':
            refresh_page_list_flow()
        elif choice == '0':
            print("Program berhenti.")
            break
        else:
            print("❌ Pilihan tidak valid.")
            time.sleep(1)
            continue
        
        input("\nTekan Enter untuk kembali ke menu utama...")



if __name__ == "__main__":
    main()
