import os
import json
import shutil
import socket
import time
import io
import hashlib
import subprocess
from PIL import Image
from flask import Flask, render_template_string, request, jsonify, send_from_directory, send_file
from urllib.parse import quote as urlquote

app = Flask(__name__)

# Tambahkan filter kustom untuk URL Encoding di Jinja2 (berguna untuk nama folder berspasi)
@app.template_filter('urlencode')
def urlencode_filter(s):
    if type(s) == 'Markup':
        s = s.unescape()
    s = s.encode('utf8')
    s = urlquote(s)
    return s

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="id" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AutoPostFB Dashboard</title>
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons+Round" rel="stylesheet">
    <!-- SortableJS -->
    <script src="https://cdn.jsdelivr.net/npm/sortablejs@latest/Sortable.min.js"></script>
    <style>
        :root {
            --bg-app: #f4f6f8; --bg-panel: #ffffff; --bg-workspace: #e1e4e8;
            --border-color: #d1d5db; --text-main: #1f2937; --text-muted: #6b7280;
            --accent: #2563eb; --accent-hover: #1d4ed8; --item-hover: #f3f4f6;
            --item-active: #eef2ff; --canvas-bg: #000000;
            --shadow-canvas: 0 4px 15px rgba(0, 0, 0, 0.08);
            --success: #10b981; --danger: #ef4444; --warning: #f59e0b;
        }
        [data-bs-theme="dark"] {
            --bg-app: #111111; --bg-panel: #1e1e1e; --bg-workspace: #161616;
            --border-color: #333333; --text-main: #e5e5e5; --text-muted: #888888;
            --accent: #3b82f6; --accent-hover: #60a5fa; --item-hover: #262626;
            --item-active: #2a3a50; --canvas-bg: #000000;
            --shadow-canvas: 0 4px 20px rgba(0, 0, 0, 0.5);
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif; background-color: var(--bg-app);
            color: var(--text-main); height: 100vh; overflow: hidden;
            display: grid; grid-template-rows: 52px 1fr; grid-template-columns: 280px 1fr;
            grid-template-areas: "header header" "sidebar workspace";
            transition: background-color 0.3s, color 0.3s;
        }
        
        /* Header */
        .header-area { grid-area: header; background-color: var(--bg-panel); border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; padding: 0 20px; z-index: 10; }
        .logo { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 15px; }
        .header-actions { display: flex; align-items: center; gap: 8px; }
        
        /* Sidebar */
        .sidebar-area { grid-area: sidebar; background-color: var(--bg-panel); border-right: 1px solid var(--border-color); display: flex; flex-direction: column; overflow-y: auto; padding-bottom: 20px; }
        .sidebar-section { padding: 16px; display: flex; flex-direction: column; gap: 12px; }
        .section-title { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: var(--text-muted); font-weight: 700; }
        
        .options-box { background-color: var(--bg-app); border: 1px solid var(--border-color); border-radius: 12px; padding: 14px; display: flex; flex-direction: column; gap: 12px; }
        .form-label { font-size: 12px; font-weight: 700; color: var(--text-main); margin-bottom: 4px; display: block; }
        .input-box, .select-box { width: 100%; background-color: var(--bg-panel); color: var(--text-main); border: 1px solid var(--border-color); padding: 8px 10px; border-radius: 8px; font-size: 13px; outline: none; transition: all 0.2s; resize: vertical; }
        .input-box:focus, .select-box:focus { border-color: var(--accent); box-shadow: 0 0 0 2px var(--item-active); }
        
        /* Buttons */
        .btn-primary { background-color: var(--accent); color: #fff; border: none; padding: 8px 14px; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px; transition: background-color 0.2s; }
        .btn-primary:hover { background-color: var(--accent-hover); }
        .btn-outline { background: transparent; border: 1px solid var(--border-color); color: var(--text-main); padding: 8px 14px; border-radius: 6px; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px; font-size: 12px; font-weight: 600; transition: background-color 0.2s; }
        .btn-outline:hover { background: var(--item-hover); }
        .btn-danger { background-color: var(--danger); color: #fff; border: none; padding: 8px 14px; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px; transition: background-color 0.2s; }
        .btn-danger:hover { background-color: #dc2626; }
        .btn-icon { background: transparent; border: none; color: var(--text-muted); cursor: pointer; padding: 6px; border-radius: 6px; display: flex; align-items: center; justify-content: center; transition: all 0.2s; }
        .btn-icon:hover { background: var(--item-hover); color: var(--text-main); }
        
        /* Workspace */
        .workspace-area { grid-area: workspace; background-color: var(--bg-workspace); display: flex; flex-direction: column; overflow-y: auto; padding: 20px; }
        
        /* GRID KOTAK */
        .queue-container { 
            display: grid; 
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); 
            gap: 16px; 
            width: 100%; 
        }
        
        .queue-card { 
            background-color: var(--bg-panel); 
            border: 1px solid var(--border-color); 
            border-radius: 12px; 
            overflow: hidden; 
            display: flex; 
            flex-direction: column; 
            transition: transform 0.2s, box-shadow 0.2s; 
            position: relative;
        }
        .queue-card:hover { box-shadow: var(--shadow-canvas); transform: translateY(-2px); }
        .queue-card.uploaded { border-color: var(--success); opacity: 0.7; }
        .queue-card.uploaded:hover { transform: none; box-shadow: none; }
        
        .drag-handle { 
            position: absolute; 
            top: 8px; right: 8px; 
            background-color: rgba(0,0,0,0.6); 
            color: white; 
            display: flex; align-items: center; justify-content: center; 
            border-radius: 6px; 
            padding: 6px;
            cursor: grab; 
            z-index: 10;
            border: 1px solid rgba(255,255,255,0.2);
            backdrop-filter: blur(4px);
            touch-action: none;
        }
        .drag-handle:active { cursor: grabbing; }

        /* Media Thumbnail */
        .card-thumbnail-wrapper {
            position: relative;
            width: 100%;
            height: 150px;
            background: #111;
            cursor: pointer;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
            border-bottom: 1px solid var(--border-color);
        }
        .card-thumbnail-wrapper::after {
            content: "Klik untuk lihat media";
            position: absolute; top:0; left:0; width:100%; height:100%;
            background: rgba(0,0,0,0.5); color: white;
            display: flex; align-items: center; justify-content: center;
            opacity: 0; transition: opacity 0.2s;
            font-size: 12px; font-weight: bold; pointer-events: none;
        }
        .card-thumbnail-wrapper:hover::after { opacity: 1; }

        .card-thumbnail {
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: transform 0.3s;
        }
        .card-thumbnail-wrapper:hover .card-thumbnail {
            transform: scale(1.05);
        }
        .video-overlay {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: white;
            background: rgba(0,0,0,0.5);
            border-radius: 50%;
            width: 40px; height: 40px;
            display: flex; align-items: center; justify-content: center;
            pointer-events: none;
            z-index: 5;
            border: 2px solid white;
        }
        .video-overlay span { font-size: 24px; }
        .media-count-badge {
            position: absolute;
            bottom: 8px; right: 8px;
            background: rgba(0,0,0,0.7);
            color: white;
            font-size: 10px; font-weight: bold;
            padding: 4px 8px; border-radius: 12px;
            z-index: 5; pointer-events: none;
            display: flex; align-items: center; gap: 4px;
        }
        
        .card-body { padding: 12px; display: flex; flex-direction: column; gap: 8px; flex: 1; }
        .card-header { font-weight: 700; font-size: 13px; display: flex; align-items: center; gap: 6px; color: var(--text-main); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        
        .badge { padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700; display: inline-flex; align-items: center; gap: 2px; width: fit-content; }
        .badge-success { background-color: var(--success); color: white; }
        .badge-primary { background-color: var(--accent); color: white; }
        .badge-warning { background-color: var(--warning); color: white; }
        .badge-danger { background-color: var(--danger); color: white; }
        .badge-info { background-color: #0ea5e9; color: white; }
        
        .caption-preview { font-size: 11px; color: var(--text-muted); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; line-height: 1.4; flex: 1; }
        
        .card-actions { display: flex; gap: 6px; margin-top: auto; }
        .card-actions button { flex: 1; }
        
        .alert { padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; font-size: 13px; display: flex; align-items: center; gap: 10px; }
        .alert-info { background-color: rgba(59, 130, 246, 0.1); color: var(--accent); border: 1px solid var(--accent); }
        .alert-warning { background-color: rgba(245, 158, 11, 0.1); color: var(--warning); border: 1px solid var(--warning); }
        
        /* Modal */
        .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.6); display: none; justify-content: center; align-items: center; z-index: 1000; backdrop-filter: blur(4px); }
        .modal-overlay.active { display: flex; }
        .modal-content { background: var(--bg-panel); width: 90%; max-width: 600px; border-radius: 12px; border: 1px solid var(--border-color); box-shadow: var(--shadow-canvas); display: flex; flex-direction: column; max-height: 90vh; }
        .modal-content.wide { max-width: 900px; }
        .modal-header { padding: 16px 20px; border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; }
        .modal-header h3 { font-size: 16px; display: flex; align-items: center; gap: 8px; }
        .modal-body { padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 16px; }
        .modal-footer { padding: 16px 20px; border-top: 1px solid var(--border-color); display: flex; justify-content: flex-end; gap: 10px; }
        
        #mediaContainer { display: flex; flex-direction: column; gap: 16px; align-items: center; background: #000; border-radius: 8px; padding: 16px; }
        .media-item { max-width: 100%; max-height: 60vh; border-radius: 8px; object-fit: contain; }

        #toastContainer { position: fixed; top: 60px; right: 20px; z-index: 10000; display: flex; flex-direction: column; gap: 10px; pointer-events: none; }
        .toast { background-color: var(--bg-panel); color: var(--text-main); border-left: 4px solid var(--accent); padding: 12px 20px; border-radius: 6px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); font-size: 13px; font-weight: 600; min-width: 250px; display: flex; align-items: center; gap: 12px; transform: translateX(120%); transition: transform 0.3s; pointer-events: auto; border: 1px solid var(--border-color); }
        .toast.show { transform: translateX(0); }
        .toast.success { border-left-color: var(--success); }
        .toast.error { border-left-color: var(--danger); }

        /* Sortable ghost */
        .sortable-ghost { opacity: 0.4; background-color: var(--item-active); border: 2px dashed var(--accent); transform: scale(0.95); }
        .sortable-drag { box-shadow: 0 20px 40px rgba(0,0,0,0.4); transform: scale(1.05) rotate(2deg); cursor: grabbing !important; }
        
        @media (max-width: 900px) {
            body { grid-template-columns: 1fr; grid-template-rows: 52px auto 1fr; grid-template-areas: "header" "sidebar" "workspace"; overflow-y: auto; height: auto; }
            .sidebar-area { border-right: none; border-bottom: 1px solid var(--border-color); max-height: none; padding-bottom: 10px; }
            .queue-container { grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); }
            .card-thumbnail-wrapper { height: 120px; }
        }
    </style>
</head>
<body>
    <div id="toastContainer"></div>
    
    <header class="header-area">
        <div class="logo">
            <div style="background: transparent; color: var(--accent); padding: 4px 10px; border-radius: 12px; border: 1px solid var(--border-color); display: flex; align-items: center; justify-content: center;">
                <span class="material-icons-round" style="font-size: 14px;">facebook</span>
            </div>
            <span>AutoPostFB Queue</span>
        </div>
        <div class="header-actions">
            <button class="btn-icon" id="btnTheme" title="Ganti Tema">
                <span class="material-icons-round">light_mode</span>
            </button>
            <button class="btn-icon" id="btnFullscreen" title="Layar Penuh">
                <span class="material-icons-round">fullscreen</span>
            </button>
        </div>
    </header>

    <aside class="sidebar-area">
        <form action="/" method="GET" id="accountForm">
            <div class="sidebar-section">
                <h3 class="section-title">📂 Pengaturan Target</h3>
                <div class="options-box">
                    <div>
                        <label class="form-label">Pilih Akun / Base Folder</label>
                        <select name="base_dir" class="select-box" onchange="document.getElementById('accountForm').submit()">
                            <option value="">-- Pilih Folder --</option>
                            {% for name, path in folders.items() %}
                                <option value="{{ path }}" {% if selected_dir == path %}selected{% endif %}>{{ name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <button type="submit" class="btn-outline" style="width:100%;">
                        <span class="material-icons-round">refresh</span> Refresh Antrean
                    </button>
                </div>
            </div>
        </form>
        
        {% if queue %}
        <div class="sidebar-section">
            <h3 class="section-title">📊 Statistik Antrean</h3>
            <div class="options-box" style="gap: 8px;">
                <div style="display:flex; justify-content:space-between; font-size:12px;">
                    <span>Total Folder:</span> <strong>{{ queue|length }}</strong>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:12px; color:var(--success);">
                    <span>Sudah Selesai:</span> <strong>{{ queue|selectattr('uploaded', 'equalto', true)|list|length }}</strong>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:12px; color:var(--warning);">
                    <span>Menunggu:</span> <strong>{{ queue|selectattr('uploaded', 'equalto', false)|list|length }}</strong>
                </div>
                <hr style="border:none; border-top:1px solid var(--border-color); margin: 4px 0;">
                <button class="btn-primary" onclick="saveOrder()" id="btnSaveOrder" style="background:#f59e0b; color:#fff;">
                    <span class="material-icons-round">save</span> Simpan Urutan (Drag & Drop)
                </button>
            </div>
        </div>
        {% endif %}
    </aside>

    <main class="workspace-area">
        {% if selected_dir %}
            {% if queue %}
                <div class="alert alert-info">
                    <span class="material-icons-round" style="font-size:18px;">info</span>
                    <div>Tahan & geser (Drag & Drop) pada <strong>icon di pojok kanan atas kartu</strong> untuk mengatur ulang urutan, lalu klik "Simpan Urutan" di sidebar.</div>
                </div>
                
                <!-- Pending Queue (Sortable) -->
                <div class="queue-container" id="sortableQueue" style="margin-bottom: 30px;">
                    {% for item in queue if not item.uploaded %}
                    <div class="queue-card" data-id="{{ item.name }}">
                        <div class="drag-handle" title="Tahan & Geser"><span class="material-icons-round" style="font-size:16px;">open_with</span></div>
                        
                        <div class="card-thumbnail-wrapper" onclick='viewMedia({{ item.name|tojson }}, {{ item.media_files|tojson }})'>
                            {% if item.first_media %}
                                {% set ext = item.first_media.split('.')[-1]|lower %}
                                {% if ext in ['mp4', 'mov', 'avi'] %}
                                    <img src="/thumbnail?base={{ selected_dir | urlencode }}&folder={{ item.name | urlencode }}&file={{ item.first_media | urlencode }}" class="card-thumbnail" loading="lazy">
                                    <div class="video-overlay"><span class="material-icons-round">play_arrow</span></div>
                                {% else %}
                                    <img src="/thumbnail?base={{ selected_dir | urlencode }}&folder={{ item.name | urlencode }}&file={{ item.first_media | urlencode }}" class="card-thumbnail" loading="lazy">
                                {% endif %}
                            {% else %}
                                <span class="material-icons-round" style="font-size:40px; color:#444;">image_not_supported</span>
                            {% endif %}
                            
                            <div class="media-count-badge">
                                <span class="material-icons-round" style="font-size:12px;">collections</span> {{ item.media_count }}
                            </div>
                        </div>

                        <div class="card-body">
                            <div class="card-header" title="{{ item.name }}">
                                <span class="material-icons-round" style="color:var(--warning); font-size:16px;">folder</span>
                                <span>{{ item.name }}</span>
                            </div>
                            
                            {% if item.type == 'video' %}
                                <span class="badge badge-danger"><span class="material-icons-round" style="font-size:10px;">movie</span> Video</span>
                            {% else %}
                                <span class="badge badge-info"><span class="material-icons-round" style="font-size:10px;">image</span> Foto</span>
                            {% endif %}
                            
                            <div class="caption-preview" title="{{ item.caption }}">
                                {{ item.caption }}
                            </div>
                            
                            <div class="card-actions">
                                <button class="btn-outline" onclick="editCaption('{{ item.name|replace("'", "\\'") }}')" title="Ubah Caption">
                                    <span class="material-icons-round" style="font-size:14px;">edit</span> Edit
                                </button>
                                <button class="btn-danger" onclick="deleteFolder('{{ item.name|replace("'", "\\'") }}')" title="Hapus">
                                    <span class="material-icons-round" style="font-size:14px;">delete</span> Hapus
                                </button>
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                </div>
                
                <!-- Completed Queue (Not Sortable) -->
                {% set uploaded_items = queue|selectattr('uploaded', 'equalto', true)|list %}
                {% if uploaded_items %}
                    <div style="font-size:12px; font-weight:bold; color:var(--text-muted); margin-bottom:12px; text-transform:uppercase;">Riwayat Selesai</div>
                    <div class="queue-container">
                        {% for item in uploaded_items %}
                        <div class="queue-card uploaded">
                            <div class="drag-handle" style="cursor:not-allowed; opacity:0.3;"><span class="material-icons-round" style="font-size:16px;">lock</span></div>
                            
                            <div class="card-thumbnail-wrapper" onclick='viewMedia({{ item.name|tojson }}, {{ item.media_files|tojson }})'>
                                {% if item.first_media %}
                                    {% set ext = item.first_media.split('.')[-1]|lower %}
                                    {% if ext in ['mp4', 'mov', 'avi'] %}
                                        <img src="/thumbnail?base={{ selected_dir | urlencode }}&folder={{ item.name | urlencode }}&file={{ item.first_media | urlencode }}" class="card-thumbnail" loading="lazy" style="filter: grayscale(80%); opacity:0.6;">
                                        <div class="video-overlay"><span class="material-icons-round">play_arrow</span></div>
                                    {% else %}
                                        <img src="/thumbnail?base={{ selected_dir | urlencode }}&folder={{ item.name | urlencode }}&file={{ item.first_media | urlencode }}" class="card-thumbnail" loading="lazy" style="filter: grayscale(80%); opacity:0.6;">
                                    {% endif %}
                                {% endif %}
                                <div style="position:absolute; background:var(--success); color:white; padding:4px 10px; font-size:12px; font-weight:bold; border-radius:20px; z-index:10;"><span class="material-icons-round" style="font-size:14px; vertical-align:middle;">check_circle</span> SELESAI</div>
                            </div>

                            <div class="card-body">
                                <div class="card-header" title="{{ item.name }}" style="text-decoration: line-through; opacity:0.7;">
                                    <span class="material-icons-round" style="color:var(--success); font-size:16px;">folder</span>
                                    <span>{{ item.name }}</span>
                                </div>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                {% endif %}
            {% else %}
                <div class="alert alert-warning">
                    <span class="material-icons-round" style="font-size:18px;">warning</span>
                    Tidak ada folder konten ditemukan di direktori ini.
                </div>
            {% endif %}
        {% else %}
            <div class="alert alert-info" style="background:transparent; border-color:var(--border-color); color:var(--text-main); display:flex; flex-direction:column; align-items:center; justify-content:center; padding:40px; text-align:center; gap:15px; height:100%;">
                <span class="material-icons-round" style="font-size:48px; color:var(--text-muted);">swipe_up</span>
                <h3>Pilih Akun Terlebih Dahulu</h3>
                <p style="color:var(--text-muted); font-size:13px;">Silakan pilih akun atau base folder dari menu sidebar di sebelah kiri untuk melihat antrean postingan.</p>
            </div>
        {% endif %}
    </main>

    <!-- Modal Edit Caption -->
    <div class="modal-overlay" id="editModal">
        <div class="modal-content">
            <div class="modal-header">
                <h3><span class="material-icons-round" style="color:var(--accent);">edit_note</span> Edit Metadata Caption</h3>
                <button class="btn-icon" onclick="closeModal('editModal')"><span class="material-icons-round">close</span></button>
            </div>
            <div class="modal-body">
                <input type="hidden" id="folderName">
                <div>
                    <label class="form-label">Judul (post_title) - Opsional</label>
                    <input type="text" class="input-box" id="postTitle" placeholder="Misal: Update Hari Ini">
                </div>
                <div>
                    <label class="form-label">Isi Konten (summary) - Utama</label>
                    <textarea class="input-box" id="postSummary" rows="6" placeholder="Ketik caption utama di sini..."></textarea>
                </div>
                <div>
                    <label class="form-label">Call to Action (cta) - Opsional</label>
                    <input type="text" class="input-box" id="postCta" placeholder="Misal: Jangan lupa share!">
                </div>
                <div>
                    <label class="form-label">Hashtags (Pisahkan dengan Spasi)</label>
                    <input type="text" class="input-box" id="postHashtags" placeholder="Misal: viral trending fyp">
                    <small style="font-size:11px; color:var(--text-muted); margin-top:4px; display:block;">Simbol '#' akan otomatis ditambahkan oleh sistem.</small>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn-outline" onclick="closeModal('editModal')" style="width:auto;">Batal</button>
                <button class="btn-primary" onclick="saveCaption()" id="btnSave" style="width:auto;">
                    <span class="material-icons-round">save</span> Simpan Perubahan
                </button>
            </div>
        </div>
    </div>

    <!-- Modal View Media -->
    <div class="modal-overlay" id="mediaModal">
        <div class="modal-content wide">
            <div class="modal-header">
                <h3 id="mediaModalTitle"><span class="material-icons-round" style="color:var(--accent);">photo_library</span> Pratinjau Media</h3>
                <button class="btn-icon" onclick="closeModal('mediaModal')"><span class="material-icons-round">close</span></button>
            </div>
            <div class="modal-body" id="mediaContainer">
                <!-- Media will be injected here -->
            </div>
        </div>
    </div>

    <script>
        // THEME & FULLSCREEN LOGIC
        function setTheme(theme, save = true) {
            document.documentElement.setAttribute('data-bs-theme', theme);
            if (save) localStorage.setItem('theme', theme);
            const icon = document.querySelector('#btnTheme span');
            if (icon) icon.innerText = theme === 'dark' ? 'dark_mode' : 'light_mode';
        }

        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) {
            setTheme(savedTheme, false);
        } else {
            setTheme(window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light', false);
        }

        document.getElementById('btnTheme').addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-bs-theme');
            setTheme(currentTheme === 'dark' ? 'light' : 'dark', true);
        });
        
        const btnFullscreen = document.getElementById('btnFullscreen');
        if(btnFullscreen) {
            btnFullscreen.addEventListener('click', () => {
                if (!document.fullscreenElement) { 
                    document.documentElement.requestFullscreen().catch(() => {}); 
                } else { 
                    document.exitFullscreen(); 
                }
            });
            document.addEventListener('fullscreenchange', () => {
                btnFullscreen.querySelector('span').innerText = document.fullscreenElement ? 'fullscreen_exit' : 'fullscreen';
            });
        }

        function showToast(message, type = 'info') {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = 'toast ' + type;
            toast.innerHTML = `<span class="material-icons-round">${type === 'success' ? 'check_circle' : (type === 'error' ? 'error' : 'info')}</span><span>${message}</span>`;
            container.appendChild(toast);
            setTimeout(() => toast.classList.add('show'), 10);
            setTimeout(() => { toast.classList.remove('show'); setTimeout(() => toast.remove(), 300); }, 3000);
        }

        const selectedDir = `{{ selected_dir|safe }}`;

        function closeModal(id) {
            document.getElementById(id).classList.remove('active');
            if (id === 'mediaModal') {
                // Hentikan pemutaran video jika ada
                const videos = document.getElementById('mediaContainer').querySelectorAll('video');
                videos.forEach(v => v.pause());
            }
        }

        // DRAG AND DROP LOGIC
        let sortableInstance;
        document.addEventListener('DOMContentLoaded', () => {
            const queueEl = document.getElementById('sortableQueue');
            if (queueEl) {
                sortableInstance = new Sortable(queueEl, {
                    handle: '.drag-handle',
                    animation: 250,
                    easing: "cubic-bezier(0.25, 1, 0.5, 1)",
                    ghostClass: 'sortable-ghost',
                    dragClass: 'sortable-drag',
                    forceFallback: true, // Meningkatkan dukungan touch pada mobile
                    fallbackTolerance: 3, // Toleransi getaran jari saat menyentuh
                    direction: 'horizontal', // Membantu deteksi geser pada layout Grid
                    swapThreshold: 0.65,
                    invertSwap: true, // Membuat pergeseran di dalam Grid lebih masuk akal
                    onEnd: function() {
                        showToast("Urutan diubah! Jangan lupa klik 'Simpan Urutan'.", "warning");
                        const btn = document.getElementById('btnSaveOrder');
                        if(btn) {
                            btn.style.transform = 'scale(1.05)';
                            setTimeout(() => btn.style.transform = 'none', 300);
                        }
                    }
                });
            }
        });

        function saveOrder() {
            if (!sortableInstance) return;
            const order = sortableInstance.toArray();
            
            const btn = document.getElementById('btnSaveOrder');
            const originalText = btn.innerHTML;
            btn.innerHTML = '<span class="material-icons-round" style="animation:spin 2s linear infinite;">sync</span> Menyimpan...';
            btn.disabled = true;

            fetch('/api/reorder', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ base_dir: selectedDir, order: order })
            }).then(r => r.json()).then(res => {
                if(res.success) {
                    showToast('Urutan berhasil disimpan!', 'success');
                    setTimeout(() => location.reload(), 1000);
                } else {
                    showToast('Gagal menyimpan urutan: ' + res.error, 'error');
                    btn.innerHTML = originalText;
                    btn.disabled = false;
                }
            }).catch(e => {
                showToast('Terjadi kesalahan jaringan!', 'error');
                btn.innerHTML = originalText;
                btn.disabled = false;
            });
        }

        function deleteFolder(folderName) {
            if(confirm(`AWAS! Anda yakin ingin menghapus folder '${folderName}'? File foto/video di dalamnya akan terhapus juga!`)) {
                fetch('/api/delete', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ base_dir: selectedDir, folder_name: folderName })
                }).then(r => r.json()).then(res => {
                    if(res.success) location.reload();
                    else showToast('Gagal menghapus folder: ' + res.error, 'error');
                }).catch(e => showToast('Terjadi kesalahan jaringan!', 'error'));
            }
        }

        function editCaption(folderName) {
            fetch(`/api/meta?base_dir=${encodeURIComponent(selectedDir)}&folder_name=${encodeURIComponent(folderName)}`)
                .then(r => r.json())
                .then(data => {
                    document.getElementById('folderName').value = folderName;
                    document.getElementById('postTitle').value = data.post_title || '';
                    document.getElementById('postSummary').value = data.summary || '';
                    document.getElementById('postCta').value = data.cta || '';
                    document.getElementById('postHashtags').value = (data.hashtags || []).join(' ');
                    document.getElementById('editModal').classList.add('active');
                }).catch(e => showToast('Gagal mengambil data dari server.', 'error'));
        }

        function saveCaption() {
            const btn = document.getElementById('btnSave');
            const originalText = btn.innerHTML;
            btn.innerHTML = '<span class="material-icons-round" style="animation:spin 2s linear infinite;">sync</span> Menyimpan...';
            btn.disabled = true;

            const payload = {
                base_dir: selectedDir,
                folder_name: document.getElementById('folderName').value,
                meta: {
                    post_title: document.getElementById('postTitle').value,
                    summary: document.getElementById('postSummary').value,
                    cta: document.getElementById('postCta').value,
                    hashtags: document.getElementById('postHashtags').value.split(' ').filter(x => x.trim() !== '')
                }
            };

            fetch('/api/meta', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            }).then(r => r.json()).then(res => {
                if(res.success) {
                    closeModal('editModal');
                    location.reload();
                } else {
                    showToast('Gagal menyimpan caption: ' + res.error, 'error');
                    btn.innerHTML = originalText;
                    btn.disabled = false;
                }
            }).catch(e => {
                showToast('Terjadi kesalahan jaringan!', 'error');
                btn.innerHTML = originalText;
                btn.disabled = false;
            });
        }

        // VIEW MEDIA LOGIC
        let currentMediaIndex = 0;
        let currentMediaList = [];
        let currentMediaFolder = "";

        function viewMedia(folderName, mediaFiles) {
            const container = document.getElementById('mediaContainer');
            container.innerHTML = '';
            document.getElementById('mediaModalTitle').innerHTML = `<span class="material-icons-round" style="color:var(--accent);">photo_library</span> Media: ${folderName}`;
            
            if (!mediaFiles || mediaFiles.length === 0) {
                container.innerHTML = '<div style="color:white; text-align:center; padding:20px;">Tidak ada media yang valid.</div>';
                document.getElementById('mediaModal').classList.add('active');
                return;
            }
            
            currentMediaFolder = folderName;
            currentMediaList = mediaFiles;
            currentMediaIndex = 0;
            
            renderMediaIndex();
            document.getElementById('mediaModal').classList.add('active');
        }

        function renderMediaIndex() {
            const container = document.getElementById('mediaContainer');
            container.innerHTML = '';
            
            if (currentMediaList.length === 0) return;
            
            const file = currentMediaList[currentMediaIndex];
            const ext = file.split('.').pop().toLowerCase();
            const url = `/media?base=${encodeURIComponent(selectedDir)}&folder=${encodeURIComponent(currentMediaFolder)}&file=${encodeURIComponent(file)}`;
            
            const wrapper = document.createElement('div');
            wrapper.style.width = '100%';
            wrapper.style.textAlign = 'center';
            wrapper.style.marginBottom = '10px';
            wrapper.style.background = '#111';
            wrapper.style.padding = '10px';
            wrapper.style.borderRadius = '8px';
            
            const headerNav = document.createElement('div');
            headerNav.style.display = 'flex';
            headerNav.style.justifyContent = 'space-between';
            headerNav.style.alignItems = 'center';
            headerNav.style.width = '100%';
            headerNav.style.marginBottom = '12px';
            
            const btnPrev = document.createElement('button');
            btnPrev.className = 'btn-outline';
            btnPrev.innerHTML = '<span class="material-icons-round">chevron_left</span> Prev';
            btnPrev.disabled = currentMediaIndex === 0;
            btnPrev.onclick = () => { currentMediaIndex--; renderMediaIndex(); };
            
            const label = document.createElement('div');
            label.style.color = '#ccc';
            label.style.fontSize = '13px';
            label.innerText = `File ${currentMediaIndex + 1} of ${currentMediaList.length}`;
            
            const btnNext = document.createElement('button');
            btnNext.className = 'btn-outline';
            btnNext.innerHTML = 'Next <span class="material-icons-round">chevron_right</span>';
            btnNext.disabled = currentMediaIndex === currentMediaList.length - 1;
            btnNext.onclick = () => { currentMediaIndex++; renderMediaIndex(); };
            
            headerNav.appendChild(btnPrev);
            headerNav.appendChild(label);
            headerNav.appendChild(btnNext);
            
            wrapper.appendChild(headerNav);
            
            const fileLabel = document.createElement('div');
            fileLabel.style.color = '#888';
            fileLabel.style.fontSize = '12px';
            fileLabel.style.marginBottom = '8px';
            fileLabel.innerText = file;
            wrapper.appendChild(fileLabel);

            let el;
            if (['mp4', 'mov', 'avi'].includes(ext)) {
                el = document.createElement('video');
                el.src = url;
                el.controls = true;
                el.autoplay = true;
                el.className = 'media-item';
            } else {
                el = document.createElement('img');
                el.src = url;
                el.className = 'media-item';
            }
            wrapper.appendChild(el);
            container.appendChild(wrapper);
        }
    </script>
</body>
</html>
"""

def get_configured_folders():
    folders = {}
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r") as f:
                cfg = json.load(f)
                for k, v in cfg.items():
                    if isinstance(v, str) and os.path.isdir(v):
                        folders[f"Desktop Profile: {k}"] = v
        except: pass
    if os.path.exists("accounts.json"):
        try:
            with open("accounts.json", "r") as f:
                cfg = json.load(f)
                for k, v in cfg.items():
                    path = v.get("folder_path")
                    if path and os.path.isdir(path):
                        folders[f"Mobile Account: {k}"] = path
        except: pass
    return folders

def read_caption(f_path):
    meta_path = os.path.join(f_path, "post_meta.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as mf:
                meta = json.load(mf)
                parts = []
                if meta.get("post_title"): parts.append(meta.get("post_title"))
                if meta.get("summary"): parts.append(meta.get("summary"))
                if meta.get("cta"): parts.append(meta.get("cta"))
                if meta.get("hashtags"): 
                    tags = [f"#{t.lstrip('#')}" for t in meta.get("hashtags")]
                    parts.append(" ".join(tags))
                if parts: return " ".join(parts)
        except: pass
    return os.path.basename(f_path)

def build_queue(base_dir):
    if not base_dir or not os.path.exists(base_dir):
        return []
    
    pending_items = []
    uploaded_items = []
    
    for f in os.listdir(base_dir):
        if f == "queue_order.json": continue
        f_path = os.path.join(base_dir, f)
        if not os.path.isdir(f_path): continue
            
        marker = os.path.join(f_path, "uploadedfb.txt")
        media_files_full = [file for file in os.listdir(f_path) if file.lower().endswith((".mp4", ".mov", ".avi", ".jpg", ".png", ".jpeg", ".webp"))]
        
        if not media_files_full: continue
            
        media_files_sorted = sorted(media_files_full)
        is_video = any(m.lower().endswith((".mp4", ".mov", ".avi")) for m in media_files_full)
        caption = read_caption(f_path)
        first_media = media_files_sorted[0] if media_files_sorted else None
        
        item = {
            "name": f, "path": f_path, "ctime": os.path.getmtime(f_path),
            "type": "video" if is_video else "photo",
            "media_count": len(media_files_full),
            "media_files": media_files_sorted,
            "first_media": first_media,
            "caption": caption,
            "uploaded": os.path.exists(marker)
        }
        
        if item["uploaded"]:
            item["ctime"] = os.path.getmtime(marker)
            uploaded_items.append(item)
        else:
            pending_items.append(item)

    # Load custom order if exists
    order_path = os.path.join(base_dir, "queue_order.json")
    custom_order = []
    if os.path.exists(order_path):
        try:
            with open(order_path, "r", encoding="utf-8") as f:
                custom_order = json.load(f)
        except: pass
    
    if custom_order:
        # Sort pending items based on custom_order list
        order_map = {name: i for i, name in enumerate(custom_order)}
        pending_items.sort(key=lambda x: (order_map.get(x['name'], 999999), x['ctime']))
    else:
        pending_items.sort(key=lambda x: x['ctime'])

    uploaded_items.sort(key=lambda x: x['ctime'], reverse=True) # Terbaru di atas
    
    return pending_items + uploaded_items

@app.route("/")
def index():
    folders = get_configured_folders()
    selected_dir = request.args.get("base_dir", "")
    queue = build_queue(selected_dir) if selected_dir else []
    return render_template_string(HTML_TEMPLATE, folders=folders, selected_dir=selected_dir, queue=queue)

@app.route("/media")
def serve_media():
    base_dir = request.args.get("base")
    folder = request.args.get("folder")
    filename = request.args.get("file")
    
    if not base_dir or not folder or not filename:
        return "Missing params", 400
        
    file_path = os.path.join(base_dir, folder, filename)
    if os.path.exists(file_path):
        return send_from_directory(os.path.dirname(file_path), os.path.basename(file_path))
    return "Not found", 404

THUMB_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".thumb_cache")
os.makedirs(THUMB_CACHE_DIR, exist_ok=True)

@app.route("/thumbnail")
def serve_thumbnail():
    base_dir = request.args.get("base")
    folder = request.args.get("folder")
    filename = request.args.get("file")
    
    if not base_dir or not folder or not filename:
        return "Missing params", 400
        
    file_path = os.path.join(base_dir, folder, filename)
    if not os.path.exists(file_path):
        return "Not found", 404
        
    path_str = f"{base_dir}_{folder}_{filename}".encode('utf-8')
    thumb_name = hashlib.md5(path_str).hexdigest() + ".jpg"
    thumb_path = os.path.join(THUMB_CACHE_DIR, thumb_name)
    
    if os.path.exists(thumb_path):
        return send_file(thumb_path, mimetype='image/jpeg')
        
    try:
        ext = filename.split('.')[-1].lower()
        if ext in ['mp4', 'mov', 'avi']:
            cmd = ['ffmpeg', '-y', '-i', file_path, '-ss', '00:00:01.000', '-vframes', '1', '-vf', 'scale=320:-1', thumb_path]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if not os.path.exists(thumb_path):
                cmd = ['ffmpeg', '-y', '-i', file_path, '-vframes', '1', '-vf', 'scale=320:-1', thumb_path]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            with Image.open(file_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.thumbnail((320, 320))
                img.save(thumb_path, format='JPEG', quality=85)
                
        if os.path.exists(thumb_path):
            return send_file(thumb_path, mimetype='image/jpeg')
    except Exception as e:
        print(f"Error thumbnailing: {e}")
        pass
        
    return send_from_directory(os.path.dirname(file_path), os.path.basename(file_path))

@app.route("/api/delete", methods=["POST"])
def delete_api():
    data = request.json
    base_dir = data.get("base_dir")
    folder_name = data.get("folder_name")
    if base_dir and folder_name:
        path = os.path.join(base_dir, folder_name)
        if os.path.exists(path) and os.path.isdir(path):
            try:
                shutil.rmtree(path)
                return jsonify({"success": True})
            except Exception as e:
                return jsonify({"success": False, "error": str(e)})
    return jsonify({"success": False, "error": "Path tidak valid"})

@app.route("/api/meta", methods=["GET", "POST"])
def meta_api():
    if request.method == "GET":
        base_dir = request.args.get("base_dir")
        folder_name = request.args.get("folder_name")
        meta_path = os.path.join(base_dir, folder_name, "post_meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    return jsonify(json.load(f))
            except: pass
        return jsonify({})
    
    elif request.method == "POST":
        data = request.json
        base_dir = data.get("base_dir")
        folder_name = data.get("folder_name")
        meta = data.get("meta", {})
        
        if 'hashtags' in meta:
            meta['hashtags'] = [t.lstrip('#').strip() for t in meta['hashtags'] if t.strip()]

        if base_dir and folder_name:
            meta_path = os.path.join(base_dir, folder_name, "post_meta.json")
            try:
                with open(meta_path, 'w', encoding='utf-8') as f:
                    json.dump(meta, f, indent=4)
                return jsonify({"success": True})
            except Exception as e:
                return jsonify({"success": False, "error": str(e)})
        return jsonify({"success": False, "error": "Data atau path tidak valid"})

@app.route("/api/reorder", methods=["POST"])
def reorder_api():
    data = request.json
    base_dir = data.get("base_dir")
    order = data.get("order", [])
    
    if base_dir and order:
        try:
            # Try to update mtime first
            paths = [os.path.join(base_dir, f) for f in order]
            valid_paths = [p for p in paths if os.path.exists(p)]
            if valid_paths:
                try:
                    min_time = min(os.path.getmtime(p) for p in valid_paths)
                    for i, path in enumerate(valid_paths):
                        new_time = min_time + i
                        os.utime(path, (new_time, new_time))
                except:
                    pass # Ignore if utime fails on Android
            
            # Save order to a json file as fallback
            order_path = os.path.join(base_dir, "queue_order.json")
            with open(order_path, "w", encoding="utf-8") as f:
                json.dump(order, f)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
            
    return jsonify({"success": False, "error": "Invalid data"})

def find_free_port(start_port=5000):
    port = start_port
    while port < 6000:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
        port += 1
    return 5000 

if __name__ == "__main__":
    print("[*] Menyiapkan Web Dashboard...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except:
        ip = "127.0.0.1"
    
    port = find_free_port(5000)
    print(f"\\n[!] Web Dashboard berjalan di port {port}")
    print(f"[!] Buka browser di HP/PC Anda dan kunjungi: http://{ip}:{port}")
    if ip != "127.0.0.1":
        print(f"[!] Atau http://127.0.0.1:{port} (jika diakses dari HP yang sama)")
        
    app.run(host="0.0.0.0", port=port, debug=False)

