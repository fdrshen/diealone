# 🎵 Spotify Local Music Manager

Aplikasi web lokal berbasis **Streamlit** untuk mengotomatisasi migrasi koleksi musik dari Spotify ke perangkat Android Anda. Tiga fungsi utama dalam satu dashboard:

1. **Downloader** — unduh playlist Spotify via `spotdl` atau URL apapun via `yt-dlp`.
2. **Playlist Generator** — convert daftar lagu (CSV Exportify atau Spotify API) menjadi `.m3u` dengan path Android (`/storage/emulated/0/Music/...`).
3. **Smart Renamer** — bandingkan file lokal dengan target `.m3u` lewat **fuzzy matching** (`thefuzz`/`rapidfuzz`), lalu rename otomatis agar cocok.

---

## 📁 Struktur Proyek

```
spotify-music-manager/
├── app.py                      # Entry point Streamlit (3 tab)
├── config.py                   # Konfigurasi (path, threshold, format)
├── requirements.txt
├── README.md
├── modules/
│   ├── downloader.py           # Wrapper spotdl/yt-dlp + streaming log
│   ├── playlist_generator.py   # CSV/Spotify API -> .m3u Android
│   └── smart_renamer.py        # Fuzzy matching + rename engine
└── utils/
    ├── filename_sanitizer.py   # Sanitasi nama file lintas-OS
    └── m3u_parser.py           # Parser/writer .m3u extended
```

**Prinsip arsitektur:** logic bisnis di `modules/`, helper murni di `utils/`, presentation di `app.py`. Setiap modul stateless dan bisa dipakai tanpa Streamlit (mudah di-test/di-CLI-kan).

---

## 🛠️ Instalasi

### 1. Persiapkan Python 3.10+

```bash
python3 --version   # pastikan >= 3.10
```

### 2. Buat virtual environment

```bash
cd spotify-music-manager
python3 -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows PowerShell
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> `spotdl` dan `yt-dlp` butuh **FFmpeg** untuk konversi audio:
> - **Ubuntu/Debian:** `sudo apt install ffmpeg`
> - **macOS:** `brew install ffmpeg`
> - **Windows:** download dari <https://www.gyan.dev/ffmpeg/builds/> dan tambahkan ke PATH

### 4. Jalankan aplikasi

```bash
streamlit run app.py
```

Buka <http://localhost:8501> di browser.

---

## 🚀 Cara Pakai

### Tab 1 — Downloader

1. Masukkan URL playlist Spotify (atau YouTube kalau pilih `yt-dlp`).
2. Pilih folder output dan format (default `mp3`).
3. Klik **Mulai Download** → log akan streaming live.

> Format output `spotdl` dipaksa ke `{title}` (lihat `config.py` → `SPOTDL_OUTPUT_FORMAT`) agar konsisten dengan path di file `.m3u`.

### Tab 2 — Playlist Generator

**Opsi A — CSV (paling mudah):**
1. Export playlist Anda dengan [Exportify](https://exportify.net).
2. Upload CSV-nya di aplikasi.
3. Klik **Generate file .m3u** → file tersimpan di `playlists/` dan bisa di-download.

**Opsi B — Spotify Web API:**
1. Buat app di [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) untuk mendapatkan `Client ID` & `Client Secret`.
2. Masukkan playlist URL + kredensial → klik **Ambil daftar lagu**.

Format path di `.m3u` (extended):
```
#EXTM3U
#EXTINF:215,Artist - Track Title
/storage/emulated/0/Music/Track Title.mp3
```

### Tab 3 — Smart Renamer

1. Pilih file `.m3u` (otomatis mendeteksi yang ada di folder `playlists/`, atau upload manual).
2. Pilih folder unduhan yang berisi file audio.
3. Atur **threshold kemiripan** (default 75%).
4. Klik **Pindai & Bandingkan** → tampil tabel:

   | Nama di M3U | Nama File Lokal Saat Ini | Status |
   |---|---|---|
   | `Bohemian Rhapsody.mp3` | `Queen - Bohemian Rhapsody (Official) (95%)` | Butuh Rename |
   | `Imagine.mp3` | `Imagine.mp3 (100%)` | Cocok |

5. Klik **Preview (Dry Run)** untuk lihat rencana, lalu **Eksekusi Rename Otomatis** untuk apply.

---

## 🧠 Logika Fuzzy Matching

`modules/smart_renamer.py` memakai `fuzz.token_set_ratio` (dari `thefuzz` + `rapidfuzz`) yang tahan terhadap:
- urutan kata berbeda (`"Title - Artist"` vs `"Artist - Title"`)
- noise YouTube (`"(Official Video)"`, `"[Audio HD]"`, `" - Topic"`) — dibuang dulu di `utils.filename_sanitizer.normalize_for_compare`

Status diputuskan begini:
- **MATCHED** — nama file sudah persis sama dengan target.
- **NEEDS_RENAME** — skor ≥ threshold, akan di-rename ke target.
- **NOT_FOUND** — tidak ada kandidat dengan skor cukup.

Kalau `thefuzz` tidak terpasang, modul fallback ke `difflib.SequenceMatcher` agar tetap jalan.

---

## ⚙️ Konfigurasi

Edit `config.py`:

| Variabel | Default | Fungsi |
|---|---|---|
| `DEFAULT_DOWNLOAD_DIR` | `./downloads` | Folder unduhan |
| `DEFAULT_PLAYLIST_DIR` | `./playlists` | Folder file `.m3u` |
| `ANDROID_MUSIC_BASE_PATH` | `/storage/emulated/0/Music` | Base path di Android |
| `SPOTDL_OUTPUT_FORMAT` | `{title}` | Template nama file spotdl |
| `DEFAULT_FUZZY_THRESHOLD` | `75` | Threshold rename |
| `AUDIO_EXTENSIONS` | `mp3, m4a, flac, ogg, opus, wav, aac` | Yang dipindai |

---

## 🐛 Troubleshooting

- **`spotdl: command not found`** — jalankan ulang `pip install -r requirements.txt` di venv yang aktif. Cek dengan `which spotdl`.
- **Lagu ter-download tapi tidak terdeteksi di Smart Renamer** — pastikan ekstensinya ada di `AUDIO_EXTENSIONS`. Tab Smart Renamer scan **non-rekursif** — taruh file langsung di folder yang dipindai.
- **Banyak status "Tidak Ditemukan"** — turunkan threshold ke 60–65, atau cek apakah `spotdl` menambahkan suffix tak terduga (`--output "{title}"` seharusnya mencegah ini).
