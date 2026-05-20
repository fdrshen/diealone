"""Spotify Local Music Manager — Streamlit dashboard.

Jalankan dengan:
    streamlit run app.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from config import (
    ANDROID_MUSIC_BASE_PATH,
    DEFAULT_AUDIO_FORMAT,
    DEFAULT_DOWNLOAD_DIR,
    DEFAULT_FUZZY_THRESHOLD,
    DEFAULT_PLAYLIST_DIR,
)
from modules.downloader import (
    DownloaderError,
    check_tool_available,
    download_with_spotdl,
    download_with_ytdlp,
)
from modules.playlist_generator import (
    fetch_tracks_from_spotify_api,
    generate_m3u_from_csv,
    tracks_to_m3u_entries,
)
from modules.smart_renamer import (
    MatchStatus,
    build_match_table,
    execute_rename,
)
from utils.m3u_parser import write_m3u

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Spotify Local Music Manager",
    page_icon="🎵",
    layout="wide",
)

st.title("🎵 Spotify Local Music Manager")
st.caption(
    "Otomatisasi unduhan, generate playlist .m3u, dan smart-rename file lokal "
    "untuk migrasi koleksi musik dari Spotify."
)

# Persisten state default
DEFAULT_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_PLAYLIST_DIR.mkdir(parents=True, exist_ok=True)

tab_dl, tab_gen, tab_ren = st.tabs([
    "⬇️  Downloader",
    "📝  Playlist Generator",
    "🪄  Smart Renamer",
])

# ===========================================================================
# TAB 1 — DOWNLOADER
# ===========================================================================
with tab_dl:
    st.header("Downloader")
    st.write("Unduh lagu dari Spotify (via `spotdl`) atau YouTube/SoundCloud (via `yt-dlp`).")

    col_a, col_b = st.columns([3, 1])
    with col_a:
        url = st.text_input(
            "URL Playlist / Track",
            placeholder="https://open.spotify.com/playlist/...",
        )
    with col_b:
        tool = st.selectbox("Tool", ["spotdl", "yt-dlp"], index=0)

    col_c, col_d = st.columns(2)
    with col_c:
        out_dir = st.text_input("Folder Output", value=str(DEFAULT_DOWNLOAD_DIR))
    with col_d:
        audio_format = st.selectbox(
            "Format Audio",
            ["mp3", "m4a", "opus", "flac", "wav"],
            index=["mp3", "m4a", "opus", "flac", "wav"].index(DEFAULT_AUDIO_FORMAT),
        )

    # Status ketersediaan tool
    tool_path = check_tool_available(tool)
    if tool_path:
        st.caption(f"✅ `{tool}` ditemukan: `{tool_path}`")
    else:
        st.caption(f"⚠️  `{tool}` tidak ada di PATH. Lihat instruksi instalasi di README.")

    if st.button("🚀 Mulai Download", type="primary", disabled=not url):
        log_box = st.empty()
        log_lines: list[str] = []

        try:
            if tool == "spotdl":
                gen = download_with_spotdl(url, Path(out_dir), audio_format)
            else:
                gen = download_with_ytdlp(url, Path(out_dir), audio_format)

            # Konsumsi generator dan tampilkan log live
            with st.spinner(f"Menjalankan {tool}..."):
                while True:
                    try:
                        line = next(gen)
                    except StopIteration as stop:
                        result = stop.value
                        break
                    log_lines.append(line)
                    log_box.code("\n".join(log_lines[-200:]), language="bash")

            if result.return_code == 0:
                st.success(f"Selesai. Tersimpan di: `{result.output_dir}`")
            else:
                st.error(f"{tool} keluar dengan kode {result.return_code}. Cek log.")

        except DownloaderError as e:
            st.error(str(e))
        except Exception as e:  # pragma: no cover
            st.exception(e)

# ===========================================================================
# TAB 2 — PLAYLIST GENERATOR
# ===========================================================================
with tab_gen:
    st.header("Playlist Generator (.m3u)")
    st.write(
        f"Buat file `.m3u` dengan path Android: "
        f"`{ANDROID_MUSIC_BASE_PATH}/<Nama_Lagu>.<ext>`"
    )

    source = st.radio(
        "Sumber daftar lagu",
        ["📄 CSV (Exportify)", "🎧 Spotify Web API"],
        horizontal=True,
    )

    # --- Opsi output ---
    col1, col2, col3 = st.columns(3)
    with col1:
        m3u_name = st.text_input("Nama file .m3u", value="playlist.m3u")
    with col2:
        ext = st.selectbox(
            "Ekstensi target",
            ["mp3", "m4a", "opus", "flac"],
            index=0,
        )
    with col3:
        include_artist = st.checkbox(
            "Sertakan artis di nama file",
            value=False,
            help="Kalau dicentang: '{Artist} - {Title}.mp3'. Kalau tidak: '{Title}.mp3' (sesuai default spotdl).",
        )

    base_path = st.text_input(
        "Base path Android",
        value=ANDROID_MUSIC_BASE_PATH,
        help="Lokasi folder musik di perangkat Android.",
    )

    tracks: list[dict] = []

    if source.startswith("📄"):
        st.markdown(
            "Export playlist Spotify Anda dengan "
            "[Exportify](https://exportify.net) lalu upload CSV-nya di sini."
        )
        uploaded = st.file_uploader("Upload CSV", type=["csv"])
        if uploaded is not None:
            csv_text = uploaded.read().decode("utf-8", errors="replace")
            from modules.playlist_generator import parse_csv_tracks
            tracks = parse_csv_tracks(csv_text)
            st.info(f"Terdeteksi **{len(tracks)}** lagu di CSV.")
    else:
        st.markdown(
            "Memerlukan kredensial dari "
            "[Spotify Developer Dashboard](https://developer.spotify.com/dashboard)."
        )
        with st.form("spotify_api_form"):
            playlist_url = st.text_input("Playlist URL atau ID")
            client_id = st.text_input("Client ID", type="password")
            client_secret = st.text_input("Client Secret", type="password")
            fetch = st.form_submit_button("Ambil daftar lagu")
        if fetch and playlist_url and client_id and client_secret:
            try:
                with st.spinner("Mengambil dari Spotify API..."):
                    tracks = fetch_tracks_from_spotify_api(
                        playlist_url, client_id, client_secret,
                    )
                st.success(f"Berhasil mengambil **{len(tracks)}** lagu.")
            except Exception as e:
                st.error(f"Gagal: {e}")

    # --- Preview & Generate ---
    if tracks:
        entries = tracks_to_m3u_entries(
            tracks,
            base_path=base_path,
            extension=ext,
            include_artist_in_filename=include_artist,
        )
        df_preview = pd.DataFrame([
            {"Title": e.title, "Artist": e.artist, "Path (.m3u)": e.path}
            for e in entries
        ])
        st.subheader("Preview")
        st.dataframe(df_preview, use_container_width=True, hide_index=True)

        if st.button("💾 Generate file .m3u", type="primary"):
            out_path = DEFAULT_PLAYLIST_DIR / m3u_name
            write_m3u(entries, out_path, extended=True)
            st.success(f"File ditulis: `{out_path}`")
            st.download_button(
                "⬇️  Download .m3u",
                data=out_path.read_bytes(),
                file_name=out_path.name,
                mime="audio/x-mpegurl",
            )

# ===========================================================================
# TAB 3 — SMART RENAMER
# ===========================================================================
with tab_ren:
    st.header("Smart Renamer")
    st.write(
        "Bandingkan file di folder unduhan dengan target dari `.m3u` menggunakan "
        "**fuzzy matching**, lalu rename file lokal agar 100% cocok."
    )

    col1, col2 = st.columns(2)
    with col1:
        m3u_files = sorted(DEFAULT_PLAYLIST_DIR.glob("*.m3u*"))
        m3u_choice = st.selectbox(
            "File .m3u",
            options=["(upload manual)"] + [str(p) for p in m3u_files],
        )
        uploaded_m3u = None
        if m3u_choice == "(upload manual)":
            uploaded_m3u = st.file_uploader("Upload .m3u", type=["m3u", "m3u8"])
    with col2:
        scan_dir = st.text_input(
            "Folder unduhan untuk dipindai",
            value=str(DEFAULT_DOWNLOAD_DIR),
        )

    threshold = st.slider(
        "Threshold kemiripan (%) untuk auto-rename",
        min_value=50, max_value=100,
        value=DEFAULT_FUZZY_THRESHOLD,
        help="File di atas threshold ini akan di-rename agar cocok dengan .m3u.",
    )

    # Tentukan path m3u yang akan dipakai
    m3u_path: Path | None = None
    if uploaded_m3u is not None:
        tmp = DEFAULT_PLAYLIST_DIR / f"_uploaded_{uploaded_m3u.name}"
        tmp.write_bytes(uploaded_m3u.getvalue())
        m3u_path = tmp
    elif m3u_choice and m3u_choice != "(upload manual)":
        m3u_path = Path(m3u_choice)

    if st.button("🔍 Pindai & Bandingkan", disabled=not m3u_path):
        if not Path(scan_dir).is_dir():
            st.error(f"Folder tidak ditemukan: `{scan_dir}`")
        else:
            with st.spinner("Menghitung kemiripan..."):
                rows = build_match_table(m3u_path, Path(scan_dir), threshold=threshold)
            st.session_state["match_rows"] = rows
            st.session_state["scan_dir"] = scan_dir
            st.session_state["threshold"] = threshold

    rows = st.session_state.get("match_rows")
    if rows:
        # Ringkasan
        n_matched = sum(1 for r in rows if r.status == MatchStatus.MATCHED)
        n_rename = sum(1 for r in rows if r.status == MatchStatus.NEEDS_RENAME)
        n_missing = sum(1 for r in rows if r.status == MatchStatus.NOT_FOUND)
        m1, m2, m3 = st.columns(3)
        m1.metric("✅ Cocok", n_matched)
        m2.metric("✏️  Butuh Rename", n_rename)
        m3.metric("❌ Tidak Ditemukan", n_missing)

        # Tabel visualisasi sesuai requirement:
        # [Nama di M3U] | [Nama File Lokal Saat Ini (Kemiripan X%)] | [Status]
        df = pd.DataFrame([
            {
                "Nama di M3U": r.target_filename,
                "Nama File Lokal Saat Ini": (
                    f"{r.local_filename} ({r.score}%)" if r.local_filename
                    else "— (tidak ditemukan)"
                ),
                "Status": r.status.value,
                "Akan diubah menjadi": r.new_path.name if r.new_path else "",
            }
            for r in rows
        ])

        def _highlight(row):
            color = {
                MatchStatus.MATCHED.value: "background-color: #1f4d2b; color: #d4edda",
                MatchStatus.NEEDS_RENAME.value: "background-color: #5c4a1a; color: #fff3cd",
                MatchStatus.NOT_FOUND.value: "background-color: #5a1f24; color: #f8d7da",
            }.get(row["Status"], "")
            return [color] * len(row)

        st.dataframe(
            df.style.apply(_highlight, axis=1),
            use_container_width=True,
            hide_index=True,
        )

        # --- Eksekusi ---
        st.divider()
        st.subheader("Eksekusi Rename")
        col_x, col_y = st.columns(2)
        with col_x:
            if st.button("👁️  Preview (Dry Run)"):
                report = execute_rename(
                    rows,
                    threshold=st.session_state["threshold"],
                    dry_run=True,
                )
                st.info(f"Akan me-rename **{len(report.renamed)}** file (dry-run).")
                for src, dst in report.renamed:
                    st.write(f"`{src.name}` → `{dst.name}`")
        with col_y:
            if st.button("⚡ Eksekusi Rename Otomatis", type="primary"):
                report = execute_rename(
                    rows,
                    threshold=st.session_state["threshold"],
                    dry_run=False,
                )
                st.success(f"Berhasil rename **{len(report.renamed)}** file.")
                if report.skipped:
                    with st.expander(f"Dilewati ({len(report.skipped)})"):
                        for path, reason in report.skipped:
                            st.write(f"- `{getattr(path, 'name', path)}` — {reason}")
                if report.errors:
                    with st.expander(f"Error ({len(report.errors)})"):
                        for path, err in report.errors:
                            st.write(f"- `{path.name}` — {err}")
                # Invalidasi cache supaya user pencet "Pindai" lagi
                st.session_state.pop("match_rows", None)

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### ℹ️  Info")
    st.markdown(
        "- Folder unduhan default: \n"
        f"  `{DEFAULT_DOWNLOAD_DIR}`\n"
        "- Folder playlist default: \n"
        f"  `{DEFAULT_PLAYLIST_DIR}`\n"
        "- Format spotdl: `{title}` "
        "(konsisten dengan target .m3u)"
    )
    st.markdown("---")
    st.caption("Spotify Local Music Manager • Streamlit")
