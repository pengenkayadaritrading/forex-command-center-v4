# Forex Command Center V4 — website online multi-user

## Penting: batasan V4

Ini adalah **versi cloud berbasis unggahan CSV**, bukan koneksi MT5 langsung. Setiap kawan mendaftar dengan email dan password khusus WEBSITE (bukan password HFM), lalu mengunggah laporan CSV miliknya. Data disimpan dengan `user_id` dan setiap query membatasi data ke pengguna yang login. **Tidak ada pengambilan saldo/equity/Bid/Ask live atau login broker.** Jangan mengklaim ini sebagai koneksi HFM live. Tidak ada fitur order trading.

V3 lokal tidak diubah. Jangan mengunggah `app_v3.py` ke hosting cloud: terminal MT5 yang sama bisa membocorkan data antar-pengguna.

## Menjalankan di Windows untuk tes (opsional)

1. Ekstrak ZIP. Buka PowerShell di folder `ForexCommandCenter_V4`.
2. `py -m venv .venv`
3. `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`
4. `$env:SECRET_KEY = (py -c "import secrets; print(secrets.token_urlsafe(48))")`
5. `$env:COOKIE_SECURE = "0"` (hanya tes HTTP lokal)
6. `.\.venv\Scripts\python.exe app.py`
7. Buka `http://127.0.0.1:5000`.

## Membuat WEBSITE ONLINE di Render + GitHub (tanpa localhost)

1. Buat akun GitHub dan Render. Jangan unggah file `.env`, password broker, atau database lokal.
2. Di GitHub, buat repository baru **Private**, misalnya `forex-command-center-v4`.
3. Klik **Add file → Upload files**, unggah isi folder V4 (bukan ZIP sebagai satu file). Pastikan `app.py`, `requirements.txt`, `render.yaml`, folder `templates`, dan folder `static` berada di root repository. Commit.
4. Buka Render Dashboard → **New → Blueprint**; hubungkan GitHub dan pilih repository V4. Render membaca `render.yaml`.
5. Tinjau biaya yang ditampilkan Render: konfigurasi contoh menggunakan web `starter` dan PostgreSQL `basic-256mb`, **bukan gratis**. Jangan konfirmasi sebelum cocok dengan biaya yang ditampilkan.
6. Deploy Blueprint. Render mengatur `SECRET_KEY` acak, database URL, dan HTTPS. Tunggu status **Live**.
7. Klik URL publik `https://...onrender.com` dari dashboard Render (URL final ditentukan Render). Buka `/register`, buat akun sendiri, lalu minta kawan membuat akun terpisah.
8. Uji privasi: unggah CSV contoh di akun A; logout; daftar akun B; pastikan data A tidak tampil di B.
9. Gunakan domain khusus jika mau: Render → service → Settings → Custom Domains, lalu atur DNS sesuai instruksi Render.

**Catatan:** Fitur pendaftaran publik terbuka. Untuk produksi yang melibatkan uang/riwayat finansial, tambahkan verifikasi email, pembatasan percobaan login, reset password, audit keamanan, kebijakan retensi data, backup, dan monitoring sebelum menyebarkan luas. Password website disimpan dalam bentuk hash; sesi memakai cookie bertanda tangan dan HTTPS. Database cloud harus dibackup sesuai kebutuhan.

## Format CSV

**Transaksi**: `deal_id,time,symbol,side,volume,price,profit` (+ opsional `commission,swap,fee`). Waktu UTC. `deal_id` unik per pengguna.

**Candle**: `time,open,high,low,close` (+ opsional `volume`). Pilih timeframe saat unggah. Contoh ada di `static/contoh_deals.csv` dan `static/contoh_candles.csv`.

CSV standar MT5 sering punya format berbeda; perlu diekspor/dirapikan ke kolom di atas. V4 belum mendukung laporan HTML langsung. Nilai P/L adalah penjumlahan deal yang diunggah, bukan saldo akun. Tidak ada auto-refresh harga.

## Jika ingin koneksi HFM live di masa depan

Perlu integrasi broker/cloud MT5 yang benar-benar mendukung banyak akun terisolasi, manajemen kredensial terenkripsi, hak akses per pengguna, dan biaya provider. Jangan menaruh password master MT5 di frontend atau memakai satu terminal MT5 untuk semua pengunjung.
