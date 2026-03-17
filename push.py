import socket
import threading
import json
import os
import sqlite3
from datetime import datetime

HOST     = '0.0.0.0'
PORT     = 1004
BASE_DIR = '/root/max'
DB_FILE  = os.path.join(BASE_DIR, 'push.db')

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def setup_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS notifications (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id  TEXT NOT NULL,
            title      TEXT NOT NULL,
            message    TEXT NOT NULL,
            domain     TEXT NOT NULL DEFAULT '',
            created    TEXT NOT NULL,
            delivered  INTEGER NOT NULL DEFAULT 0
        );
    """)
    db.commit()
    db.close()
    print('[Push] Veritabani hazir.')

def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def pull_notifications(device_id):
    try:
        db = get_db()
        rows = db.execute(
            'SELECT id, title, message, domain FROM notifications '
            'WHERE device_id=? AND delivered=0 ORDER BY created ASC',
            (device_id,)
        ).fetchall()
        if not rows:
            db.close()
            return '[]'
        ids = [r['id'] for r in rows]
        db.execute(
            'UPDATE notifications SET delivered=1 WHERE id IN ({})'.format(','.join('?'*len(ids))),
            ids
        )
        db.commit()
        db.close()
        result = [{'title': r['title'], 'message': r['message'], 'domain': r['domain']} for r in rows]
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        print('[Push] Pull hatasi:', e)
        return '[]'

def push_notification(device_id, title, message, domain=''):
    try:
        db = get_db()
        db.execute(
            'INSERT INTO notifications (device_id, title, message, domain, created) VALUES (?,?,?,?,?)',
            (device_id, title, message, domain, now())
        )
        db.commit()
        db.close()
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def push_all(title, message, domain=''):
    try:
        db = get_db()
        devices = db.execute('SELECT DISTINCT device_id FROM notifications').fetchall()
        db.close()
        if not devices:
            return {'ok': False, 'error': 'Kayitli cihaz yok.'}
        for d in devices:
            push_notification(d['device_id'], title, message, domain)
        return {'ok': True, 'sent': len(devices)}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def handle_client(conn):
    try:
        raw = b''
        conn.settimeout(10)
        while True:
            try:
                chunk = conn.recv(4096)
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
        parts = req.split('|', 3)
        action = parts[0].strip()
        if action == 'PULL':
            device_id = parts[1].strip() if len(parts) > 1 else ''
            if not device_id:
                conn.sendall(b'[]')
                return
            conn.sendall(pull_notifications(device_id).encode('utf-8'))
        elif action == 'PUSH':
            device_id = parts[1].strip() if len(parts) > 1 else ''
            title     = parts[2].strip() if len(parts) > 2 else 'MaxNetwork'
            message   = parts[3].strip() if len(parts) > 3 else ''
            if device_id == 'ALL':
                result = push_all(title, message)
            else:
                result = push_notification(device_id, title, message)
            conn.sendall(json.dumps(result).encode('utf-8'))
        else:
            conn.sendall(b'UNKNOWN')
    except Exception as e:
        print('[Hata]', e)
    finally:
        try:
            conn.close()
        except:
            pass

def start():
    os.makedirs(BASE_DIR, exist_ok=True)
    setup_db()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(50)
    print('MaxPush calisiyor: port', PORT)
    while True:
        try:
            conn, _ = s.accept()
            threading.Thread(target=handle_client, args=(conn,), daemon=True).start()
        except Exception as e:
            print('[Accept]', e)

if __name__ == '__main__':
    start()
