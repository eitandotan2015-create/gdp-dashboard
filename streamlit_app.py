import streamlit as st
import yt_dlp
import os
import json
import tempfile
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta

st.set_page_config(
    page_title="AI Video Downloader",
    page_icon="🎬",
    layout="wide",
)

# ── Styles ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        text-align: center;
    }
    .main-header h1 { color: #e94560; margin: 0; font-size: 2.5rem; }
    .main-header p  { color: #a8b2d8; margin: 0.5rem 0 0; font-size: 1.1rem; }
    .video-card {
        background: #1e1e2e;
        border: 1px solid #333;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .badge {
        display: inline-block;
        background: #0f3460;
        color: #e94560;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.8rem;
        margin: 2px;
    }
    .success-box {
        background: #0d2818;
        border: 1px solid #1a7a3c;
        border-radius: 8px;
        padding: 1rem;
        color: #4ade80;
    }
    .info-row { display: flex; gap: 1rem; flex-wrap: wrap; margin: 0.5rem 0; }
</style>
""", unsafe_allow_html=True)

# ── Header ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🎬 AI Video Downloader</h1>
    <p>Download videos from YouTube, Twitter/X, TikTok, Instagram, Vimeo, Reddit & 1000+ more sites</p>
</div>
""", unsafe_allow_html=True)

# ── Session state ───────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []
if "video_info" not in st.session_state:
    st.session_state.video_info = None
if "last_url" not in st.session_state:
    st.session_state.last_url = ""

DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "ai_video_downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# ── Helpers ─────────────────────────────────────────────────────────────────────
SUPPORTED_SITES = [
    "YouTube", "YouTube Shorts", "YouTube Playlist",
    "Twitter / X", "TikTok", "Instagram", "Facebook",
    "Vimeo", "Dailymotion", "Reddit", "Twitch",
    "SoundCloud", "Bandcamp", "Rumble", "Odysee",
    "BBC iPlayer", "Ted Talks", "Bilibili", "… and 1000+ more",
]

FORMAT_OPTIONS = {
    "Best Video + Audio (MP4)": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "Best Quality (any format)": "bestvideo+bestaudio/best",
    "1080p (MP4)": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]",
    "720p (MP4)": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]",
    "480p (MP4)": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]",
    "Audio Only (MP3)": "bestaudio/best",
    "Audio Only (M4A)": "bestaudio[ext=m4a]/bestaudio",
}

def format_duration(seconds):
    if not seconds:
        return "Unknown"
    return str(timedelta(seconds=int(seconds)))

def format_size(bytes_val):
    if not bytes_val:
        return "Unknown"
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} TB"

def get_video_info(url: str) -> dict | None:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "skip_download": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        return {"error": str(e)}

def download_video(url: str, fmt: str, output_path: Path, progress_callback=None) -> dict:
    result = {"success": False, "file": None, "error": None, "title": ""}

    class ProgressLogger:
        def debug(self, msg): pass
        def warning(self, msg): pass
        def error(self, msg): result["error"] = msg

    def progress_hook(d):
        if progress_callback and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            if total:
                progress_callback(downloaded / total)
        if d.get("status") == "finished":
            result["file"] = d.get("filename", "")
            if progress_callback:
                progress_callback(1.0)

    # Determine postprocessors
    postprocessors = []
    if "MP3" in fmt:
        postprocessors = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]

    ydl_opts = {
        "format": fmt,
        "outtmpl": str(output_path / "%(title)s.%(ext)s"),
        "logger": ProgressLogger(),
        "progress_hooks": [progress_hook],
        "merge_output_format": "mp4",
        "postprocessors": postprocessors,
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            result["title"] = info.get("title", "Unknown")
            result["success"] = True
    except Exception as e:
        result["error"] = str(e)

    # Find the actual downloaded file
    if result["success"] and not result["file"]:
        files = sorted(output_path.glob("*"), key=lambda f: f.stat().st_mtime, reverse=True)
        if files:
            result["file"] = str(files[0])

    return result

# ── Tabs ────────────────────────────────────────────────────────────────────────
tab_download, tab_playlist, tab_history, tab_about = st.tabs(
    ["⬇️ Download", "📋 Playlist / Batch", "📜 History", "ℹ️ Supported Sites"]
)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 – Single Download
# ═══════════════════════════════════════════════════════════════════════════════
with tab_download:
    col_left, col_right = st.columns([2, 1])

    with col_left:
        url = st.text_input(
            "Video URL",
            placeholder="Paste any video URL – YouTube, TikTok, Instagram, Twitter, Vimeo…",
            help="Supports 1000+ sites powered by yt-dlp",
        )

        col_fmt, col_btn = st.columns([3, 1])
        with col_fmt:
            selected_format_name = st.selectbox("Quality / Format", list(FORMAT_OPTIONS.keys()))
        with col_btn:
            st.write("")
            st.write("")
            fetch_info = st.button("🔍 Fetch Info", use_container_width=True)

    with col_right:
        st.markdown("**Quick Tips**")
        st.markdown("""
- Paste any URL and click **Fetch Info** to preview
- Choose quality then click **Download**
- Files are ready to save to your device
- Use **Playlist** tab for bulk downloads
        """)

    # ── Fetch info ──────────────────────────────────────────────────────────────
    if fetch_info and url:
        with st.spinner("Fetching video information…"):
            info = get_video_info(url)
            if info and "error" not in info:
                st.session_state.video_info = info
                st.session_state.last_url = url
            elif info:
                st.error(f"Could not fetch info: {info['error']}")
            else:
                st.error("Failed to retrieve video info. Check the URL.")

    # ── Display info card ───────────────────────────────────────────────────────
    info = st.session_state.video_info
    if info and st.session_state.last_url == url:
        st.markdown("---")
        c1, c2 = st.columns([1, 2])

        with c1:
            thumb = info.get("thumbnail")
            if thumb:
                st.image(thumb, use_container_width=True)

        with c2:
            title = info.get("title", "Unknown Title")
            uploader = info.get("uploader") or info.get("channel", "Unknown")
            duration = format_duration(info.get("duration"))
            view_count = info.get("view_count", 0)
            like_count = info.get("like_count", 0)
            upload_date = info.get("upload_date", "")
            if upload_date and len(upload_date) == 8:
                upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
            webpage_url = info.get("webpage_url", url)
            extractor = info.get("extractor_key", info.get("extractor", "")).replace("IE", "")

            st.markdown(f"### {title}")
            st.markdown(f"""
<div class="info-row">
  <span class="badge">📺 {extractor}</span>
  <span class="badge">⏱️ {duration}</span>
  <span class="badge">👤 {uploader}</span>
  {'<span class="badge">👁️ ' + f"{view_count:,}" + ' views</span>' if view_count else ''}
  {'<span class="badge">👍 ' + f"{like_count:,}" + '</span>' if like_count else ''}
  {'<span class="badge">📅 ' + upload_date + '</span>' if upload_date else ''}
</div>
""", unsafe_allow_html=True)

            desc = info.get("description", "")
            if desc:
                with st.expander("Description"):
                    st.text(desc[:1000] + ("…" if len(desc) > 1000 else ""))

            # Available formats
            formats = info.get("formats", [])
            if formats:
                best_formats = [
                    f for f in formats
                    if f.get("vcodec") != "none" and f.get("acodec") != "none"
                    and f.get("height")
                ]
                if best_formats:
                    heights = sorted(set(f["height"] for f in best_formats if f.get("height")), reverse=True)
                    st.markdown("**Available resolutions:** " + "  ".join(
                        f"`{h}p`" for h in heights[:8]
                    ))

        # ── Download button ─────────────────────────────────────────────────────
        st.markdown("---")
        dl_col1, dl_col2 = st.columns([3, 1])
        with dl_col2:
            start_download = st.button("⬇️ Download Now", type="primary", use_container_width=True)

        if start_download:
            fmt_str = FORMAT_OPTIONS[selected_format_name]
            progress_bar = st.progress(0, text="Starting download…")
            status_text = st.empty()

            def update_progress(p):
                pct = min(int(p * 100), 100)
                progress_bar.progress(pct, text=f"Downloading… {pct}%")

            with st.spinner(""):
                result = download_video(url, fmt_str, DOWNLOAD_DIR, update_progress)

            if result["success"] and result["file"]:
                progress_bar.progress(100, text="Complete!")
                file_path = Path(result["file"])
                if file_path.exists():
                    file_bytes = file_path.read_bytes()
                    st.markdown(f'<div class="success-box">✅ Downloaded: <b>{file_path.name}</b> ({format_size(len(file_bytes))})</div>', unsafe_allow_html=True)
                    st.download_button(
                        label=f"💾 Save to device – {file_path.name}",
                        data=file_bytes,
                        file_name=file_path.name,
                        mime="video/mp4" if file_path.suffix == ".mp4" else "application/octet-stream",
                        use_container_width=True,
                        type="primary",
                    )
                    # Save to history
                    st.session_state.history.append({
                        "title": result["title"] or title,
                        "url": url,
                        "format": selected_format_name,
                        "file": file_path.name,
                        "size": format_size(len(file_bytes)),
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    })
                else:
                    st.warning("File was downloaded but could not be located for saving.")
            else:
                progress_bar.empty()
                st.error(f"Download failed: {result.get('error', 'Unknown error')}")

    elif url and not info:
        st.info("Click **Fetch Info** to preview the video before downloading.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 – Playlist / Batch
# ═══════════════════════════════════════════════════════════════════════════════
with tab_playlist:
    st.subheader("📋 Playlist & Batch Downloader")
    st.markdown("Enter one URL per line. Supports YouTube playlists, channels, or any mix of URLs.")

    batch_urls_raw = st.text_area(
        "URLs (one per line)",
        height=160,
        placeholder="https://www.youtube.com/watch?v=...\nhttps://www.youtube.com/watch?v=...",
    )
    batch_fmt_name = st.selectbox("Quality / Format", list(FORMAT_OPTIONS.keys()), key="batch_fmt")
    max_items = st.slider("Max items from playlists", 1, 50, 10)

    if st.button("⬇️ Start Batch Download", type="primary"):
        urls = [u.strip() for u in batch_urls_raw.splitlines() if u.strip()]
        if not urls:
            st.warning("Please enter at least one URL.")
        else:
            st.markdown(f"**Downloading {len(urls)} URL(s)…**")
            fmt_str = FORMAT_OPTIONS[batch_fmt_name]
            results_container = st.container()
            overall = st.progress(0, text="Starting…")

            for idx, u in enumerate(urls, 1):
                overall.progress(int((idx - 1) / len(urls) * 100), text=f"Item {idx}/{len(urls)}")

                ydl_opts_batch = {
                    "format": fmt_str,
                    "outtmpl": str(DOWNLOAD_DIR / "%(playlist_index)s-%(title)s.%(ext)s"),
                    "merge_output_format": "mp4",
                    "quiet": True,
                    "no_warnings": True,
                    "playlistend": max_items,
                    "ignoreerrors": True,
                }
                if "MP3" in batch_fmt_name:
                    ydl_opts_batch["postprocessors"] = [
                        {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
                    ]

                try:
                    with yt_dlp.YoutubeDL(ydl_opts_batch) as ydl:
                        info = ydl.extract_info(u, download=True)
                        title_batch = info.get("title", u) if info else u
                    results_container.success(f"✅ {idx}. {title_batch}")
                    st.session_state.history.append({
                        "title": title_batch,
                        "url": u,
                        "format": batch_fmt_name,
                        "file": "batch",
                        "size": "—",
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    })
                except Exception as e:
                    results_container.error(f"❌ {idx}. {u} — {e}")

            overall.progress(100, text="All done!")

            # List downloaded files
            files = sorted(DOWNLOAD_DIR.glob("*"), key=lambda f: f.stat().st_mtime, reverse=True)
            recent = [f for f in files if (datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)).seconds < 600]
            if recent:
                st.markdown("### Downloaded files")
                for f in recent:
                    data = f.read_bytes()
                    st.download_button(
                        label=f"💾 {f.name} ({format_size(len(data))})",
                        data=data,
                        file_name=f.name,
                        mime="application/octet-stream",
                        key=f"dl_{f.name}_{idx}",
                    )

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 – History
# ═══════════════════════════════════════════════════════════════════════════════
with tab_history:
    st.subheader("📜 Download History")
    if not st.session_state.history:
        st.info("No downloads yet in this session. Start downloading to see history here.")
    else:
        if st.button("🗑️ Clear History"):
            st.session_state.history = []
            st.rerun()

        for i, item in enumerate(reversed(st.session_state.history)):
            with st.expander(f"🎬 {item['title']} — {item['time']}"):
                st.markdown(f"""
- **URL:** {item['url']}
- **Format:** {item['format']}
- **File:** `{item['file']}`
- **Size:** {item['size']}
- **Downloaded:** {item['time']}
""")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 – Supported Sites
# ═══════════════════════════════════════════════════════════════════════════════
with tab_about:
    st.subheader("ℹ️ Supported Sites & Features")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown("**Video Platforms**")
        for s in ["YouTube", "YouTube Shorts", "YouTube Playlists", "Vimeo", "Dailymotion",
                  "Rumble", "Odysee", "Bilibili", "Ted Talks", "BBC iPlayer"]:
            st.markdown(f"✅ {s}")
    with col_b:
        st.markdown("**Social Media**")
        for s in ["Twitter / X", "TikTok", "Instagram (Reels/Posts)", "Facebook",
                  "Reddit (videos)", "Twitch (clips/VODs)", "LinkedIn"]:
            st.markdown(f"✅ {s}")
    with col_c:
        st.markdown("**Audio & More**")
        for s in ["SoundCloud", "Bandcamp", "Spotify (via ytdl-sub)", "Mixcloud",
                  "Apple Podcasts", "… 1000+ extractors"]:
            st.markdown(f"✅ {s}")

    st.markdown("---")
    st.markdown("""
### Output Formats
| Format | Description |
|--------|-------------|
| MP4 (Best) | Highest quality video + audio merged into MP4 |
| 1080p / 720p / 480p | Specific resolution cap in MP4 |
| MP3 (Audio) | Extracts audio, converts to 192kbps MP3 |
| M4A (Audio) | Native AAC audio, smaller file size |

### Powered By
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** – the most powerful open-source video downloader
- **[Streamlit](https://streamlit.io)** – interactive Python web app framework
    """)

# ── Footer ──────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption("AI Video Downloader · Powered by yt-dlp & Streamlit · For personal/educational use only. Respect copyright laws.")
