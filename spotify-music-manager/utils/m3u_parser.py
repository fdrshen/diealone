"""Parser dan writer file .m3u / .m3u8 (extended)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass
class M3UEntry:
    """Satu entri di playlist .m3u."""
    title: str          # Judul lagu (tanpa path/ekstensi), dipakai untuk rename
    path: str           # Path lengkap di file .m3u (mis. /storage/emulated/0/Music/Foo.mp3)
    duration: int = -1  # Durasi detik (-1 jika tidak diketahui)
    artist: str = ""    # Artis (opsional, dipakai di #EXTINF)


def write_m3u(
    entries: Iterable[M3UEntry],
    output_path: Path,
    *,
    extended: bool = True,
) -> Path:
    """Tulis daftar entri ke file .m3u (UTF-8, format extended bila diminta)."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: List[str] = []
    if extended:
        lines.append("#EXTM3U")

    for e in entries:
        if extended:
            display = f"{e.artist} - {e.title}" if e.artist else e.title
            lines.append(f"#EXTINF:{e.duration},{display}")
        lines.append(e.path)

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def parse_m3u(m3u_path: Path) -> List[M3UEntry]:
    """Baca file .m3u dan kembalikan list M3UEntry.

    Mendukung format simple (path saja per baris) dan extended (#EXTINF).
    """
    m3u_path = Path(m3u_path)
    text = m3u_path.read_text(encoding="utf-8", errors="replace")
    entries: List[M3UEntry] = []

    pending_title = ""
    pending_artist = ""
    pending_duration = -1

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF:"):
            # Format: #EXTINF:duration,Artist - Title  (artist opsional)
            payload = line[len("#EXTINF:"):]
            if "," in payload:
                dur_str, display = payload.split(",", 1)
                try:
                    pending_duration = int(float(dur_str.strip()))
                except ValueError:
                    pending_duration = -1
                if " - " in display:
                    pending_artist, pending_title = display.split(" - ", 1)
                    pending_artist = pending_artist.strip()
                    pending_title = pending_title.strip()
                else:
                    pending_title = display.strip()
            continue
        if line.startswith("#"):
            # Komentar/extension lain, skip
            continue

        # Ini baris path. Title fallback = stem path.
        title = pending_title or Path(line).stem
        entries.append(M3UEntry(
            title=title,
            path=line,
            duration=pending_duration,
            artist=pending_artist,
        ))
        pending_title = ""
        pending_artist = ""
        pending_duration = -1

    return entries
