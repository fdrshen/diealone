"""Utilitas sanitasi nama file agar aman dipakai di filesystem (Windows/Linux/Android)."""
import re
import unicodedata

# Karakter yang dilarang di Windows + control char
_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
# Whitespace berlebih
_MULTI_SPACE = re.compile(r"\s+")


def sanitize_filename(name: str, max_length: int = 200) -> str:
    """Sanitasi string menjadi nama file yang valid lintas-OS.

    - Hapus karakter ilegal
    - Normalize unicode
    - Trim whitespace berlebih
    - Hindari trailing dot/space (Windows)
    """
    if not name:
        return "untitled"

    # Normalize unicode (NFKC) supaya karakter aksen tetap tapi konsisten
    name = unicodedata.normalize("NFKC", name)

    # Ganti karakter ilegal dengan spasi
    cleaned = _ILLEGAL_CHARS.sub(" ", name)

    # Rapikan whitespace
    cleaned = _MULTI_SPACE.sub(" ", cleaned).strip()

    # Hapus trailing dot/space (Windows tidak suka)
    cleaned = cleaned.rstrip(". ")

    # Truncate kalau kepanjangan
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip(". ")

    return cleaned or "untitled"


def normalize_for_compare(name: str) -> str:
    """Normalisasi untuk perbandingan fuzzy: lowercase + buang ekstensi + buang noise.

    Contoh noise yang dibuang: ' (Official Video)', ' [Audio]', ' - Topic', dst.
    """
    # Buang ekstensi kalau ada
    name = re.sub(r"\.[a-zA-Z0-9]{2,5}$", "", name)
    name = name.lower()
    # Buang konten dalam kurung yang sering jadi noise YouTube
    name = re.sub(r"[\(\[].*?(official|video|audio|lyrics?|hd|mv|m/?v|topic).*?[\)\]]",
                  " ", name)
    # Buang " - Topic"
    name = re.sub(r"\s*-\s*topic\b", " ", name)
    name = _MULTI_SPACE.sub(" ", name).strip()
    return name
