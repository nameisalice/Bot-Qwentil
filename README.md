# ⚡ Qwen Cloud API Key Research Tool (Bot-Qwentil)

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/playwright-async-green.svg)](https://playwright.dev/python/)
[![License](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)

Program otomatisasi berbasis Python dan Playwright untuk riset alur otentikasi web, pengujian endpoint API Qwen/DashScope, dan eksperimen dynamic IP/proxy rotation.

Program ini cocok untuk lingkungan riset dan akun yang memang Anda miliki/izinkan. Hindari penggunaan untuk mass registration, bypass proteksi layanan, atau aktivitas yang melanggar ToS platform.

---

## ✨ Fitur Utama

- **Otomatisasi Browser Berbasis Playwright**: Menjalankan alur web secara headless maupun non-headless untuk kebutuhan pengujian.
- **Dynamic IP Proxy Module**: Modul `proxy_dynamic_ip` untuk riset rotasi proxy, health check, dan request-level proxy usage.
- **Pembuatan & Penyalinan API Key Qwen**: Secara otomatis membuat API Key baru di dashboard Qwen Cloud dan menyalinnya.
- **Pengujian API Key Instan**: Menguji API Key yang dibuat langsung ke endpoint API Qwen (`qwen-turbo`) untuk memeriksa status keaktifan (`OK`, `DENIED`, `UNELIGIBLE`, `DEAD`).
- **Penyimpanan Terorganisir**: Hasil akun dan API Key secara otomatis disimpan dalam file text sesuai hasil pengujian:
  - `Valid.txt` (Untuk akun dengan API Key aktif/berfungsi).
  - `Uneligible.txt` (Untuk akun yang belum mendapatkan kuota gratis/eligible).
  - `Dead.txt` (Untuk akun mati atau diblokir).
- **Tampilan Dashboard CLI yang Estetik**: Menggunakan pustaka `rich` untuk menampilkan panel progres interaktif, status worker real-time, dan ringkasan statistik akhir secara visual di terminal Anda.
- **Konkurensi & Manajemen Antrean**: Mendukung eksekusi multi-worker menggunakan asyncio Semaphores dan slot queues yang dapat diatur kecepatannya via `.env`.

---

## 🛠️ Persyaratan Sistem

Sebelum menjalankan program ini, pastikan Anda telah menginstal komponen berikut:

1. **Python 3.10+** (disarankan 3.10, 3.11, atau 3.12)
2. **Playwright** (beserta browser Chromium yang diperlukan)
3. **Rich** (untuk visualisasi terminal)
4. **aiohttp** dan **certifi** (untuk modul dynamic proxy)

Untuk VPS non-GUI, gunakan `HEADLESS=true`. RAM minimum 2 GB, 4 GB lebih aman untuk Chromium/Playwright.

---

## 🚀 Panduan Instalasi & Penggunaan

### 1. Kloning Repositori
```bash
git clone https://github.com/Zeambut/Bot-Qwentil.git
cd Bot-Qwentil
```

### 2. Instal Dependensi
Disarankan memakai virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Pasang browser Chromium untuk Playwright:
```bash
python -m playwright install chromium
```

Di VPS Ubuntu/Debian non-GUI, gunakan opsi `--with-deps` agar dependency sistem ikut terpasang:

```bash
python -m playwright install --with-deps chromium
```

Jika `--with-deps` gagal karena permission, jalankan dependency sistem secara manual:

```bash
sudo apt update
sudo apt install -y libnss3 libnspr4 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2
python -m playwright install chromium
```

### 3. Konfigurasi File `.env`
Buat file bernama `.env` di direktori utama proyek (jika belum ada) dan sesuaikan pengaturannya:

```env
# Password untuk akun Alibaba Cloud & GoMail yang akan didaftarkan (harus 8-20 karakter)
PASSWORD=Astral11*

# Jumlah item per run. Untuk tes awal/VPS kecil, mulai dari 1.
ACCOUNTS_PER_RUN=1

# VPS non-GUI wajib true. false hanya untuk laptop/desktop dengan GUI.
HEADLESS=true

# Jumlah worker yang berjalan bersamaan. Mulai dari 1 untuk stabil.
CONCURRENCY=1

# Cooldown antar batch dalam satu run (detik)
COOLDOWN_BETWEEN_BATCHES=30

# Jeda setelah satu run selesai sebelum restart otomatis (detik)
# Set 0 untuk menonaktifkan auto-restart (bot berhenti setelah selesai)
RESTART_DELAY=15

# Untuk tes awal, batasi 1 run supaya mudah debug.
MAX_RESTARTS=1

# Dynamic IP Proxy
# Untuk tes awal, matikan dulu. Aktifkan setelah mode direct sudah stabil.
PROXY_ENABLED=false
PROXY_MIN_POOL=5
PROXY_MAX_POOL=20
```

### 4. Jalankan Bot
Jalankan skrip utama menggunakan Python:
```bash
python qwen2.py
```

### 5. VPS Non-GUI
Konfigurasi yang disarankan untuk VPS non-GUI:

```env
HEADLESS=true
CONCURRENCY=1
ACCOUNTS_PER_RUN=1
MAX_RESTARTS=1
RESTART_DELAY=0
PROXY_ENABLED=false
```

Jalankan:

```bash
cd /path/ke/Bot-Qwentil
source .venv/bin/activate
python qwen2.py
```

Jika sudah stabil tanpa proxy, baru aktifkan proxy untuk riset dynamic IP:

```env
PROXY_ENABLED=true
PROXY_MIN_POOL=5
PROXY_MAX_POOL=20
```

Hindari nilai pool besar di VPS kecil karena validasi proxy gratis bisa lambat dan boros resource.

---

## 🌐 Dynamic IP Proxy

Modul proxy berada di:

```text
proxy_dynamic_ip/
```

Dependency proxy sudah masuk ke `requirements.txt`. Modul ini menggunakan `aiohttp` untuk mengambil daftar proxy, melakukan health check, dan memilih proxy dari pool.

Catatan stabilitas:

- Proxy gratis sering mati, lambat, atau tidak anonim.
- Jangan mengirim password, API key, atau credential sensitif lewat proxy publik.
- Untuk riset yang lebih stabil, gunakan proxy private yang Anda kontrol.
- Mulai dari `PROXY_MIN_POOL=5` dan `PROXY_MAX_POOL=20`, lalu naikkan perlahan jika VPS mampu.

Test import modul proxy:

```bash
python -c "from proxy_dynamic_ip.dynamic_proxy import DynamicProxyClient; print('proxy ok')"
```

---

## 🖥️ Tampilan Dashboard CLI

Saat berjalan, Anda akan disuguhkan dashboard dinamis langsung di terminal Anda:

```text
⚡ QWEN CLOUD API RESEARCH TOOL  Elapsed: 45s
Progress: [██████████░░░░░░░░░░] 50.0% (1/2) | ✓ 1 | ✗ 0
─────────────────────────────────────────────────────────────────
  » WORKER-1  johnsmith123@awdigi.dev         | [██████████] 100% (Selesai)
  » WORKER-2  jamesjones456@awdigi.dev        | [██████░░░░]  60% (otp masuk...)
```

Setelah semua proses selesai, ringkasan pengujian akan ditampilkan:

```text
=================================================================
📊 SUMMARY HASIL PENGUJIAN API KEY:
=================================================================
Total Registrasi Diproses : 2
✔ API Key OK / Aktif      : 2
✖ API Key DENIED          : 0
⚠ API Key UNELIGIBLE      : 0
💀 API Key DEAD/EXPIRED    : 0
✗ Gagal Registrasi Bot    : 0
```

---

## 📁 Struktur File Output

Setiap akun yang berhasil diproses akan dicatat pada salah satu file berikut sesuai kelayakannya dengan format `email|api_key`:

- **`Valid.txt`**:
  ```text
  johnsmith123@awdigi.dev|sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  ```
- **`Uneligible.txt`**:
  ```text
  jamesjones456@awdigi.dev|sk-yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
  ```
- **`Dead.txt`**:
  ```text
  faileduser789@awdigi.dev|sk-zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz
  ```

---

## ⚠️ Disclaimer

Alat ini dibuat **hanya untuk tujuan edukasi dan penelitian** mengenai otomasi browser, pengujian API, dan dynamic IP/proxy rotation. Penulis tidak bertanggung jawab atas penyalahgunaan alat ini yang melanggar hukum, ToS Alibaba Cloud/Qwen Cloud, atau platform terkait lainnya. Harap gunakan hanya pada akun, sistem, dan traffic yang Anda miliki izin untuk uji.

---

## 📝 Lisensi

Proyek ini dilisensikan di bawah lisensi MIT - lihat file [LICENSE](LICENSE) untuk detailnya.
