"""Smart Renamer: cocokkan file lokal dengan entri .m3u via fuzzy matching.

Strategi:
1. Baca .m3u -> daftar nama target (dari path: stem file)
2. Scan folder -> daftar file audio yang ada
3. Untuk tiap target, cari kandidat file lokal terbaik berdasar fuzz.ratio
   pada string yang sudah dinormalisasi (lowercase, buang noise YouTube)
4. Tandai status: MATCHED / NEEDS_RENAME / NOT_FOUND
5. Eksekusi rename hanya bila score >= threshold dan status NEEDS_RENAME
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Sequence, Set

from config import (
    AUDIO_EXTENSIONS,
    DEFAULT_FUZZY_THRESHOLD,
    PERFECT_MATCH_THRESHOLD,
)
from utils.filename_sanitizer import normalize_for_compare, sanitize_filename
from utils.m3u_parser import M3UEntry, parse_m3u

# Pakai thefuzz kalau ada (lebih cepat dengan rapidfuzz backend),
# fallback ke difflib agar app tetap jalan tanpa dependency tambahan.
try:
    from thefuzz import fuzz  # type: ignore

    def _ratio(a: str, b: str) -> int:
        # token_set_ratio lebih tahan terhadap urutan kata berbeda (mis. "Artist - Title" vs "Title")
        return int(fuzz.token_set_ratio(a, b))
except ImportError:  # pragma: no cover
    from difflib import SequenceMatcher

    def _ratio(a: str, b: str) -> int:
        return int(SequenceMatcher(None, a, b).ratio() * 100)


class MatchStatus(str, Enum):
    MATCHED = "Cocok"
    NEEDS_RENAME = "Butuh Rename"
    NOT_FOUND = "Tidak Ditemukan"


@dataclass
class MatchRow:
    """Satu baris hasil matching untuk ditampilkan di tabel UI."""
    m3u_title: str                       # Nama target (dari .m3u)
    target_filename: str                 # Nama file yang DIINGINKAN (target.mp3)
    local_filename: Optional[str]        # Nama file lokal saat ini (None bila tidak ketemu)
    local_path: Optional[Path]           # Path absolut file lokal
    score: int                           # Skor fuzzy 0-100
    status: MatchStatus
    new_path: Optional[Path] = None      # Path setelah rename (untuk preview)


@dataclass
class RenameReport:
    """Hasil eksekusi rename."""
    renamed: List[tuple[Path, Path]] = field(default_factory=list)
    skipped: List[tuple[Path, str]] = field(default_factory=list)  # (path, reason)
    errors: List[tuple[Path, str]] = field(default_factory=list)


def scan_audio_folder(folder: Path, extensions: Set[str] = AUDIO_EXTENSIONS) -> List[Path]:
    """Pindai folder (non-recursive) cari semua file audio."""
    folder = Path(folder)
    if not folder.is_dir():
        return []
    return sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in extensions
    )


def _target_filename_from_entry(entry: M3UEntry) -> str:
    """Ambil nama file yang diinginkan dari path .m3u (stem + ext)."""
    p = Path(entry.path)
    # Sanitasi karena path .m3u mungkin mengandung karakter yang tidak valid di filesystem lokal
    stem = sanitize_filename(p.stem)
    ext = p.suffix or ".mp3"
    return f"{stem}{ext}"


def build_match_table(
    m3u_path: Path,
    download_folder: Path,
    *,
    threshold: int = DEFAULT_FUZZY_THRESHOLD,
) -> List[MatchRow]:
    """Bangun tabel perbandingan M3U vs folder lokal."""
    entries = parse_m3u(m3u_path)
    local_files = scan_audio_folder(download_folder)

    # Pre-compute normalisasi nama lokal supaya tidak dihitung ulang per target
    local_norm = [(p, normalize_for_compare(p.stem)) for p in local_files]
    used: Set[Path] = set()  # Hindari satu file dipakai untuk dua target

    rows: List[MatchRow] = []
    for entry in entries:
        target_filename = _target_filename_from_entry(entry)
        target_norm = normalize_for_compare(Path(target_filename).stem)

        # Cari kandidat dengan skor tertinggi yang belum dipakai
        best: Optional[tuple[Path, int]] = None
        for path, norm in local_norm:
            if path in used:
                continue
            score = _ratio(target_norm, norm)
            if best is None or score > best[1]:
                best = (path, score)

        if best is None:
            rows.append(MatchRow(
                m3u_title=entry.title,
                target_filename=target_filename,
                local_filename=None,
                local_path=None,
                score=0,
                status=MatchStatus.NOT_FOUND,
            ))
            continue

        path, score = best
        # Tentukan status
        if path.name == target_filename:
            status = MatchStatus.MATCHED
            new_path = None
        elif score >= PERFECT_MATCH_THRESHOLD:
            # Konten sama persis, tapi nama file beda (mis. ekstensi atau case berbeda)
            status = MatchStatus.NEEDS_RENAME
            new_path = path.with_name(target_filename)
        elif score >= threshold:
            status = MatchStatus.NEEDS_RENAME
            new_path = path.with_name(target_filename)
        else:
            # Skor rendah -> jangan klaim kandidat ini
            rows.append(MatchRow(
                m3u_title=entry.title,
                target_filename=target_filename,
                local_filename=None,
                local_path=None,
                score=score,
                status=MatchStatus.NOT_FOUND,
            ))
            continue

        used.add(path)
        rows.append(MatchRow(
            m3u_title=entry.title,
            target_filename=target_filename,
            local_filename=path.name,
            local_path=path,
            score=score,
            status=status,
            new_path=new_path,
        ))

    return rows


def execute_rename(
    rows: Sequence[MatchRow],
    *,
    threshold: int = DEFAULT_FUZZY_THRESHOLD,
    dry_run: bool = False,
) -> RenameReport:
    """Eksekusi rename pada baris yang status-nya NEEDS_RENAME dan score >= threshold."""
    report = RenameReport()

    for row in rows:
        if row.status != MatchStatus.NEEDS_RENAME:
            continue
        if row.score < threshold:
            report.skipped.append((row.local_path, f"score {row.score} < threshold {threshold}"))
            continue
        if row.local_path is None or row.new_path is None:
            continue

        src = row.local_path
        dst = row.new_path

        if dst.exists() and dst.resolve() != src.resolve():
            report.skipped.append((src, f"target sudah ada: {dst.name}"))
            continue

        if dry_run:
            report.renamed.append((src, dst))
            continue

        try:
            src.rename(dst)
            report.renamed.append((src, dst))
        except OSError as e:
            report.errors.append((src, str(e)))

    return report
