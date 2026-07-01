# ⚡ Qwen Cloud Concurrent Batch Account Generator & Tester (Bot-Qwentil)

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/playwright-async-green.svg)](https://playwright.dev/python/)
[![License](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)

Program otomatisasi berbasis Python dan Playwright untuk melakukan registrasi akun Alibaba Cloud secara massal, mendaftarkan layanan Qwen Cloud (Model Studio / DashScope), mengklaim kuota gratis, membuat API Key, serta menguji validitas API Key tersebut secara instan.

Alat ini dilengkapi dengan sistem bypass anti-bot canggih menggunakan kurva Bezier untuk mensimulasikan pergerakan mouse manusia asli (human-like mouse movement) guna melewati Slider Captcha Alibaba Cloud.

---

## ✨ Fitur Utama

- **Otomatisasi Pendaftaran GoMail**: Secara otomatis membuat mailbox baru di `mail.gopretstudio.com` untuk digunakan sebagai email pendaftaran Alibaba Cloud.
- **Registrasi Akun Alibaba Cloud & Qwen Cloud**: Mengisi formulir, menangani kode verifikasi (OTP) secara langsung dari kotak masuk GoMail, menyetujui ketentuan layanan, dan mengaktifkan free tier benefit.
- **Human-Like Mouse Simulator**:
  - Menggunakan algoritma **Cubic Bezier** untuk pergerakan kursor mouse yang natural.
  - Penambahan tremor mikro (getaran tangan) yang berkurang saat mendekati target.
  - Simulasi akselerasi dan deselerasi kecepatan seret (speed profile).
  - Efek *overshoot* (tarikan berlebih) dan *recoil* (pantulan kembali ke kiri) sebelum melepaskan slider.
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

1. **Python 3.8+**
2. **Playwright** (beserta browser Chromium yang diperlukan)
3. **Rich** (untuk visualisasi terminal)

---

## 🚀 Panduan Instalasi & Penggunaan

### 1. Kloning Repositori
```bash
git clone https://github.com/Zeambut/Bot-Qwentil.git
cd Bot-Qwentil
```

### 2. Instal Dependensi
Instal pustaka Python yang dibutuhkan:
```bash
pip install playwright rich
```

Lalu, pasang browser biner Playwright:
```bash
playwright install chromium
```

### 3. Konfigurasi File `.env`
Buat file bernama `.env` di direktori utama proyek (jika belum ada) dan sesuaikan pengaturannya:

```env
# Password untuk akun Alibaba Cloud & GoMail yang akan didaftarkan (harus 8-20 karakter)
PASSWORD=Astral11*

# Jumlah akun per satu batch sebelum jeda (disarankan maksimal 2 untuk mencegah penalti IP)
ACCOUNTS_PER_RUN=2

# Jalankan browser tanpa GUI? (true = tersembunyi / headless, false = tampilkan jendela browser)
HEADLESS=true

# Jumlah worker yang berjalan bersamaan (concurrency)
CONCURRENCY=2

# Cooldown antar batch dalam satu run (detik)
COOLDOWN_BETWEEN_BATCHES=30

# Jeda setelah satu run selesai sebelum restart otomatis (detik)
# Set 0 untuk menonaktifkan auto-restart (bot berhenti setelah selesai)
RESTART_DELAY=15

# Batas berapa kali bot akan auto-restart (0 = tidak terbatas / loop selamanya)
MAX_RESTARTS=0
```

### 4. Jalankan Bot
Jalankan skrip utama menggunakan Python:
```bash
python qwen2.py
```

---

## 🖥️ Tampilan Dashboard CLI

Saat berjalan, Anda akan disuguhkan dashboard dinamis langsung di terminal Anda:

```text
⚡ PROSES PEMBUATAN AKUN QWEN CLOUD  Elapsed: 45s
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
✔ API Key OK / Aktif      : 1
✖ API Key DENIED          : 0
⚠ API Key UNELIGIBLE      : 0
💀 API Key DEAD/EXPIRED    : 0
✗ Gagal Registrasi Bot    : 1
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

Alat ini dibuat **hanya untuk tujuan edukasi dan penelitian** mengenai sistem deteksi otomasi dan pengujian antarmuka web. Penulis tidak bertanggung jawab atas penyalahgunaan alat ini yang melanggar Ketentuan Layanan (ToS) Alibaba Cloud atau platform terkait lainnya. Harap gunakan dengan bijak.

---

## 📝 Lisensi

Proyek ini dilisensikan di bawah lisensi MIT - lihat file [LICENSE](LICENSE) untuk detailnya.
