"""German dictionary lookups, word audio, and card folder search."""

import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request


def _find_ffmpeg():
    """Find ffmpeg binary, checking PATH and common locations."""
    home = os.path.expanduser("~")
    extra_dirs = [
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
        os.path.join(home, ".local", "bin"),
    ]
    original_path = os.environ.get("PATH", "")
    extended_path = original_path + ":" + ":".join(extra_dirs)
    result = shutil.which("ffmpeg", path=extended_path)
    if result:
        return result
    for d in extra_dirs:
        candidate = os.path.join(d, "ffmpeg")
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return "ffmpeg"


# ── Dictionary lookups ─────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5,de;q=0.3",
}


def _http_get(url, headers=None, timeout=15):
    """Simple HTTP GET returning response body as string."""
    headers = headers or HEADERS
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def lookup_english(word):
    """Look up a German word and return an English translation string.

    Uses dict.cc (scraping the search results page).
    Returns a short translation or empty string on failure.
    """
    try:
        encoded = urllib.parse.quote(word, safe="")
        url = f"https://www.dict.cc/?s={encoded}"
        html = _http_get(url)

        # dict.cc puts translations in td elements with class "td7nl"
        # The pattern: German side (td7nl) → English side (td7nl) in pairs
        # Simpler: look for the first few translation pairs
        translations = []
        # Find pairs between <td class="td7nl"> tags
        pattern = r'<td class="td7nl"[^>]*>.*?<a[^>]*>([^<]+)</a>'
        matches = re.findall(pattern, html)
        # dict.cc alternates: odd = German, even = English (or vice versa)
        # Take up to 3 unique translations
        seen = set()
        for m in matches:
            m = m.strip()
            if m and m.lower() != word.lower() and m not in seen:
                seen.add(m)
                translations.append(m)
                if len(translations) >= 3:
                    break

        return "; ".join(translations) if translations else ""
    except Exception:
        return ""


def _lookup_german_dwds(word):
    """Try DWDS (Digitales Wörterbuch der deutschen Sprache)."""
    encoded = urllib.parse.quote(word, safe="")
    url = f"https://www.dwds.de/wb/{encoded}"
    html = _http_get(url)

    # Try multiple CSS class patterns DWDS uses
    patterns = [
        r'class="dwdswb-definition"[^>]*>(.*?)</div>',
        r'class="dwdswb-lesart-def"[^>]*>(.*?)</div>',
        r'class="dwdswb-bedeutung"[^>]*>(.*?)</div>',
    ]
    definitions = []
    for pattern in patterns:
        defs = re.findall(pattern, html, re.DOTALL)
        for d in defs:
            clean = re.sub(r"<[^>]+>", "", d).strip()
            if clean and len(clean) > 3 and clean not in definitions:
                definitions.append(clean)
                if len(definitions) >= 3:
                    return " | ".join(definitions)
    return " | ".join(definitions) if definitions else ""


def _lookup_german_wiktionary(word):
    """Try German Wiktionary as fallback."""
    encoded = urllib.parse.quote(word, safe="")
    url = f"https://de.wiktionary.org/wiki/{encoded}"
    html = _http_get(url)

    # Look for Bedeutungen (meanings) section
    meaning_match = re.search(
        r'Bedeutungen.*?</span>\s*</h\d>.*?<dl>(.*?)</dl>',
        html, re.DOTALL
    )
    if not meaning_match:
        return ""

    meanings_html = meaning_match.group(1)
    items = re.findall(r'<dd>(.*?)</dd>', meanings_html, re.DOTALL)
    definitions = []
    for item in items:
        clean = re.sub(r"<[^>]+>", "", item).strip()
        clean = re.sub(r"\[\d+\]\s*", "", clean).strip()
        if clean and len(clean) > 3 and clean not in definitions:
            definitions.append(clean)
            if len(definitions) >= 3:
                break

    return " | ".join(definitions) if definitions else ""


def lookup_german(word):
    """Look up a German word and return a German definition string.

    Tries DWDS first, then falls back to German Wiktionary.
    Returns a definition string or empty string on failure.
    """
    # Try DWDS first
    try:
        result = _lookup_german_dwds(word)
        if result:
            return result
    except Exception:
        pass

    # Fallback to German Wiktionary
    try:
        result = _lookup_german_wiktionary(word)
        if result:
            return result
    except Exception:
        pass

    return ""


# ── Word audio via macOS say command ───────────────────────────────────────

def generate_word_audio(word, output_path):
    """Generate audio for a German word using macOS 'say' command with Anna voice.

    Args:
        word: The German word/phrase to speak
        output_path: Path to save the .aiff file (will be converted to mp3)

    Returns:
        Path to the generated mp3 file, or None on failure.
    """
    try:
        # say outputs .aiff natively
        aiff_path = output_path.rsplit(".", 1)[0] + ".aiff"

        subprocess.run(
            ["say", "-v", "Anna", "-o", aiff_path, word],
            capture_output=True,
            check=True,
        )

        # Convert to mp3 with ffmpeg
        ffmpeg = _find_ffmpeg()
        mp3_path = output_path.rsplit(".", 1)[0] + ".mp3"
        subprocess.run(
            [ffmpeg, "-y", "-i", aiff_path, "-acodec", "libmp3lame", "-q:a", "2", mp3_path],
            capture_output=True,
            check=True,
        )

        # Clean up aiff
        if os.path.exists(aiff_path):
            os.remove(aiff_path)

        if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0:
            return mp3_path

    except Exception:
        pass

    return None


# ── Card folder search ─────────────────────────────────────────────────────

def scan_card_folders(base_dir):
    """Scan a directory for card folders and return list of card info dicts.

    Each dict: {"folder": path, "text": sentence, "has_audio": bool, "has_image": bool}
    """
    cards = []
    if not os.path.isdir(base_dir):
        return cards

    for name in sorted(os.listdir(base_dir)):
        card_dir = os.path.join(base_dir, name)
        if not os.path.isdir(card_dir) or not name.startswith("card_"):
            continue

        text_file = os.path.join(card_dir, "text.txt")
        if not os.path.isfile(text_file):
            continue

        with open(text_file, "r", encoding="utf-8") as f:
            text = f.read().strip()

        cards.append({
            "folder": card_dir,
            "name": name,
            "text": text,
            "has_audio": os.path.isfile(os.path.join(card_dir, "audio.mp3")),
            "has_image": os.path.isfile(os.path.join(card_dir, "frame.jpg")),
        })

    return cards


def search_cards(cards, query):
    """Filter cards whose text contains the query (case-insensitive)."""
    if not query.strip():
        return cards
    q = query.lower()
    return [c for c in cards if q in c["text"].lower()]


def get_source_url(base_dir):
    """Read the source YouTube URL from metadata.json."""
    meta_path = os.path.join(base_dir, "metadata.json")
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("url", "")
        except Exception:
            pass
    return ""
