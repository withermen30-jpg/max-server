import socket
import threading
import os
import json
import mimetypes
import hashlib
import hmac
import base64
from urllib.parse import unquote
from datetime import datetime

HOST         = '0.0.0.0'
PORT         = 1000
BASE_DIR     = '/root/max'
SITES_DIR    = os.path.join(BASE_DIR, 'sites')
DOMAINS_FILE = os.path.join(SITES_DIR, 'domains', 'list.json')
SECRET_KEY   = 'maxnetwork-secret-2024-xK9mP3qR'

def setup():
    os.makedirs(SITES_DIR, exist_ok=True)
    os.makedirs(os.path.join(SITES_DIR, 'domains'), exist_ok=True)

    if not os.path.exists(DOMAINS_FILE):
        with open(DOMAINS_FILE, 'w') as f:
            json.dump({"anasayfa.max": {}, "maxsearch.max": {}}, f, indent=2)
        print('[Kurulum] domains/list.json olusturuldu.')

    anasayfa_dir = os.path.join(SITES_DIR, 'anasayfa.max')
    os.makedirs(anasayfa_dir, exist_ok=True)
    index_file = os.path.join(anasayfa_dir, 'index.html')
    if not os.path.exists(index_file):
        with open(index_file, 'w', encoding='utf-8') as f:
            f.write("""<!DOCTYPE html>
<html lang="tr"><head><meta charset="UTF-8">
<title>MaxNetwork</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#070810;color:#E8EAF6;font-family:'Segoe UI',Arial;
     min-height:100vh;display:flex;align-items:center;justify-content:center}
.card{text-align:center;padding:48px}
.logo{font-size:48px;font-weight:900;color:#4FC3F7;margin-bottom:8px}
.logo span{color:#E8EAF6}
.sub{color:#7986A8;font-size:16px;margin-bottom:40px}
.links a{display:inline-block;margin:8px;padding:12px 28px;
         background:rgba(79,195,247,.1);border:1px solid rgba(79,195,247,.3);
         border-radius:12px;color:#4FC3F7;text-decoration:none;font-size:14px}
</style></head>
<body><div class="card">
  <div class="logo">Max<span>Network</span></div>
  <div class="sub">Ozel Internet Agi</div>
  <div class="links">
    <a href="max://maxsearch.max">MaxSearch</a>
    <a href="max://anasayfa.max">Anasayfa</a>
  </div>
</div></body></html>""")
        print('[Kurulum] anasayfa.max/index.html olusturuldu.')

    search_dir = os.path.join(SITES_DIR, 'maxsearch.max')
    os.makedirs(search_dir, exist_ok=True)
    search_file = os.path.join(search_dir, 'index.html')
    if not os.path.exists(search_file):
        with open(search_file, 'w', encoding='utf-8') as f:
            f.write("""<!DOCTYPE html>
<html lang="tr"><head><meta charset="UTF-8">
<title>MaxSearch</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#070810;color:#E8EAF6;font-family:'Segoe UI',Arial;
     min-height:100vh;display:flex;align-items:center;justify-content:center}
.wrap{text-align:center;width:90%;max-width:500px}
.logo{font-size:42px;font-weight:900;color:#4FC3F7;margin-bottom:32px}
.logo span{color:#E8EAF6}
form{display:flex;gap:10px}
input{flex:1;background:rgba(255,255,255,.07);border:1px solid rgba(79,195,247,.3);
      border-radius:12px;padding:14px 18px;color:#E8EAF6;font-size:15px;outline:none}
input:focus{border-color:#4FC3F7}
button{background:#4FC3F7;color:#000;border:none;border-radius:12px;
       padding:14px 24px;font-weight:bold;cursor:pointer;font-size:15px}
</style></head>
<body><div class="wrap">
  <div class="logo">Max<span>Search</span></div>
  <form onsubmit="ara(event)">
    <input id="q" type="text" placeholder="Ara..." autofocus/>
    <button type="submit">Ara</button>
  </form>
</div>
<script>
function ara(e) {
  e.preventDefault();
  var q = document.getElementById('q').value.trim();
  if (!q) return;
  var result = MaxBridge.searchDefault(q);
  alert(result);
}
</script>
</body></html>""")
        print('[Kurulum] maxsearch.max/index.html olusturuldu.')

    print('[Kurulum] Tamamlandi.')

def load_domains():
    try:
        with open(DOMAINS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def maxdns_lookup(domain):
    """MaxDNS'e sorar, domain varsa (ip, port) döner, yoksa None."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect(('127.0.0.1', 1003))
        req = 'LOOKUP||' + json.dumps({'domain': domain}) + '\n'
        s.sendall(req.encode('utf-8'))
        resp = b''
        while True:
            chunk = s.recv(4096)
            if not chunk: break
            resp += chunk
            if b'\n' in resp or b'}' in resp: break
        s.close()
        data = json.loads(resp.decode('utf-8', errors='replace').strip())
        if data.get('ok'):
            return data['ip'], int(data['port'])
        return None
    except:
        return None

def proxy_request(domain, path, query, ip, port):
    """Başka bir MaxNetwork sunucusundan sayfa al."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(10)
        s.connect((ip, port))
        req = f'GET|{domain}|{path}|{query}|\n'
        s.sendall(req.encode('utf-8'))
        chunks = []
        while True:
            chunk = s.recv(65536)
            if not chunk: break
            chunks.append(chunk)
        s.close()
        return b''.join(chunks).decode('utf-8', errors='replace')
    except Exception as e:
        return error_html(domain, f'Uzak sunucuya baglanilamadi: {e}')

def serve_file(domain, path):
    domains = load_domains()

    # Kendi listesinde yoksa MaxDNS'e sor
    if domain not in domains:
        result = maxdns_lookup(domain)
        if result:
            ip, port = result
            now_str = datetime.now().strftime('%H:%M:%S')
            print(f'[{now_str}] MaxDNS yonlendirme: {domain} -> {ip}:{port}')
            return proxy_request(domain, path, '', ip, port)
        return error_html(domain, 'Domain kayitli degil.')

    domain_dir = os.path.join(SITES_DIR, domain)
    if not os.path.exists(domain_dir):
        return error_html(domain, 'Site dizini bulunamadi.')

    clean = unquote(path.strip()) or '/'
    if clean == '/':
        clean = '/index.html'

    full = os.path.abspath(os.path.join(domain_dir, clean.lstrip('/')))
    if not full.startswith(os.path.abspath(domain_dir)):
        return error_html(domain, 'Gecersiz yol.')

    if os.path.isdir(full):
        full = os.path.join(full, 'index.html')

    if not os.path.exists(full):
        return error_html(domain, f'Sayfa bulunamadi: {clean}')

    try:
        ext = os.path.splitext(full)[1].lower()
        text_exts = {'.html','.htm','.css','.js','.json','.txt','.xml','.md'}
        if ext in text_exts:
            with open(full, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        else:
            with open(full, 'rb') as f:
                data = f.read()
            mime = mimetypes.guess_type(full)[0] or 'application/octet-stream'
            b64 = base64.b64encode(data).decode()
            return f'<img src="data:{mime};base64,{b64}" style="max-width:100%">'
    except Exception as e:
        return error_html(domain, f'Dosya okunamadi: {e}')

def error_html(domain, msg):
    return f"""<!DOCTYPE html>
<html lang="tr"><head><meta charset="UTF-8"><title>Hata</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#070810;color:#E8EAF6;font-family:'Segoe UI',Arial;
     min-height:100vh;display:flex;align-items:center;justify-content:center}}
.card{{background:rgba(18,21,31,.95);border:1px solid rgba(79,195,247,.15);
       border-radius:20px;padding:48px;text-align:center;max-width:420px}}
.icon{{font-size:48px;margin-bottom:16px}}
h1{{color:#FF5252;font-size:24px;margin-bottom:8px}}
.domain{{color:#4FC3F7;font-size:13px;margin:10px 0 16px;
         background:rgba(79,195,247,.08);border-radius:20px;padding:4px 14px;display:inline-block}}
p{{color:#7986A8;font-size:13px;line-height:1.6}}
.footer{{margin-top:32px;color:#2A3A4A;font-size:11px}}
</style></head>
<body><div class="card">
  <div class="icon">&#9888;</div>
  <h1>Hata</h1>
  <div class="domain">{domain}</div>
  <p>{msg}</p>
  <div class="footer">MaxNetwork Server v2.0</div>
</div></body></html>"""

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
        parts = req.split('|')

        if len(parts) < 5:
            conn.sendall(b'INVALID')
            return

        method  = parts[0]
        domain  = parts[1]
        path    = parts[2]
        query   = parts[3]
        body    = parts[4]

        now = datetime.now().strftime('%H:%M:%S')
        print(f'[{now}] {domain} sitesine baglanti istegi')

        if method in ('GET', 'POST'):
            response = serve_file(domain, path or '/')
        else:
            response = error_html(domain, f'Desteklenmeyen method: {method}')

        conn.sendall(response.encode('utf-8'))

    except Exception as e:
        print(f'[Hata] {e}')
        try:
            conn.sendall(error_html('server', str(e)).encode())
        except:
            pass
    finally:
        try:
            conn.close()
        except:
            pass

def start():
    setup()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(50)
    print('=' * 48)
    print('  MaxNetwork Site Sunucusu v2.0')
    print('=' * 48)
    print(f'  Port    : {PORT}')
    print(f'  Siteler : {SITES_DIR}')
    print('=' * 48)
    while True:
        try:
            conn, _ = s.accept()
            threading.Thread(target=handle_client, args=(conn,), daemon=True).start()
        except Exception as e:
            print(f'[Accept Hatasi] {e}')

if __name__ == '__main__':
    start()

