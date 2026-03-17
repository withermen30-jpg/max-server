# MaxNetwork Server

**MaxNetwork** ekosisteminin sunucu altyapısı. `.max` domain sistemi üzerine kurulu bağımsız bir internet ağının backend servisleri.

---

## Servisler

| Dosya | Port | Açıklama |
|-------|------|----------|
| `main.py` | 1000 | `.max` site sunucusu — TCP protokolü ile statik dosya servisi |
| `maxdns.py` | 1003 | MaxDNS — domain kayıt ve yönetim sistemi |
| `push.py` | 1004 | MaxPush — arka plan bildirim servisi |
| `maxcloud.py` | 1005 | MaxCloud — kişisel bulut depolama (2GB/kullanıcı) |

---

## Nasıl Çalışır?

MaxNetwork, HTTP yerine ham **TCP protokolü** kullanır.

İstek formatı:
```
METHOD|domain|path|query|body
```

Örnek:
```bash
echo "GET|anasayfa.max|/||" | nc 127.0.0.1 1000
```

---

## Kurulum

### Gereksinimler
- Python 3.8+
- SQLite (Python ile birlikte gelir)

### Başlatma

```bash
# Klasör yapısını oluştur
mkdir -p /root/max/sites/domains

# Tüm servisleri başlat
nohup python3 /root/max/main.py &
nohup python3 /root/max/maxdns.py &
nohup python3 /root/max/push.py &
nohup python3 /root/max/maxcloud.py &
```

### Klasör Yapısı

```
/root/max/
├── main.py
├── maxdns.py
├── push.py
├── maxcloud.py
├── maxdns.db
├── push.db
├── maxcloud.db
├── cloud/           ← MaxCloud kullanıcı dosyaları
└── sites/
    ├── domains/
    │   └── list.json
    ├── anasayfa.max/
    │   └── index.html
    └── maxsearch.max/
        └── index.html
```

### domains/list.json Formatı

```json
{
  "anasayfa.max": {},
  "maxsearch.max": {},
  "maxdns.max": {}
}
```

---

## MaxNetwork Ekosistemi

Bu sunucu aşağıdaki istemcilerle çalışır:

- **MaxNetwork Browser (Android)** — [github.com/withermen30-jpg/maxnetwork-browser](https://github.com/withermen30-jpg/maxnetwork-browser)
- **MaxCloud (Android)** — Ayrı uygulama, yakında
- **MaxNetwork Browser (PC)** — PyQt6 tabanlı masaüstü tarayıcı

---

## Lisans

```
MIT Lisansı — Ancak Ticari Kullanım Yasaktır

Telif Hakkı (c) 2024 Kerem (withermen30-jpg)

Bu yazılım ve ilişkili belgeler ("Yazılım"), aşağıdaki koşullar dahilinde
herhangi bir kısıtlama olmaksızın kullanılabilir, kopyalanabilir, değiştirilebilir,
birleştirilebilir, yayınlanabilir ve dağıtılabilir:

✓ Kişisel kullanım
✓ Eğitim amaçlı kullanım  
✓ Açık kaynaklı projelerde kullanım
✓ Değiştirip kendi sunucunda çalıştırma

✗ Ticari amaçla kullanım, satış veya kiralamak yasaktır
✗ Bu yazılımı temel alan ücretli bir hizmet sunmak yasaktır
✗ Kaynak kod belirtilmeden dağıtmak yasaktır

Yukarıdaki telif hakkı bildirimi ve bu izin bildirimi, yazılımın tüm
kopyalarına veya önemli bölümlerine dahil edilmelidir.

YAZILIM "OLDUĞU GİBİ" SAĞLANMAKTADIR. YAZAR HİÇBİR DURUMDA SORUMLU
TUTULAMAZ.
```

---

## İletişim

- **GitHub:** [github.com/withermen30-jpg](https://github.com/withermen30-jpg)
- **E-posta:** kerem@kerem.site
- **Instagram:** [@maxnetwork_tarayici](https://instagram.com/maxnetwork_tarayici)

---

> Bu proje aktif geliştirme aşamasındadır. Katkıda bulunmak isteyenler PR açabilir.
