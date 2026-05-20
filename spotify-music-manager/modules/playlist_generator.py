"""Generator file .m3u dari sumber CSV (export Exportify) atau Spotify API.

Output path mengikuti standar Android internal:
    /storage/emulated/0/Music/{Nama_Lagu}.mp3
"""
from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from config import ANDROID_MUSIC_BASE_PATH, DEFAULT_AUDIO_FORMAT
from utils.filename_sanitizer import sanitize_filename
from utils.m3u_parser import M3UEntry, write_m3u


# Kolom yang biasa muncul di CSV export dari Exportify / Spotify Web API
_TITLE_COLS = ("Track Name", "track_name", "name", "Title", "title")
_ARTIST_COLS = ("Artist Name(s)", "artist_name", "artist", "Artists", "artists")
_DURATION_COLS = ("Duration (ms)", "duration_ms", "duration")


def _pick(row: dict, candidates: Sequence[str]) -> str:
    for c in candidates:
        if c in row and row[c]:
            return str(row[c]).strip()
    return ""


def _parse_duration_seconds(raw: str) -> int:
    """Parse durasi dari string (ms atau s) ke detik. Return -1 jika gagal."""
    if not raw:
        return -1
    try:
        val = float(raw)
    except ValueError:
        return -1
    # Heuristik: kalau > 10000 anggap milidetik
    if val > 10000:
        return int(val / 1000)
    return int(val)


def parse_csv_tracks(csv_text: str) -> List[dict]:
    """Parse CSV (Exportify-style) menjadi list dict {title, artist, duration}."""
    reader = csv.DictReader(StringIO(csv_text))
    tracks: List[dict] = []
    for row in reader:
        title = _pick(row, _TITLE_COLS)
        if not title:
            continue
        tracks.append({
            "title": title,
            "artist": _pick(row, _ARTIST_COLS),
            "duration": _parse_duration_seconds(_pick(row, _DURATION_COLS)),
        })
    return tracks


def build_android_path(
    title: str,
    *,
    artist: str = "",
    base_path: str = ANDROID_MUSIC_BASE_PATH,
    extension: str = DEFAULT_AUDIO_FORMAT,
    include_artist: bool = False,
) -> str:
    """Bangun path absolut untuk perangkat Android.

    Default: /storage/emulated/0/Music/{Title}.mp3
    Kalau include_artist=True: /storage/emulated/0/Music/{Artist} - {Title}.mp3
    """
    if include_artist and artist:
        filename = sanitize_filename(f"{artist} - {title}")
    else:
        filename = sanitize_filename(title)
    base = base_path.rstrip("/")
    return f"{base}/{filename}.{extension.lstrip('.')}"


def tracks_to_m3u_entries(
    tracks: Iterable[dict],
    *,
    base_path: str = ANDROID_MUSIC_BASE_PATH,
    extension: str = DEFAULT_AUDIO_FORMAT,
    include_artist_in_filename: bool = False,
) -> List[M3UEntry]:
    """Konversi list track dict -> list M3UEntry dengan path Android."""
    entries: List[M3UEntry] = []
    for t in tracks:
        title = t.get("title", "").strip()
        if not title:
            continue
        artist = t.get("artist", "").strip()
        path = build_android_path(
            title,
            artist=artist,
            base_path=base_path,
            extension=extension,
            include_artist=include_artist_in_filename,
        )
        entries.append(M3UEntry(
            title=title,
            path=path,
            duration=int(t.get("duration", -1) or -1),
            artist=artist,
        ))
    return entries


def generate_m3u_from_csv(
    csv_text: str,
    output_m3u: Path,
    *,
    base_path: str = ANDROID_MUSIC_BASE_PATH,
    extension: str = DEFAULT_AUDIO_FORMAT,
    include_artist_in_filename: bool = False,
) -> tuple[Path, List[M3UEntry]]:
    """Pipeline lengkap: CSV string -> file .m3u. Return (path, entries)."""
    tracks = parse_csv_tracks(csv_text)
    entries = tracks_to_m3u_entries(
        tracks,
        base_path=base_path,
        extension=extension,
        include_artist_in_filename=include_artist_in_filename,
    )
    out = write_m3u(entries, output_m3u, extended=True)
    return out, entries


# --- Sumber alternatif: Spotify Web API (opsional) -------------------------

def fetch_tracks_from_spotify_api(
    playlist_url_or_id: str,
    client_id: str,
    client_secret: str,
) -> List[dict]:
    """Ambil daftar lagu dari Spotify Web API menggunakan Spotipy.

    Memerlukan paket 'spotipy' dan kredensial Spotify Developer.
    """
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials
    except ImportError as e:
        raise RuntimeError(
            "Paket 'spotipy' belum terpasang. Jalankan: pip install spotipy"
        ) from e

    auth = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    sp = spotipy.Spotify(auth_manager=auth)

    # Ekstrak playlist ID dari URL kalau perlu
    playlist_id = playlist_url_or_id
    if "playlist/" in playlist_id:
        playlist_id = playlist_id.split("playlist/")[1].split("?")[0]

    tracks: List[dict] = []
    results = sp.playlist_items(playlist_id, additional_types=("track",))
    while results:
        for item in results.get("items", []):
            tr = item.get("track")
            if not tr:
                continue
            tracks.append({
                "title": tr.get("name", ""),
                "artist": ", ".join(a["name"] for a in tr.get("artists", [])),
                "duration": int(tr.get("duration_ms", 0) / 1000),
            })
        results = sp.next(results) if results.get("next") else None
    return tracks
