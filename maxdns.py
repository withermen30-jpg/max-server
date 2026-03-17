import socket
import threading
import os
import json
import sqlite3
import hashlib
import secrets
from datetime import datetime

HOST     = '0.0.0.0'
PORT     = 1003
BASE_DIR = '/root/max'
DB_FILE  = os.path.join(BASE_DIR, 'maxdns.db')

# ══════════════════════════════════════════════════════
#  VERİTABANI
# ══════════════════════════════════════════════════════
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def setup_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            username  TEXT UNIQUE NOT NULL,
            password  TEXT NOT NULL,
            email     TEXT,
            created   TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS domains (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            domain    TEXT UNIQUE NOT NULL,
            user_id   INTEGER NOT NULL,
            ip        TEXT NOT NULL,
            port      INTEGER NOT NULL DEFAULT 1000,
            active    INTEGER NOT NULL DEFAULT 1,
            created   TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token     TEXT PRIMARY KEY,
            user_id   INTEGER NOT NULL,
            created   TEXT NOT NULL
        );
    """)
    db.commit()
    db.close()
    print('[MaxDNS] Veritabani hazir.')

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# ══════════════════════════════════════════════════════
#  DNS LOOKUP — main.py tarafından kullanılır
# ══════════════════════════════════════════════════════
def dns_lookup(domain):
    """Bir domain için IP:port döndür. Bulunamazsa None."""
    try:
        db = get_db()
        row = db.execute(
            'SELECT ip, port FROM domains WHERE domain=? AND active=1',
            (domain,)
        ).fetchone()
        db.close()
        if row:
            return {'ip': row['ip'], 'port': row['port']}
        return None
    except:
        return None

# ══════════════════════════════════════════════════════
#  API İŞLEMLERİ
# ══════════════════════════════════════════════════════
def api_register(data):
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    email    = data.get('email', '').strip()

    if not username or not password:
        return {'ok': False, 'error': 'Kullanici adi ve sifre gerekli.'}
    if len(username) < 3:
        return {'ok': False, 'error': 'Kullanici adi en az 3 karakter olmali.'}
    if len(password) < 6:
        return {'ok': False, 'error': 'Sifre en az 6 karakter olmali.'}

    try:
        db = get_db()
        db.execute(
            'INSERT INTO users (username, password, email, created) VALUES (?,?,?,?)',
            (username, hash_password(password), email, now())
        )
        db.commit()
        user_id = db.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone()['id']
        token = secrets.token_hex(32)
        db.execute('INSERT INTO sessions (token, user_id, created) VALUES (?,?,?)',
                   (token, user_id, now()))
        db.commit()
        db.close()
        return {'ok': True, 'token': token, 'username': username}
    except sqlite3.IntegrityError:
        return {'ok': False, 'error': 'Bu kullanici adi zaten kullaniliyor.'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def api_login(data):
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return {'ok': False, 'error': 'Kullanici adi ve sifre gerekli.'}

    try:
        db = get_db()
        user = db.execute(
            'SELECT * FROM users WHERE username=? AND password=?',
            (username, hash_password(password))
        ).fetchone()
        if not user:
            db.close()
            return {'ok': False, 'error': 'Kullanici adi veya sifre yanlis.'}
        token = secrets.token_hex(32)
        db.execute('INSERT INTO sessions (token, user_id, created) VALUES (?,?,?)',
                   (token, user['id'], now()))
        db.commit()
        db.close()
        return {'ok': True, 'token': token, 'username': username}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def get_user_from_token(token):
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

def api_register_domain(data, token):
    user = get_user_from_token(token)
    if not user:
        return {'ok': False, 'error': 'Giris yapmaniz gerekiyor.'}

    domain = data.get('domain', '').strip().lower()
    ip     = data.get('ip', '').strip()
    port   = int(data.get('port', 1000))

    if not domain or not ip:
        return {'ok': False, 'error': 'Domain ve IP gerekli.'}
    if not domain.endswith('.max'):
        return {'ok': False, 'error': 'Domain .max ile bitmeli.'}
    if len(domain) < 6:
        return {'ok': False, 'error': 'Domain cok kisa.'}
    if port < 1 or port > 65535:
        return {'ok': False, 'error': 'Gecersiz port.'}

    # Rezerve domainler — manuel eklenenler + sistem domainleri
    import os, json as _json
    reserved_system = ['maxdns.max', 'maxsearch.max', 'anasayfa.max', 'admin.max']
    if domain in reserved_system:
        return {'ok': False, 'error': 'Bu domain rezerve edilmis.'}

    # list.json'daki manuel domainler de rezerve sayılır
    domains_file = '/root/max/sites/domains/list.json'
    if os.path.exists(domains_file):
        try:
            with open(domains_file) as _f:
                manual_domains = _json.load(_f)
            if domain in manual_domains:
                return {'ok': False, 'error': 'Bu domain zaten kullanımda.'}
        except:
            pass

    try:
        db = get_db()
        db.execute(
            'INSERT INTO domains (domain, user_id, ip, port, active, created) VALUES (?,?,?,?,1,?)',
            (domain, user['id'], ip, port, now())
        )
        db.commit()
        db.close()
        return {'ok': True, 'domain': domain, 'ip': ip, 'port': port}
    except sqlite3.IntegrityError:
        return {'ok': False, 'error': 'Bu domain zaten kayitli.'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def api_my_domains(token):
    user = get_user_from_token(token)
    if not user:
        return {'ok': False, 'error': 'Giris yapmaniz gerekiyor.'}
    try:
        db = get_db()
        rows = db.execute(
            'SELECT domain, ip, port, active, created FROM domains WHERE user_id=? ORDER BY created DESC',
            (user['id'],)
        ).fetchall()
        db.close()
        return {'ok': True, 'domains': [dict(r) for r in rows]}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def api_update_domain(data, token):
    user = get_user_from_token(token)
    if not user:
        return {'ok': False, 'error': 'Giris yapmaniz gerekiyor.'}

    domain = data.get('domain', '').strip().lower()
    ip     = data.get('ip', '').strip()
    port   = int(data.get('port', 1000))

    if not domain or not ip:
        return {'ok': False, 'error': 'Domain ve IP gerekli.'}

    try:
        db = get_db()
        result = db.execute(
            'UPDATE domains SET ip=?, port=? WHERE domain=? AND user_id=?',
            (ip, port, domain, user['id'])
        )
        db.commit()
        db.close()
        if result.rowcount == 0:
            return {'ok': False, 'error': 'Domain bulunamadi veya yetkiniz yok.'}
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def api_delete_domain(data, token):
    user = get_user_from_token(token)
    if not user:
        return {'ok': False, 'error': 'Giris yapmaniz gerekiyor.'}

    domain = data.get('domain', '').strip().lower()
    try:
        db = get_db()
        result = db.execute(
            'DELETE FROM domains WHERE domain=? AND user_id=?',
            (domain, user['id'])
        )
        db.commit()
        db.close()
        if result.rowcount == 0:
            return {'ok': False, 'error': 'Domain bulunamadi.'}
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def api_lookup(data):
    domain = data.get('domain', '').strip().lower()
    result = dns_lookup(domain)
    if result:
        return {'ok': True, 'ip': result['ip'], 'port': result['port']}
    return {'ok': False, 'error': 'Domain bulunamadi.'}

# ══════════════════════════════════════════════════════
#  İSTEK İŞLE
# ══════════════════════════════════════════════════════
def handle_client(conn):
    try:
        raw = b''
        conn.settimeout(10)
        while True:
            try:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                raw += chunk
                if b'\n' in raw or b'\r' in raw:
                    break
            except socket.timeout:
                break

        if not raw:
            return

        req = raw.decode('utf-8', errors='replace').strip().split('\n')[0].strip()

        # Format: ACTION|token|json_data
        parts = req.split('|', 2)
        if len(parts) < 2:
            conn.sendall(json.dumps({'ok': False, 'error': 'Gecersiz istek.'}).encode())
            return

        action = parts[0].strip()
        token  = parts[1].strip() if len(parts) > 1 else ''
        data   = {}
        if len(parts) > 2:
            try:
                data = json.loads(parts[2])
            except:
                data = {}

        now_str = datetime.now().strftime('%H:%M:%S')
        print(f'[{now_str}] MaxDNS istek: {action}')

        if action == 'REGISTER':
            result = api_register(data)
        elif action == 'LOGIN':
            result = api_login(data)
        elif action == 'REGISTER_DOMAIN':
            result = api_register_domain(data, token)
        elif action == 'MY_DOMAINS':
            result = api_my_domains(token)
        elif action == 'UPDATE_DOMAIN':
            result = api_update_domain(data, token)
        elif action == 'DELETE_DOMAIN':
            result = api_delete_domain(data, token)
        elif action == 'LOOKUP':
            result = api_lookup(data)
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

# ══════════════════════════════════════════════════════
#  BAŞLAT
# ══════════════════════════════════════════════════════
def start():
    os.makedirs(BASE_DIR, exist_ok=True)
    setup_db()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(50)

    print('=' * 48)
    print('  MaxDNS Sunucusu v1.0')
    print('=' * 48)
    print(f'  Port : {PORT}')
    print(f'  DB   : {DB_FILE}')
    print('=' * 48)

    while True:
        try:
            conn, _ = s.accept()
            threading.Thread(target=handle_client, args=(conn,), daemon=True).start()
        except Exception as e:
            print(f'[Accept Hatasi] {e}')

if __name__ == '__main__':
    start()

