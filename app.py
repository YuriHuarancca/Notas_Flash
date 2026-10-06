import os
import sys

# Optimizar arranque de WebView2 (Chromium) desactivando servicios innecesarios para widget local
os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = (
    '--disable-background-networking '
    '--disable-background-timer-throttling '
    '--disable-breakpad '
    '--disable-component-update '
    '--disable-domain-reliability '
    '--disable-features=Translate,OptimizationHints,MediaRouter '
    '--disable-sync '
    '--no-default-browser-check '
    '--disable-search-engine-choice-screen'
)

import json
import re
import time
import threading
import socket
from datetime import datetime
import ctypes
from ctypes import wintypes
import webview

g_tray = None
IPC_PORT = 49281

def get_minimal_timestamp():
    return datetime.now().strftime("%d/%m · %H:%M")

# Configurar funciones Win32 seguras de 64 bits para evitar deadlocks entre hilos
user32 = ctypes.windll.user32
user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, wintypes.INT, wintypes.INT,
    wintypes.INT, wintypes.INT, wintypes.UINT
]
user32.SetWindowPos.restype = wintypes.BOOL

user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL

user32.ShowWindow.argtypes = [wintypes.HWND, wintypes.INT]
user32.ShowWindow.restype = wintypes.BOOL

user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = wintypes.LPARAM

user32.ReleaseCapture.argtypes = []
user32.ReleaseCapture.restype = wintypes.BOOL

user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND

user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL

user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL

user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL

# Constantes Win32
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9

def try_send_to_existing_instance(args):
    """Verifica si ya existe una instancia activa en segundo plano. Si existe, le envia la orden y retorna True."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.35)
        s.connect(('127.0.0.1', IPC_PORT))
        req = {'magic': 'WIDGET_NOTAS_WIN11', 'action': 'open', 'args': list(args)}
        s.sendall(json.dumps(req).encode('utf-8'))
        ack = s.recv(1024).decode('utf-8')
        s.close()
        if ack == 'OK':
            return True
    except Exception:
        pass
    return False

def start_ipc_server(api):
    """Inicia el servidor local IPC para recibir peticiones de nuevas aperturas en 0.01 segundos."""
    def server_loop():
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(('127.0.0.1', IPC_PORT))
            srv.listen(5)
            while True:
                conn, _ = srv.accept()
                try:
                    raw = conn.recv(65536).decode('utf-8')
                    if raw:
                        payload = json.loads(raw)
                        if payload.get('magic') == 'WIDGET_NOTAS_WIN11':
                            conn.sendall(b'OK')
                            args = payload.get('args', [])
                            file_cand = args[0] if args and args[0] else None
                            threading.Thread(target=api.show_and_activate, args=(file_cand,), daemon=True).start()
                except Exception as e:
                    print(f"IPC error: {e}")
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass
        except Exception as e:
            print(f"IPC server bind error: {e}")
    threading.Thread(target=server_loop, daemon=True).start()

def get_resource_path(relative_path):
    """Obtiene la ruta absoluta al recurso, compatible con PyInstaller (_MEIPASS) y ejecución directa."""
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

# Directorio de datos de usuario en AppData
APPDATA_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'win11-widget-notes')
os.makedirs(APPDATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(APPDATA_DIR, 'widget-data.json')
RECOVERY_FILE = os.path.join(APPDATA_DIR, 'widget-recovery.json')
EMERGENCY_BACKUP_HTML = os.path.join(APPDATA_DIR, 'ultimo-respaldo-seguridad.html')
BACKUP_DIR = os.path.join(APPDATA_DIR, 'backups')
os.makedirs(BACKUP_DIR, exist_ok=True)

def make_safety_backup(content, title, file_path=None):
    """Crea una copia de seguridad timestamped e inmutable de la nota en segundo plano."""
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = "".join(c for c in (title or 'nota') if c.isalnum() or c in (' ', '_', '-')).strip()
        fname = f"backup_{ts}_{slug[:25]}.html"
        full_path = os.path.join(BACKUP_DIR, fname)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(f"<!-- Respaldo de seguridad automatico: {datetime.now()} | Archivo: {file_path or 'Widget'} -->\n")
            f.write(f"<h2>{escape_html(title or 'Nota')}</h2>\n")
            f.write(f"<div>{content or ''}</div>\n")
        # Mantener historial de maximo 25 copias
        items = sorted(os.listdir(BACKUP_DIR))
        if len(items) > 25:
            for old in items[:-25]:
                try:
                    os.remove(os.path.join(BACKUP_DIR, old))
                except Exception:
                    pass
    except Exception as e:
        print(f"Error creating safety backup: {e}")

SPANISH_MONTHS = {
    1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun',
    7: 'Jul', 8: 'Ago', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic'
}

def get_documents_dir():
    """Obtiene la ruta a la carpeta Documentos del usuario en Windows."""
    try:
        CSIDL_PERSONAL = 5
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        res = ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, 0, buf)
        if res == 0 and buf.value and os.path.exists(buf.value):
            return buf.value
    except Exception:
        pass
    docs = os.path.join(os.environ.get('USERPROFILE', os.path.expanduser('~')), 'Documents')
    if os.path.exists(docs):
        return docs
    doc_es = os.path.join(os.environ.get('USERPROFILE', os.path.expanduser('~')), 'Documentos')
    if os.path.exists(doc_es):
        return doc_es
    return os.path.expanduser('~')

def get_notes_folder():
    """Obtiene la carpeta Documentos/[Mes Año] (ej. 'Documents/Oct 2026') creándola si no existe."""
    docs = get_documents_dir()
    now = datetime.now()
    m_name = SPANISH_MONTHS.get(now.month, 'Ene')
    folder_name = f"{m_name} {now.year}"
    target = os.path.join(docs, folder_name)
    try:
        os.makedirs(target, exist_ok=True)
    except Exception as e:
        print(f"Error creando carpeta de notas: {e}")
        return docs
    return target

EXAMPLE_CONTENT = (
    '<h2>Mi Widget de Notas</h2>'
    '<p>Bienvenido a tu editor para el escritorio de Windows 11.</p>'
    '<ul><li>Haz listas con viñetas</li><li>Organiza tus ideas</li></ul>'
    '<ol><li>Primer paso importante</li><li>Segundo paso del día</li></ol>'
    '<ul class="task-list">'
    '<li data-checked="false">Nueva tarea por hacer (haz clic para marcar)</li>'
    '<li data-checked="true">Tarea completada</li>'
    '</ul>'
    '<p>Usa el botón de anclaje para mantenerlo siempre visible en pantalla.</p>'
)

DEFAULT_DATA = {
    'content': '',
    'title': get_minimal_timestamp(),
    'alwaysOnTop': True,
    'theme': 'theme-dark-mica',
    'opacity': 0.95,
    'fontSize': 15.0,
    'first_launch_done': False,
    'bounds': {
        'width': 330,
        'height': 330,
        'x': None,
        'y': None
    }
}

def load_data():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                if saved.get('fontSize') in (13.5, '13.5', None):
                    saved['fontSize'] = 15.0
                saved['alwaysOnTop'] = True

                # Si es la primera apertura, mostrar el texto de ejemplo y marcar first_launch_done
                if not saved.get('first_launch_done', False):
                    saved['content'] = EXAMPLE_CONTENT
                    saved['first_launch_done'] = True
                    try:
                        with open(DATA_FILE, 'w', encoding='utf-8') as wf:
                            json.dump(saved, wf, indent=2, ensure_ascii=False)
                    except Exception:
                        pass

                return {**DEFAULT_DATA, **saved}
    except Exception as e:
        print(f"Error cargando datos: {e}")

    # Si el archivo no existía en absoluto (primera apertura)
    first_data = {
        **DEFAULT_DATA,
        'content': EXAMPLE_CONTENT,
        'title': get_minimal_timestamp(),
        'first_launch_done': True
    }
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(first_data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
    return first_data

def save_data(data):
    try:
        if not data:
            return
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                current = json.load(f)
        else:
            current = {**DEFAULT_DATA}
        current.update(data)
        current['first_launch_done'] = True
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error guardando datos: {e}")

def escape_html(text):
    return (str(text)
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&#039;'))

def write_note_to_file(file_path, note_data, chosen_title=None):
    """Guarda directamente el contenido formateado de una nota en disco segun su extension."""
    ext = os.path.splitext(file_path)[1].lower()
    file_name = os.path.basename(file_path)
    if not chosen_title:
        chosen_title = os.path.splitext(file_name)[0]

    if ext == '.txt':
        raw_html = note_data.get('content', '')
        clean_text = re.sub(r'<br\s*/?>', '\n', raw_html, flags=re.IGNORECASE)
        clean_text = re.sub(r'</p>', '\n', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'</li>', '\n', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'<[^>]+>', '', clean_text)
        clean_text = clean_text.strip()
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"{chosen_title}\n{'=' * len(chosen_title)}\n\n{clean_text}\n")
    elif ext in ('.html', '.htm') or ext not in ('.w11note', '.json'):
        meta_json = json.dumps({
            'version': '1.0',
            'title': chosen_title,
            'content': note_data.get('content', ''),
            'theme': note_data.get('theme', 'theme-dark-mica'),
            'fontSize': note_data.get('fontSize', 15.0)
        }, ensure_ascii=False)

        html_content = (
            "<!DOCTYPE html>\n"
            "<html lang='es'>\n"
            "<head>\n"
            "  <meta charset='UTF-8'>\n"
            "  <meta name='viewport' content='width=device-width, initial-scale=1.0'>\n"
            f"  <title>{chosen_title}</title>\n"
            "  <style>\n"
            "    :root { font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; }\n"
            "    body { font-family: inherit; background: #1c1e27; color: #f0f3f8; margin: 0; padding: 2rem 1rem; line-height: 1.6; }\n"
            "    .document-card { max-width: 760px; margin: 0 auto; background: rgba(36, 39, 50, 0.95); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 28px; box-shadow: 0 12px 32px rgba(0, 0, 0, 0.4); }\n"
            "    .note-header { border-bottom: 2px solid #0078d4; padding-bottom: 10px; margin-bottom: 20px; }\n"
            "    .note-title { margin: 0; font-size: 1.6rem; font-weight: 700; color: #ffffff; }\n"
            "    .note-body { font-size: 14px; color: #e4e7ee; }\n"
            "    .note-body h1, .note-body h2, .note-body h3 { color: #60cdff; margin-top: 1.1em; margin-bottom: 0.4em; }\n"
            "    .note-body p { margin: 0.5em 0; }\n"
            "    .note-body ul, .note-body ol { padding-left: 24px; margin: 0.5em 0; }\n"
            "    .note-body li { margin: 4px 0; }\n"
            "    ul.task-list { list-style: none !important; padding-left: 0 !important; }\n"
            "    ul.task-list li[data-checked='true'] { color: #8a90a0; text-decoration: none; opacity: 0.65; }\n"
            "    ul.task-list li[data-checked='true']::before { content: '☑'; color: #107c41; font-weight: bold; font-size: 16px; margin-right: 6px; }\n"
            "    ul.task-list li[data-checked='false']::before { content: '☐'; color: #8a90a0; font-weight: bold; font-size: 16px; margin-right: 6px; }\n"
            "    img { max-width: 100%; height: auto; border-radius: 8px; margin: 10px auto; display: block; }\n"
            "    @media print { body { background: #ffffff; color: #111111; padding: 0; } .document-card { box-shadow: none; border: none; padding: 0; } }\n"
            "  </style>\n"
            f"  <script type='application/json' id='w11note-data'>{meta_json}</script>\n"
            "</head>\n"
            "<body>\n"
            "  <div class='document-card'>\n"
            "    <div class='note-header'>\n"
            f"      <h1 class='note-title'>{chosen_title}</h1>\n"
            "    </div>\n"
            f"    <div class='note-body'>{note_data.get('content', '')}</div>\n"
            "  </div>\n"
            "</body>\n"
            "</html>"
        )
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
    else:
        payload = {
            'version': '1.0',
            'title': chosen_title,
            'content': note_data.get('content', ''),
            'theme': note_data.get('theme', 'theme-dark-mica'),
            'fontSize': note_data.get('fontSize', 15.0)
        }
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

class JsApi:
    def __init__(self):
        self._window = None
        self._is_pinned = True
        self._opened_file_data = None
        self._current_file_path = None
        self._is_dirty = False
        self._is_visible = True

    def set_dirty(self, state):
        self._is_dirty = bool(state)
        return True

    def is_dirty(self):
        return getattr(self, '_is_dirty', False)

    def set_current_file_path(self, path):
        self._current_file_path = path or None
        return True

    def direct_save_file(self, note_data):
        file_path = note_data.get('filePath') or getattr(self, '_current_file_path', None)
        if not file_path:
            return self.export_file(note_data)
        try:
            write_note_to_file(file_path, note_data)
            self._current_file_path = file_path
            self._is_dirty = False
            self.mark_clean_exit()
            make_safety_backup(note_data.get('content', ''), note_data.get('title', ''), file_path)
            file_name = os.path.basename(file_path)
            title = os.path.splitext(file_name)[0]
            return {
                'success': True,
                'filePath': file_path,
                'fileName': file_name,
                'title': title
            }
        except Exception as e:
            print(f"Error direct saving: {e}")
            return {'success': False, 'error': str(e)}

    def save_recovery_snapshot(self, data):
        try:
            if not data:
                return False
            payload = {
                'content': data.get('content', ''),
                'title': data.get('title', ''),
                'filePath': data.get('filePath') or getattr(self, '_current_file_path', None),
                'theme': data.get('theme', 'theme-dark-mica'),
                'fontSize': data.get('fontSize', 15.0),
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'timestampReadable': datetime.now().strftime("%d/%m · %H:%M"),
                'isDirty': True,
                'cleanExit': False
            }
            with open(RECOVERY_FILE, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

            # Guardar copia de seguridad histórica inmutable
            clean_text = re.sub(r'<[^>]+>', '', payload['content']).strip()
            if len(clean_text) > 0:
                make_safety_backup(payload['content'], payload['title'], payload['filePath'])

            # Respaldo HTML directo legible
            try:
                with open(EMERGENCY_BACKUP_HTML, 'w', encoding='utf-8') as hf:
                    hf.write(
                        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
                        f"<title>{payload['title']}</title></head><body>"
                        f"<h1>{payload['title']}</h1>"
                        f"<p><small>Respaldo de seguridad: {payload['timestamp']}</small></p>"
                        f"<div class='note-body'>{payload['content']}</div>"
                        "</body></html>"
                    )
            except Exception:
                pass
            return True
        except Exception as e:
            print(f"Error guardando snapshot de recuperacion: {e}")
            return False

    def check_recovery_snapshot(self):
        try:
            if os.path.exists(RECOVERY_FILE):
                with open(RECOVERY_FILE, 'r', encoding='utf-8') as f:
                    rec = json.load(f)
                if rec and rec.get('isDirty') and not rec.get('cleanExit'):
                    raw_content = rec.get('content', '')
                    clean_text = re.sub(r'<[^>]+>', '', raw_content).strip()
                    if len(clean_text) > 0:
                        return rec
        except Exception as e:
            print(f"Error comprobando recuperacion: {e}")
        return None

    def mark_clean_exit(self):
        try:
            if os.path.exists(RECOVERY_FILE):
                with open(RECOVERY_FILE, 'r', encoding='utf-8') as f:
                    rec = json.load(f)
                rec['cleanExit'] = True
                rec['isDirty'] = False
                with open(RECOVERY_FILE, 'w', encoding='utf-8') as f:
                    json.dump(rec, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def discard_recovery_snapshot(self):
        try:
            if os.path.exists(RECOVERY_FILE):
                os.remove(RECOVERY_FILE)
            return True
        except Exception:
            return False

    def set_window(self, window):
        self._window = window

    def _get_hwnd(self):
        try:
            if self._window:
                from webview.platforms.winforms import BrowserView
                instance = BrowserView.instances.get(self._window.uid)
                if instance and hasattr(instance, 'Handle'):
                    return instance.Handle.ToInt64()
        except Exception:
            pass
        try:
            return user32.FindWindowW(None, 'Widget de Notas Windows 11')
        except Exception:
            return None

    def window_ready(self):
        self._uncloak_window()
        return True

    def _uncloak_window(self):
        hwnd = self._get_hwnd()
        if hwnd:
            try:
                # DWMWA_CLOAK = 13 -> 0 (desenmascarar ventana de forma instantánea sin cuadros vacíos)
                val = ctypes.c_int(0)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 13, ctypes.byref(val), 4)
            except Exception:
                pass

    def _read_file_content(self, file_path):
        try:
            if not os.path.isfile(file_path):
                return None
            ext = os.path.splitext(file_path)[1].lower()
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                raw = f.read()

            if ext == '.txt':
                lines = raw.splitlines()
                html_body = "".join(f"<p>{escape_html(l) if l.strip() else '<br>'}</p>" for l in lines)
                title = os.path.splitext(os.path.basename(file_path))[0]
                return {
                    'title': title,
                    'content': html_body or '<p><br></p>',
                    'theme': 'theme-dark-mica',
                    'fontSize': 15.0,
                    'filePath': file_path
                }
            elif ext in ('.html', '.htm'):
                meta_match = re.search(r'<script[^>]*id=[\'"]w11note-data[\'"][^>]*>(.*?)</script>', raw, re.DOTALL | re.IGNORECASE)
                if meta_match:
                    try:
                        parsed = json.loads(meta_match.group(1))
                        return {
                            'title': parsed.get('title', os.path.splitext(os.path.basename(file_path))[0]),
                            'content': parsed.get('content', ''),
                            'theme': parsed.get('theme', 'theme-dark-mica'),
                            'fontSize': parsed.get('fontSize', 15.0),
                            'filePath': file_path
                        }
                    except Exception:
                        pass
                title_match = re.search(r'<title>(.*?)</title>', raw, re.IGNORECASE)
                title = title_match.group(1) if title_match else os.path.splitext(os.path.basename(file_path))[0]
                body_match = re.search(r'<div[^>]*class=[\'"][^\'"]*note-body[^\'"]*[\'"][^>]*>(.*?)</div>\s*</div>\s*</body>', raw, re.DOTALL | re.IGNORECASE)
                if not body_match:
                    body_match = re.search(r'<body[^>]*>(.*?)</body>', raw, re.DOTALL | re.IGNORECASE)
                content = body_match.group(1) if body_match else raw
                return {'title': title, 'content': content, 'theme': 'theme-dark-mica', 'fontSize': 15.0, 'filePath': file_path}
            else:
                parsed = json.loads(raw)
                return {
                    'title': parsed.get('title', os.path.splitext(os.path.basename(file_path))[0]),
                    'content': parsed.get('content', ''),
                    'theme': parsed.get('theme', 'theme-dark-mica'),
                    'fontSize': parsed.get('fontSize', 15.0),
                    'filePath': file_path
                }
        except Exception as e:
            print(f"Error leyendo archivo {file_path}: {e}")
            return None

    def get_initial_data(self):
        if getattr(self, '_opened_file_data', None):
            data = dict(self._opened_file_data)
            data['alwaysOnTop'] = getattr(self, '_is_pinned', True)
            data['first_launch_done'] = True
            self._current_file_path = data.get('filePath')
            return data
        data = load_data()
        data['alwaysOnTop'] = getattr(self, '_is_pinned', data.get('alwaysOnTop', True))
        return data

    def save_data(self, data):
        save_data(data)
        return True

    def toggle_pin(self, state=None):
        if state is None:
            new_state = not getattr(self, '_is_pinned', True)
        else:
            new_state = bool(state)
        self._is_pinned = new_state
        self._apply_pin(new_state)
        save_data({'alwaysOnTop': new_state})
        return new_state

    def _apply_pin(self, on_top):
        hwnd = self._get_hwnd()
        if hwnd:
            target = HWND_TOPMOST if on_top else HWND_NOTOPMOST
            flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
            if getattr(self, '_is_visible', True):
                flags |= SWP_SHOWWINDOW
            user32.SetWindowPos(hwnd, target, 0, 0, 0, 0, flags)

    def get_window_rect(self):
        hwnd = self._get_hwnd()
        if hwnd:
            rect = wintypes.RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return {
                    'x': rect.left,
                    'y': rect.top,
                    'width': rect.right - rect.left,
                    'height': rect.bottom - rect.top
                }
        return None

    def set_window_position(self, pos):
        x = int(pos.get('x', 0))
        y = int(pos.get('y', 0))
        hwnd = self._get_hwnd()
        if hwnd:
            user32.SetWindowPos(hwnd, 0, x, y, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
        return True

    def set_window_geometry(self, geom):
        x = int(geom.get('x', 0))
        y = int(geom.get('y', 0))
        w = max(260, int(geom.get('width', 300)))
        h = max(44 if getattr(self, '_is_compact', False) else 140, int(geom.get('height', 200)))
        hwnd = self._get_hwnd()
        if hwnd:
            user32.SetWindowPos(hwnd, 0, x, y, w, h, SWP_NOZORDER | SWP_NOACTIVATE)
        return True

    def move_step(self, delta):
        dx = int(delta.get('deltaX', 0))
        dy = int(delta.get('deltaY', 0))
        if dx == 0 and dy == 0:
            return True
        hwnd = self._get_hwnd()
        if hwnd:
            rect = wintypes.RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                new_x = rect.left + dx
                new_y = rect.top + dy
                user32.SetWindowPos(hwnd, 0, new_x, new_y, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
        return True

    def resize_step(self, delta):
        direction = delta.get('direction', 'bottom-right')
        dx = int(delta.get('deltaX', 0))
        dy = int(delta.get('deltaY', 0))
        hwnd = self._get_hwnd()
        if not hwnd:
            return

        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return

        cur_x = rect.left
        cur_y = rect.top
        cur_w = rect.right - rect.left
        cur_h = rect.bottom - rect.top

        min_w = 260
        min_h = 44 if getattr(self, '_is_compact', False) else 140

        new_x = cur_x
        new_y = cur_y
        new_w = cur_w
        new_h = cur_h

        # Redimensionamiento horizontal
        if 'right' in direction:
            new_w = max(min_w, cur_w + dx)
        elif 'left' in direction:
            candidate_w = cur_w - dx
            if candidate_w >= min_w:
                new_w = candidate_w
                new_x = rect.right - new_w
            else:
                new_w = min_w
                new_x = rect.right - min_w

        # Redimensionamiento vertical
        if 'bottom' in direction:
            new_h = max(min_h, cur_h + dy)
        elif 'top' in direction:
            candidate_h = cur_h - dy
            if candidate_h >= min_h:
                new_h = candidate_h
                new_y = rect.bottom - new_h
            else:
                new_h = min_h
                new_y = rect.bottom - min_h

        # Aplicar cambio de tamaño y posición de forma atómica en Win32
        if new_x != cur_x or new_y != cur_y:
            user32.SetWindowPos(hwnd, 0, new_x, new_y, new_w, new_h, SWP_NOZORDER | SWP_NOACTIVATE)
        elif new_w != cur_w or new_h != cur_h:
            user32.SetWindowPos(hwnd, 0, 0, 0, new_w, new_h, SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE)

    def toggle_compact_mode(self, is_compact):
        hwnd = self._get_hwnd()
        if hwnd:
            rect = wintypes.RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                current_w = rect.right - rect.left
                current_h = rect.bottom - rect.top
                dpi = user32.GetDpiForWindow(hwnd) if hasattr(user32, 'GetDpiForWindow') else 96
                scale = (dpi / 96.0) if dpi else 1.0

                if is_compact:
                    self._pre_compact_height = current_h
                    target_h = int(44 * scale)
                    user32.SetWindowPos(hwnd, 0, 0, 0, current_w, target_h, SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE)
                    return {'isCompact': True, 'targetHeight': target_h}
                else:
                    restore_h = getattr(self, '_pre_compact_height', None)
                    if not restore_h or restore_h <= int(60 * scale):
                        restore_h = int(520 * scale)
                    user32.SetWindowPos(hwnd, 0, 0, 0, current_w, restore_h, SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE)
                    return {'isCompact': False, 'targetHeight': restore_h}
        return {'isCompact': is_compact}

    def _get_dpi_scale(self):
        hwnd = self._get_hwnd()
        if hwnd and hasattr(user32, 'GetDpiForWindow'):
            dpi = user32.GetDpiForWindow(hwnd)
            return (dpi / 96.0) if dpi else 1.0
        return 1.0

    def save_window_position(self):
        hwnd = self._get_hwnd()
        if hwnd:
            rect = wintypes.RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                scale = self._get_dpi_scale()
                w = max(240, int((rect.right - rect.left) / scale))
                h = max(240, int((rect.bottom - rect.top) / scale))
                x = int(rect.left / scale)
                y = int(rect.top / scale)
                save_data({
                    'bounds': {
                        'x': x,
                        'y': y,
                        'width': w,
                        'height': h
                    }
                })

    def minimize(self):
        hwnd = self._get_hwnd()
        if hwnd:
            user32.ShowWindow(hwnd, SW_MINIMIZE)
        elif self._window:
            self._window.minimize()

    def hide_window(self):
        self.save_window_position()
        hwnd = self._get_hwnd()
        if hwnd:
            user32.ShowWindow(hwnd, SW_HIDE)
        elif self._window:
            self._window.hide()
        self._is_visible = False

    def close(self):
        # Al hacer clic en X, ocultar en segundo plano para apertura inmediata (< 0.05s)
        self.hide_window()

    def is_window_visible(self):
        hwnd = self._get_hwnd()
        if hwnd:
            return bool(user32.IsWindowVisible(hwnd))
        return getattr(self, '_is_visible', True)

    def toggle_visibility(self):
        if self.is_window_visible():
            self.hide_window()
        else:
            self.show_and_activate()

    def show_and_activate(self, file_cand=None):
        self._is_visible = True
        hwnd = self._get_hwnd()
        if hwnd:
            try:
                cur_fore = user32.GetForegroundWindow()
                cur_thread = user32.GetWindowThreadProcessId(cur_fore, None) if cur_fore else 0
                app_thread = user32.GetWindowThreadProcessId(hwnd, None)
                if cur_thread and app_thread and cur_thread != app_thread:
                    user32.AttachThreadInput(cur_thread, app_thread, True)
                    user32.ShowWindow(hwnd, SW_RESTORE)
                    user32.ShowWindow(hwnd, SW_SHOW)
                    user32.BringWindowToTop(hwnd)
                    user32.SetForegroundWindow(hwnd)
                    user32.AttachThreadInput(cur_thread, app_thread, False)
                else:
                    user32.ShowWindow(hwnd, SW_RESTORE)
                    user32.ShowWindow(hwnd, SW_SHOW)
                    user32.BringWindowToTop(hwnd)
                    user32.SetForegroundWindow(hwnd)
            except Exception:
                user32.ShowWindow(hwnd, SW_SHOW)
                user32.SetForegroundWindow(hwnd)

            self._apply_pin(getattr(self, '_is_pinned', True))
            self._uncloak_window()

        if self._window:
            if file_cand and os.path.isfile(file_cand):
                norm_cand = os.path.normcase(os.path.abspath(file_cand))
                cur_norm = os.path.normcase(os.path.abspath(self._current_file_path)) if getattr(self, '_current_file_path', None) else None
                if cur_norm and cur_norm == norm_cand:
                    # El archivo ya esta abierto en esta misma ventana
                    self._window.evaluate_js("window.notifyAlreadyOpen && window.notifyAlreadyOpen();")
                else:
                    note_data = self._read_file_content(file_cand)
                    if note_data:
                        self._window.evaluate_js(f"window.requestOpenFile && window.requestOpenFile({json.dumps(note_data)});")

            self._window.evaluate_js("window.triggerEntranceAnimation && window.triggerEntranceAnimation();")

    def new_blank_note(self):
        self._current_file_path = None
        self.show_and_activate()
        if self._window:
            self._window.evaluate_js("window.newBlankNote && window.newBlankNote();")

    def full_exit(self):
        self.mark_clean_exit()
        global g_tray
        if g_tray:
            try:
                g_tray.Visible = False
                g_tray.Dispose()
            except Exception:
                pass
        self.save_window_position()
        if self._window:
            self._window.destroy()
        os._exit(0)

    def export_file(self, note_data):
        if not self._window:
            return {'success': False, 'error': 'No window'}
        raw_title = (note_data.get('title') or '').strip()
        now = datetime.now()
        timestamp_slug = now.strftime('%d-%m_%H-%M')

        # Si el usuario no escribió un nombre específico, prellenar con fecha y hora por defecto
        if not raw_title or raw_title in ('Notas Rápidas', 'Notas Rapidas', '--/-- · --:--') or ('/' in raw_title and '·' in raw_title):
            suggested_name = f"Nota_{timestamp_slug}"
            display_title = now.strftime("%d/%m · %H:%M")
        else:
            safe_title = raw_title.replace('/', '-').replace(':', '-').replace('·', '_')
            safe_title = "".join(c for c in safe_title if c.isalnum() or c in (' ', '_', '-')).strip()
            suggested_name = safe_title or f"Nota_{timestamp_slug}"
            display_title = raw_title

        default_filename = f"{suggested_name}.html"
        target_folder = get_notes_folder()

        save_dialog_flag = getattr(webview, 'FileDialog', None) and getattr(webview.FileDialog, 'SAVE', webview.SAVE_DIALOG) or webview.SAVE_DIALOG
        result = self._window.create_file_dialog(
            save_dialog_flag,
            directory=target_folder,
            save_filename=default_filename,
            file_types=(
                'Documento Web HTML (*.html)',
                'Documento de Texto Plano (*.txt)',
                'Nota de Widget (*.w11note)',
                'Todos los archivos (*.*)'
            )
        )

        if not result:
            return {'success': False, 'canceled': True}

        file_path = result if isinstance(result, str) else result[0]
        try:
            file_name = os.path.basename(file_path)
            folder_path = os.path.dirname(file_path)
            chosen_title = os.path.splitext(file_name)[0]

            write_note_to_file(file_path, note_data, chosen_title=chosen_title)

            self._current_file_path = file_path
            self._is_dirty = False
            self.mark_clean_exit()
            make_safety_backup(note_data.get('content', ''), chosen_title, file_path)

            return {
                'success': True,
                'filePath': file_path,
                'fileName': file_name,
                'folder': folder_path,
                'title': chosen_title
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def import_file(self):
        if not self._window:
            return {'success': False, 'error': 'No window'}
        target_folder = get_notes_folder()
        open_dialog_flag = getattr(webview, 'FileDialog', None) and getattr(webview.FileDialog, 'OPEN', webview.OPEN_DIALOG) or webview.OPEN_DIALOG
        result = self._window.create_file_dialog(
            open_dialog_flag,
            directory=target_folder,
            allow_multiple=False,
            file_types=(
                'Notas Compatibles (*.html;*.htm;*.txt;*.w11note;*.json)',
                'Documento Web HTML (*.html;*.htm)',
                'Documento de Texto Plano (*.txt)',
                'Nota de Widget (*.w11note;*.json)',
                'Todos los archivos (*.*)'
            )
        )
        if not result:
            return {'success': False, 'canceled': True}
        file_path = result if isinstance(result, str) else result[0]
        data = self._read_file_content(file_path)
        if data:
            self._current_file_path = file_path
            return {'success': True, 'data': data}
        return {'success': False, 'error': 'No se pudo leer el archivo'}

def main():
    # 1. Comprobar si ya existe una instancia activa en segundo plano (arranque instantáneo < 0.05s)
    if try_send_to_existing_instance(sys.argv[1:]):
        sys.exit(0)

    api = JsApi()

    # Iniciar servidor local IPC para recibir llamadas de nuevas aperturas
    start_ipc_server(api)

    # Comprobar si se abrió en modo oculto explícito o con un archivo
    start_hidden = any(arg.lower() in ('--hidden', '-h') for arg in sys.argv)
    api._is_visible = not start_hidden
    cli_files = [arg for arg in sys.argv[1:] if not arg.startswith('-')]
    if cli_files:
        cand = cli_files[0].strip('\"')
        if os.path.isfile(cand):
            file_data = api._read_file_content(cand)
            if file_data:
                api._opened_file_data = file_data
                api._current_file_path = cand
                start_hidden = False
                api._is_visible = True

    saved = load_data()

    # Obtener resolución de pantalla para tamaño inicial de 1/4 ancho y 1/3 altura, centrado
    try:
        screens = webview.screens
        if screens and len(screens) > 0:
            sw = screens[0].width
            sh = screens[0].height
        else:
            sw = user32.GetSystemMetrics(0) or 1536
            sh = user32.GetSystemMetrics(1) or 864
    except Exception:
        sw = user32.GetSystemMetrics(0) or 1536
        sh = user32.GetSystemMetrics(1) or 864

    side = 500
    width = side
    height = side
    cx = max(0, (sw - side) // 2)
    cy = max(0, (sh - side) // 2)
    x = cx
    y = cy

    has_custom_pos = False
    if saved and isinstance(saved.get('bounds'), dict):
        b = saved['bounds']
        bw = b.get('width')
        bh = b.get('height')
        if bw and bh and 260 <= bw <= 520 and 260 <= bh <= 520:
            width = int(bw)
            height = int(bh)
        if b.get('x') is not None and b.get('y') is not None:
            cand_x = int(b['x'])
            cand_y = int(b['y'])
            if 40 <= cand_x <= (sw - width - 40) and 40 <= cand_y <= (sh - height - 40):
                x = cand_x
                y = cand_y
                has_custom_pos = True

    on_top = saved.get('alwaysOnTop', True) if saved else True
    api._is_pinned = on_top

    html_file = get_resource_path('index.html')
    file_url = 'file:///' + os.path.abspath(html_file).replace('\\', '/')

    window = webview.create_window(
        title='Widget de Notas Windows 11',
        url=file_url,
        js_api=api,
        width=width,
        height=height,
        x=x,
        y=y,
        min_size=(200, 30),
        frameless=True,
        hidden=start_hidden,
        easy_drag=False,
        shadow=True,
        transparent=False,
        on_top=on_top,
        resizable=True,
        text_select=True,
        background_color='#1c1e27'
    )
    api.set_window(window)

    def on_before_show():
        hwnd = api._get_hwnd()
        if hwnd:
            try:
                # Asegurar que el compositor no oculte la superficie DirectComposition
                val = ctypes.c_int(0)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 13, ctypes.byref(val), 4)
            except Exception:
                pass

    window.events.before_show += on_before_show

    def on_loaded():
        api._apply_pin(on_top)
        api._uncloak_window()
        hwnd = api._get_hwnd()
        if hwnd:
            try:
                # Activar la sombra nativa densa CS_DROPSHADOW
                GCL_STYLE = -26
                CS_DROPSHADOW = 0x00020000
                if hasattr(user32, 'SetClassLongPtrW'):
                    user32.SetClassLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
                    user32.SetClassLongPtrW.restype = ctypes.c_void_p
                    user32.GetClassLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
                    user32.GetClassLongPtrW.restype = ctypes.c_void_p
                    cur = user32.GetClassLongPtrW(hwnd, GCL_STYLE)
                    user32.SetClassLongPtrW(hwnd, GCL_STYLE, (cur or 0) | CS_DROPSHADOW)
                else:
                    cur_cls = user32.GetClassLongW(hwnd, GCL_STYLE)
                    user32.SetClassLongW(hwnd, GCL_STYLE, cur_cls | CS_DROPSHADOW)
            except Exception:
                pass
            try:
                # Extender marco DWM y forzar esquinas redondeadas
                class MARGINS(ctypes.Structure):
                    _fields_ = [
                        ('cxLeftWidth', ctypes.c_int),
                        ('cxRightWidth', ctypes.c_int),
                        ('cyTopHeight', ctypes.c_int),
                        ('cyBottomHeight', ctypes.c_int)
                    ]
                m = MARGINS(1, 1, 1, 1)
                ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(m))
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 2, ctypes.byref(ctypes.c_int(2)), 4)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 30, ctypes.byref(ctypes.c_int(2)), 4)
            except Exception:
                pass

        if not has_custom_pos:
            try:
                window.resize(side, side)
            except Exception:
                pass

        # Inicializar icono en bandeja del sistema (System Tray) para segundo plano
        global g_tray
        try:
            import clr
            clr.AddReference('System.Windows.Forms')
            clr.AddReference('System.Drawing')
            from System.Windows.Forms import (  # type: ignore
                NotifyIcon,
                ContextMenuStrip,
                ToolStripMenuItem,
                ToolStripSeparator,
                MouseButtons
            )
            from System.Drawing import Icon  # type: ignore

            g_tray = NotifyIcon()
            icon_file = get_resource_path('icon.ico')
            if os.path.exists(icon_file):
                g_tray.Icon = Icon(icon_file)
            g_tray.Text = "Widget de Notas (Clic para abrir)"
            g_tray.Visible = True

            tray_menu = ContextMenuStrip()
            m_show = ToolStripMenuItem("Abrir Widget de Notas")
            m_show.Click += lambda s, e: api.show_and_activate()

            m_new = ToolStripMenuItem("Nueva nota en blanco")
            m_new.Click += lambda s, e: api.new_blank_note()

            m_hide = ToolStripMenuItem("Ocultar en segundo plano")
            m_hide.Click += lambda s, e: api.hide_window()

            m_exit = ToolStripMenuItem("Cerrar completamente")
            m_exit.Click += lambda s, e: api.full_exit()

            tray_menu.Items.Add(m_show)
            tray_menu.Items.Add(m_new)
            tray_menu.Items.Add(m_hide)
            tray_menu.Items.Add(ToolStripSeparator())
            tray_menu.Items.Add(m_exit)
            g_tray.ContextMenuStrip = tray_menu

            def on_tray_mouse_click(s, e):
                if e.Button == MouseButtons.Left:
                    api.toggle_visibility()
            g_tray.MouseClick += on_tray_mouse_click
        except Exception as e:
            print(f"Error initializing system tray: {e}")

        def safety_uncloak():
            time.sleep(0.2)
            api._uncloak_window()
        threading.Thread(target=safety_uncloak, daemon=True).start()

    def on_closing():
        try:
            if api.is_dirty():
                api.show_and_activate()
                api._window.evaluate_js("window.handleCloseRequest && window.handleCloseRequest();")
                return False
        except Exception:
            pass
        api.mark_clean_exit()
        api.save_window_position()
        return True

    window.events.closing += on_closing
    window.events.loaded += on_loaded

    # Iniciar WebView2 con caché persistente
    webview.start(private_mode=False, storage_path=APPDATA_DIR, debug=False)

if __name__ == '__main__':
    main()
