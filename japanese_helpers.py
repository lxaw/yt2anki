"""Japanese dictionary lookups and word audio."""

import os
import re
import shutil
import subprocess
import urllib.parse
import urllib.request


def _find_ffmpeg():
    home = os.path.expanduser("~")
    extra_dirs = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", os.path.join(home, ".local", "bin")]
    extended_path = os.environ.get("PATH", "") + ":" + ":".join(extra_dirs)
    result = shutil.which("ffmpeg", path=extended_path)
    if result:
        return result
    for d in extra_dirs:
        candidate = os.path.join(d, "ffmpeg")
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return "ffmpeg"


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.5",
}


def _http_get(url, timeout=15):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def lookup_english(word):
    """Look up a Japanese word on Jisho, return English definitions."""
    try:
        encoded = urllib.parse.quote(word, safe="")
        html = _http_get(f"https://jisho.org/search/{encoded}")
        meanings = re.findall(r'class="meaning-meaning"[^>]*>(.*?)</span>', html, re.DOTALL)
        defs = []
        for m in meanings:
            clean = re.sub(r"<[^>]+>", "", m).strip()
            if clean and clean not in defs:
                defs.append(clean)
                if len(defs) >= 4:
                    break
        return "; ".join(defs)
    except Exception:
        return ""


def lookup_japanese(word):
    """Look up a Japanese word on Kotobank, return Japanese definition."""
    try:
        encoded = urllib.parse.quote(word, safe="")
        html = _http_get(f"https://kotobank.jp/word/{encoded}")
        # Kotobank wraps definitions in <p class="description">
        defs = re.findall(r'class="description"[^>]*>(.*?)</p>', html, re.DOTALL)
        results = []
        for d in defs:
            clean = re.sub(r"<[^>]+>", "", d).strip()
            clean = re.sub(r"\s+", " ", clean)
            if clean and len(clean) > 3 and clean not in results:
                results.append(clean)
                if len(results) >= 2:
                    break
        return " | ".join(results)
    except Exception:
        return ""


def generate_word_audio(word, output_path):
    """Generate audio for a Japanese word using macOS 'say' with Kyoko voice."""
    try:
        aiff_path = output_path.rsplit(".", 1)[0] + ".aiff"
        subprocess.run(
            ["say", "-v", "Kyoko", "-o", aiff_path, word],
            capture_output=True, check=True,
        )
        ffmpeg = _find_ffmpeg()
        mp3_path = output_path.rsplit(".", 1)[0] + ".mp3"
        subprocess.run(
            [ffmpeg, "-y", "-i", aiff_path, "-acodec", "libmp3lame", "-q:a", "2", mp3_path],
            capture_output=True, check=True,
        )
        if os.path.exists(aiff_path):
            os.remove(aiff_path)
        if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0:
            return mp3_path
    except Exception:
        pass
    return None
