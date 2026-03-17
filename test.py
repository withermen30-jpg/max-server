import socket
import threading

HOST = '0.0.0.0'
PORT = 1004

HTML = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>Test Sunucusu</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#070810; color:#E8EAF6; font-family:'Segoe UI',Arial;
       min-height:100vh; display:flex; align-items:center; justify-content:center; }
.card { text-align:center; padding:48px; }
.icon { font-size:64px; margin-bottom:20px; }
h1 { font-size:32px; font-weight:900; color:#00C853; margin-bottom:10px; }
p { color:#7986A8; font-size:15px; }
.badge { display:inline-block; margin-top:20px; padding:8px 20px;
         background:rgba(0,200,83,.1); border:1px solid rgba(0,200,83,.3);
         border-radius:20px; color:#00C853; font-size:13px; }
</style>
</head>
<body>
<div class="card">
  <div class="icon">✅</div>
  <h1>Bağlantı Başarılı!</h1>
  <p>MaxDNS yönlendirmesi çalışıyor.</p>
  <div class="badge">Port 1004 — Aktif</div>
</div>
</body>
</html>"""

def handle(conn):
    try:
        raw = b''
        conn.settimeout(10)
        while True:
            try:
                chunk = conn.recv(4096)
                if not chunk: break
                raw += chunk
                if b'\n' in raw or b'\r' in raw: break
            except: break
        conn.sendall(HTML.encode('utf-8'))
    except Exception as e:
        print(f'Hata: {e}')
    finally:
        conn.close()

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind((HOST, PORT))
s.listen(50)
print(f'Test sunucusu calisiyor: port {PORT}')

while True:
    conn, _ = s.accept()
    threading.Thread(target=handle, args=(conn,), daemon=True).start()

