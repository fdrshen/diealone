"""Konfigurasi global aplikasi Spotify Local Music Manager."""
from pathlib import Path

# Direktori default untuk hasil unduhan (relatif ke root proyek)
DEFAULT_DOWNLOAD_DIR = Path("downloads").resolve()

# Direktori default untuk menyimpan file .m3u
DEFAULT_PLAYLIST_DIR = Path("playlists").resolve()

# Path Android internal untuk file .m3u (sesuai standar storage Android)
ANDROID_MUSIC_BASE_PATH = "/storage/emulated/0/Music"

# Format output spotdl yang konsisten (hanya judul lagu)
# Referensi: https://spotdl.readthedocs.io/en/latest/usage/#output
SPOTDL_OUTPUT_FORMAT = "{title}"

# Format audio default
DEFAULT_AUDIO_FORMAT = "mp3"

# Threshold fuzzy matching (0-100). File dengan kemiripan di atas ini dianggap kandidat rename.
DEFAULT_FUZZY_THRESHOLD = 75

# Threshold "match sempurna" - di atas ini dianggap sudah cocok, tidak perlu rename
PERFECT_MATCH_THRESHOLD = 98

# Ekstensi audio yang dipindai oleh smart renamer
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".flac", ".ogg", ".opus", ".wav", ".aac"}
