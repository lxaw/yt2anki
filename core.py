"""Core logic for downloading YouTube videos and splitting into flashcards."""

import json
import os
import re
import subprocess
import tempfile


def run(cmd, **kwargs):
    """Run a subprocess command and return its output."""
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout.strip()


def get_video_info(url):
    """Fetch video metadata via yt-dlp."""
    out = run(["yt-dlp", "--dump-json", "--no-download", url])
    return json.loads(out)


def find_caption_lang(info, lang=None):
    """Find a suitable caption track. Returns (lang_code, is_automatic).

    Raises ValueError if no captions are found.
    """
    subs = info.get("subtitles") or {}
    auto_subs = info.get("automatic_captions") or {}

    if lang:
        if lang in subs:
            return lang, False
        if lang in auto_subs:
            return lang, True
        available = sorted(set(list(subs.keys()) + list(auto_subs.keys())))
        msg = f"No captions found for language '{lang}'."
        if available:
            msg += f" Available: {', '.join(available)}"
        raise ValueError(msg)

    # Auto-detect: prefer the video's native language
    native_lang = info.get("language")

    if subs:
        if native_lang and native_lang in subs:
            return native_lang, False
        return next(iter(subs)), False
    if auto_subs:
        if native_lang and native_lang in auto_subs:
            return native_lang, True
        # Fall back to original language (first key often is), skip 'en' preference
        return next(iter(auto_subs)), True

    raise ValueError("This video has no captions or automatic captions available.")


def get_available_languages(info):
    """Return sorted list of (lang_code, is_auto) tuples."""
    subs = info.get("subtitles") or {}
    auto_subs = info.get("automatic_captions") or {}
    langs = []
    for code in sorted(subs.keys()):
        langs.append((code, False))
    for code in sorted(auto_subs.keys()):
        if code not in subs:
            langs.append((code, True))
    return langs


def download_video_and_subs(url, tmpdir, lang, is_auto):
    """Download video and subtitle file. Returns (video_path, srt_path).

    Downloads video first, then attempts subtitles separately so a 429
    on subs doesn't block the whole download.
    """
    video_template = os.path.join(tmpdir, "video.%(ext)s")

    # Download video first (no subs)
    run([
        "yt-dlp",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--no-write-subs",
        "-o", video_template,
        url,
    ])

    # Now download subs separately — if 429, retry with native lang
    sub_flag = "--write-auto-subs" if is_auto else "--write-subs"
    try:
        run([
            "yt-dlp",
            "--skip-download",
            sub_flag,
            "--sub-langs", lang,
            "--convert-subs", "srt",
            "-o", video_template,
            url,
        ])
    except RuntimeError as e:
        if "429" in str(e) and is_auto:
            # Try the video's original language instead
            raise RuntimeError(
                f"YouTube rate-limited subtitle download for '{lang}'. "
                f"Try again later, or specify the video's native language with -l (e.g. -l de, -l ja)."
            )
        raise

    video_path = None
    srt_path = None
    for f in os.listdir(tmpdir):
        full = os.path.join(tmpdir, f)
        if f.startswith("video") and f.endswith(".mp4"):
            video_path = full
        if f.endswith(".srt"):
            srt_path = full

    if not video_path:
        raise RuntimeError("Failed to download video.")
    if not srt_path:
        raise RuntimeError("Failed to download subtitles.")

    return video_path, srt_path


def parse_srt(srt_path):
    """Parse an SRT file into a list of (start_secs, end_secs, text_lines) tuples."""
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = re.split(r"\n\s*\n", content.strip())
    entries = []

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 2:
            continue

        ts_line = None
        text_start = None
        for i, line in enumerate(lines):
            if "-->" in line:
                ts_line = line
                text_start = i + 1
                break

        if not ts_line or text_start is None:
            continue

        match = re.match(
            r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})",
            ts_line,
        )
        if not match:
            continue

        g = [int(x) for x in match.groups()]
        start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0
        end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0

        text_lines = []
        for line in lines[text_start:]:
            cleaned = re.sub(r"<[^>]+>", "", line).strip()
            if cleaned:
                text_lines.append(cleaned)

        if text_lines:
            entries.append((start, end, text_lines))

    return entries


def deduplicate_auto_captions(entries):
    """Clean up YouTube auto-caption duplicates.

    YouTube auto-captions follow a specific pattern:
      - Two-line entries (~3s): Line 1 is carried over from previous, Line 2 is NEW
      - Single-line entries (10ms): Transition markers, should be skipped

    Input entries have text as a list of lines (from parse_srt).
    Output entries have text as a single joined string.
    """
    if not entries:
        return entries

    cleaned = []
    for start, end, text_lines in entries:
        duration = end - start

        if duration < 0.05:
            continue

        if len(text_lines) >= 2:
            new_text = text_lines[-1]
        else:
            new_text = text_lines[0]

        if new_text.strip():
            cleaned.append((start, end, new_text.strip()))

    return cleaned


def merge_short_entries(entries, min_duration=1.0):
    """Merge very short consecutive entries that are likely split words."""
    if not entries:
        return entries

    merged = [entries[0]]
    for start, end, text in entries[1:]:
        prev_start, prev_end, prev_text = merged[-1]
        if start - prev_end < 0.1 and (prev_end - prev_start) < min_duration:
            merged[-1] = (prev_start, end, prev_text + " " + text)
        else:
            merged.append((start, end, text))
    return merged


def extract_cards(video_path, entries, output_dir, progress_callback=None):
    """Extract audio clip and screenshot for each caption entry.

    progress_callback(current, total, text) is called after each card if provided.
    """
    total = len(entries)
    pad = len(str(total))

    for i, (start, end, text) in enumerate(entries, 1):
        card_dir = os.path.join(output_dir, f"card_{i:0{pad}d}")
        os.makedirs(card_dir, exist_ok=True)

        duration = end - start
        fast_seek = max(0, start - 10)
        precise_offset = start - fast_seek

        # Audio clip
        audio_path = os.path.join(card_dir, "audio.mp3")
        subprocess.run([
            "ffmpeg", "-y",
            "-ss", f"{fast_seek:.3f}",
            "-i", video_path,
            "-ss", f"{precise_offset:.3f}",
            "-t", f"{duration:.3f}",
            "-vn", "-acodec", "libmp3lame", "-q:a", "2",
            audio_path,
        ], capture_output=True)

        # Screenshot
        image_path = os.path.join(card_dir, "frame.jpg")
        subprocess.run([
            "ffmpeg", "-y",
            "-ss", f"{fast_seek:.3f}",
            "-i", video_path,
            "-ss", f"{precise_offset:.3f}",
            "-frames:v", "1",
            "-q:v", "2",
            image_path,
        ], capture_output=True)

        # Text file
        text_path = os.path.join(card_dir, "text.txt")
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(text + "\n")

        if progress_callback:
            progress_callback(i, total, text)


def process_video(url, output_dir, lang=None, progress_callback=None):
    """Full pipeline: download, parse captions, extract cards.

    progress_callback(current, total, message) is called at each stage.
    Returns (title, num_cards).
    """
    def update(current, total, msg):
        if progress_callback:
            progress_callback(current, total, msg)

    update(0, 0, "Fetching video info...")
    info = get_video_info(url)
    title = info.get("title", "Unknown")

    update(0, 0, f"Title: {title}")

    lang_code, is_auto = find_caption_lang(info, lang)
    caption_type = "automatic" if is_auto else "manual"
    update(0, 0, f"Using {caption_type} captions in '{lang_code}'")

    with tempfile.TemporaryDirectory() as tmpdir:
        update(0, 0, "Downloading video and subtitles...")
        video_path, srt_path = download_video_and_subs(url, tmpdir, lang_code, is_auto)

        update(0, 0, "Parsing captions...")
        entries = parse_srt(srt_path)
        entries = deduplicate_auto_captions(entries)
        entries = merge_short_entries(entries)

        if not entries:
            raise RuntimeError("No caption entries found after parsing.")

        update(0, len(entries), f"Found {len(entries)} caption segments")

        os.makedirs(output_dir, exist_ok=True)

        meta_path = os.path.join(output_dir, "metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "title": title,
                "url": url,
                "language": lang_code,
                "caption_type": caption_type,
                "total_cards": len(entries),
            }, f, indent=2)

        extract_cards(video_path, entries, output_dir, progress_callback=progress_callback)

    return title, len(entries)
