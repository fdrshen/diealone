"""Wrapper untuk spotdl / yt-dlp dengan output stream baris-per-baris.

Pakai subprocess.Popen agar stdout bisa dibaca real-time dan ditampilkan di UI Streamlit.
"""
from __future__ import annotations

import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, List, Optional

from config import DEFAULT_AUDIO_FORMAT, SPOTDL_OUTPUT_FORMAT


class DownloaderError(RuntimeError):
    """Error dari proses downloader (binary tidak ada, exit code != 0, dll)."""


@dataclass
class DownloadResult:
    """Hasil akhir proses download."""
    return_code: int
    output_dir: Path
    tool: str  # 'spotdl' atau 'yt-dlp'


def _which_or_raise(binary: str) -> str:
    """Pastikan binary ada di PATH, kalau tidak raise dengan pesan jelas."""
    path = shutil.which(binary)
    if not path:
        raise DownloaderError(
            f"'{binary}' tidak ditemukan di PATH. "
            f"Install dengan: pip install {binary}"
        )
    return path


def build_spotdl_command(
    spotify_url: str,
    output_dir: Path,
    audio_format: str = DEFAULT_AUDIO_FORMAT,
    output_template: str = SPOTDL_OUTPUT_FORMAT,
) -> List[str]:
    """Susun command spotdl dengan output template konsisten.

    spotdl docs: 'spotdl download <url> --output "{title}" --format mp3'
    """
    return [
        _which_or_raise("spotdl"),
        "download",
        spotify_url,
        "--output", str(output_dir / output_template),
        "--format", audio_format,
    ]


def build_ytdlp_command(
    url: str,
    output_dir: Path,
    audio_format: str = DEFAULT_AUDIO_FORMAT,
) -> List[str]:
    """Susun command yt-dlp untuk ekstrak audio saja."""
    return [
        _which_or_raise("yt-dlp"),
        "-x",                              # extract audio
        "--audio-format", audio_format,
        "-o", str(output_dir / "%(title)s.%(ext)s"),
        url,
    ]


def stream_download(
    command: List[str],
    output_dir: Path,
) -> Generator[str, None, DownloadResult]:
    """Jalankan command sebagai subprocess, yield setiap baris stdout/stderr.

    Pemakaian:
        gen = stream_download(cmd, out)
        for line in gen:
            print(line)
        # generator return value (exit code, dll) bisa diambil dari StopIteration.value
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Tampilkan command (di-quote agar mudah dicopy ke terminal)
    yield f"$ {' '.join(shlex.quote(c) for c in command)}"

    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,   # gabung stderr ke stdout supaya urutan log tetap
        text=True,
        bufsize=1,                  # line-buffered
        encoding="utf-8",
        errors="replace",
    )

    assert proc.stdout is not None
    try:
        for raw_line in proc.stdout:
            line = raw_line.rstrip("\n")
            if line:
                yield line
    finally:
        proc.stdout.close()
        proc.wait()

    tool = Path(command[0]).name
    return DownloadResult(return_code=proc.returncode, output_dir=output_dir, tool=tool)


def download_with_spotdl(
    spotify_url: str,
    output_dir: Path,
    audio_format: str = DEFAULT_AUDIO_FORMAT,
) -> Generator[str, None, DownloadResult]:
    """High-level: download via spotdl dengan output template '{title}'."""
    cmd = build_spotdl_command(spotify_url, output_dir, audio_format)
    return stream_download(cmd, output_dir)


def download_with_ytdlp(
    url: str,
    output_dir: Path,
    audio_format: str = DEFAULT_AUDIO_FORMAT,
) -> Generator[str, None, DownloadResult]:
    """High-level: download via yt-dlp (audio-only)."""
    cmd = build_ytdlp_command(url, output_dir, audio_format)
    return stream_download(cmd, output_dir)


def check_tool_available(tool: str) -> Optional[str]:
    """Cek apakah tool tersedia. Return path-nya atau None."""
    return shutil.which(tool)
