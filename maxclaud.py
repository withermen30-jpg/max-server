import socket
import threading
import os
import json
import sqlite3
import hashlib
import secrets
import base64
from datetime import datetime

HOST      = '0.0.0.0'
PORT      = 1005
BASE_DIR  = '/root/max'
DB_FILE   = os.path.join(BASE_DIR, 'maxcloud.db')
FILES_DIR = os.path.join(BASE_DIR, 'cloud')
FREE_QUOTA = 2 * 1024 * 1024 * 1024  # 2GB

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def setup():
    os.makedirs(FILES_DIR, exist_ok=True)
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email    TEXT,
            quota    INTEGER NOT NULL DEFAULT 2147483648,
            created  TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS files (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER NOT NULL,
            filename  TEXT NOT NULL,
            size      INTEGER NOT NULL DEFAULT 0,
            mime      TEXT NOT NULL DEFAULT 'application/octet-stream',
            created   TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token   TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created TEXT NOT NULL
        );
    """)
    db.commit()
    db.close()
    print('[MaxCloud] Veritabani hazir.')

def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def get_user(token):
    try:
        db = get_db()
        row = db.execute(
            'SELECT u.* FROM users u JOIN sessions s ON u.id=s.user_id WHERE s.token=?',
            (token,)
        ).fetchone()
        db.close()
        return dict(row) if row else None
    except:
        return None

def user_dir(user_id):
    d = os.path.join(FILES_DIR, str(user_id))
    os.makedirs(d, exist_ok=True)
    return d

def used_space(user_id):
    try:
        db = get_db()
        row = db.execute('SELECT SUM(size) as total FROM files WHERE user_id=?', (user_id,)).fetchone()
        db.close()
        return row['total'] or 0
    except:
        return 0

# ══ API ══
def api_register(data):
    u = data.get('username','').strip()
    p = data.get('password','').strip()
    e = data.get('email','').strip()
    if not u or not p:
        return {'ok': False, 'error': 'Kullanici adi ve sifre gerekli.'}
    if len(u) < 3:
        return {'ok': False, 'error': 'Kullanici adi en az 3 karakter.'}
    if len(p) < 6:
        return {'ok': False, 'error': 'Sifre en az 6 karakter.'}
    try:
        db = get_db()
        db.execute('INSERT INTO users (username,password,email,created) VALUES (?,?,?,?)',
                   (u, hash_pw(p), e, now()))
        db.commit()
        user_id = db.execute('SELECT id FROM users WHERE username=?', (u,)).fetchone()['id']
        token = secrets.token_hex(32)
        db.execute('INSERT INTO sessions (token,user_id,created) VALUES (?,?,?)', (token, user_id, now()))
        db.commit()
        db.close()
        os.makedirs(os.path.join(FILES_DIR, str(user_id)), exist_ok=True)
        return {'ok': True, 'token': token, 'username': u, 'quota': FREE_QUOTA}
    except sqlite3.IntegrityError:
        return {'ok': False, 'error': 'Bu kullanici adi zaten var.'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def api_login(data):
    u = data.get('username','').strip()
    p = data.get('password','').strip()
    if not u or not p:
        return {'ok': False, 'error': 'Kullanici adi ve sifre gerekli.'}
    try:
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username=? AND password=?',
                          (u, hash_pw(p))).fetchone()
        if not user:
            db.close()
            return {'ok': False, 'error': 'Kullanici adi veya sifre yanlis.'}
        token = secrets.token_hex(32)
        db.execute('INSERT INTO sessions (token,user_id,created) VALUES (?,?,?)',
                   (token, user['id'], now()))
        db.commit()
        db.close()
        return {'ok': True, 'token': token, 'username': u, 'quota': user['quota']}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def api_list(token):
    user = get_user(token)
    if not user:
        return {'ok': False, 'error': 'Giris yapmaniz gerekiyor.'}
    try:
        db = get_db()
        rows = db.execute(
            'SELECT id, filename, size, mime, created FROM files WHERE user_id=? ORDER BY created DESC',
            (user['id'],)
        ).fetchall()
        db.close()
        used = used_space(user['id'])
        return {
            'ok': True,
            'files': [dict(r) for r in rows],
            'used': used,
            'quota': user['quota']
        }
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def api_upload(token, filename, mime, data_b64):
    user = get_user(token)
    if not user:
        return {'ok': False, 'error': 'Giris yapmaniz gerekiyor.'}

    filename = os.path.basename(filename.strip())
    if not filename:
        return {'ok': False, 'error': 'Gecersiz dosya adi.'}

    try:
        file_data = base64.b64decode(data_b64)
    except:
        return {'ok': False, 'error': 'Dosya verisi okunamadi.'}

    size = len(file_data)
    used = used_space(user['id'])

    if used + size > user['quota']:
        return {'ok': False, 'error': 'Depolama alani dolu. (2GB limit)'}

    # Benzersiz dosya adı
    safe_name = f"{int(datetime.now().timestamp())}_{filename}"
    file_path = os.path.join(user_dir(user['id']), safe_name)

    try:
        with open(file_path, 'wb') as f:
            f.write(file_data)

        db = get_db()
        db.execute(
            'INSERT INTO files (user_id, filename, size, mime, created) VALUES (?,?,?,?,?)',
            (user['id'], filename, size, mime or 'application/octet-stream', now())
        )
        db.commit()
        file_id = db.execute('SELECT last_insert_rowid() as id').fetchone()['id']
        db.close()

        return {'ok': True, 'id': file_id, 'filename': filename, 'size': size}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def api_download(token, file_id):
    user = get_user(token)
    if not user:
        return {'ok': False, 'error': 'Giris yapmaniz gerekiyor.'}
    try:
        db = get_db()
        row = db.execute(
            'SELECT * FROM files WHERE id=? AND user_id=?',
            (file_id, user['id'])
        ).fetchone()
        db.close()
        if not row:
            return {'ok': False, 'error': 'Dosya bulunamadi.'}

        # Dosya adını bul
        udir = user_dir(user['id'])
        matches = [f for f in os.listdir(udir) if f.endswith('_' + row['filename'])]
        if not matches:
            return {'ok': False, 'error': 'Dosya diskde bulunamadi.'}

        file_path = os.path.join(udir, matches[-1])
        with open(file_path, 'rb') as f:
            data = f.read()

        b64 = base64.b64encode(data).decode()
        return {'ok': True, 'filename': row['filename'], 'mime': row['mime'], 'data': b64}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def api_delete(token, file_id):
    user = get_user(token)
    if not user:
        return {'ok': False, 'error': 'Giris yapmaniz gerekiyor.'}
    try:
        db = get_db()
        row = db.execute('SELECT * FROM files WHERE id=? AND user_id=?',
                         (file_id, user['id'])).fetchone()
        if not row:
            db.close()
            return {'ok': False, 'error': 'Dosya bulunamadi.'}

        udir = user_dir(user['id'])
        matches = [f for f in os.listdir(udir) if f.endswith('_' + row['filename'])]
        for m in matches:
            try:
                os.remove(os.path.join(udir, m))
            except:
                pass

        db.execute('DELETE FROM files WHERE id=?', (file_id,))
        db.commit()
        db.close()
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

# ══ İSTEK İŞLE ══
def handle_client(conn):
    try:
        raw = b''
        conn.settimeout(30)
        while True:
            try:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                raw += chunk
                # JSON bitişini bekle
                if raw.strip().endswith(b'}') or raw.strip().endswith(b'null'):
                    break
                if len(raw) > 50 * 1024 * 1024:  # 50MB limit
                    break
            except socket.timeout:
                break

        if not raw:
            return

        req_str = raw.decode('utf-8', errors='replace').strip()

        # Format: ACTION|token|json
        parts = req_str.split('|', 2)
        action = parts[0].strip()
        token  = parts[1].strip() if len(parts) > 1 else ''
        data   = {}
        if len(parts) > 2:
            try:
                data = json.loads(parts[2])
            except:
                data = {}

        t = datetime.now().strftime('%H:%M:%S')
        print(f'[{t}] MaxCloud: {action}')

        if action == 'REGISTER':
            result = api_register(data)
        elif action == 'LOGIN':
            result = api_login(data)
        elif action == 'LIST':
            result = api_list(token)
        elif action == 'UPLOAD':
            filename = data.get('filename', '')
            mime     = data.get('mime', '')
            b64data  = data.get('data', '')
            result   = api_upload(token, filename, mime, b64data)
        elif action == 'DOWNLOAD':
            file_id = data.get('id', 0)
            result  = api_download(token, file_id)
        elif action == 'DELETE':
            file_id = data.get('id', 0)
            result  = api_delete(token, file_id)
        else:
            result = {'ok': False, 'error': f'Bilinmeyen aksiyon: {action}'}

        conn.sendall(json.dumps(result, ensure_ascii=False).encode('utf-8'))

    except Exception as e:
        print(f'[Hata] {e}')
        try:
            conn.sendall(json.dumps({'ok': False, 'error': str(e)}).encode())
        except:
            pass
    finally:
        try:
            conn.close()
        except:
            pass

def start():
    os.makedirs(BASE_DIR, exist_ok=True)
    os.makedirs(FILES_DIR, exist_ok=True)
    setup()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(50)

    print('=' * 45)
    print('  MaxCloud Sunucusu v1.0')
    print('=' * 45)
    print(f'  Port   : {PORT}')
    print(f'  Dosyalar: {FILES_DIR}')
    print(f'  Kota   : 2GB / kullanici')
    print('=' * 45)

    while True:
        try:
            conn, _ = s.accept()
            threading.Thread(target=handle_client, args=(conn,), daemon=True).start()
        except Exception as e:
            print(f'[Accept] {e}')

if __name__ == '__main__':
    start()

