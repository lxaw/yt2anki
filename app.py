#!/usr/bin/env python3
"""YouTube to Flashcard — Native macOS app via pywebview."""

import os
import subprocess
import sys
import tempfile
import threading

import webview

from core import process_video, _find_bin


def _check_dependencies():
    """Check that required external tools are available. Show alert if not."""
    missing = []
    for name in ("yt-dlp", "ffmpeg"):
        path = _find_bin(name)
        # _find_bin returns bare name if not found — check if it's actually executable
        if path == name or not os.path.isfile(path):
            missing.append(name)
    if missing:
        msg = (
            f"Missing required tools: {', '.join(missing)}\n\n"
            "Install them with Homebrew:\n"
            f"  brew install {' '.join(missing)}\n\n"
            "Then relaunch the app."
        )
        # Try native macOS dialog
        try:
            subprocess.run([
                "osascript", "-e",
                f'display dialog "{msg}" with title "YouTube to Flashcard" buttons {{"OK"}} default button "OK" with icon stop'
            ], check=False)
        except Exception:
            print(msg, file=sys.stderr)
        sys.exit(1)


_check_dependencies()
from anki_connect import (
    get_deck_names,
    create_deck,
    ensure_german_model,
    ensure_japanese_model,
    add_note,
)
from german_helpers import (
    scan_card_folders,
    search_cards,
    get_source_url,
    lookup_english as de_lookup_english,
    lookup_german,
    generate_word_audio as de_generate_word_audio,
)
from japanese_helpers import (
    lookup_english as ja_lookup_english,
    lookup_japanese,
    generate_word_audio as ja_generate_word_audio,
)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=VT323&display=swap');

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'VT323', 'Courier New', monospace;
    font-size: 16px;
    background: #c0c0c0;
    color: #000;
    padding: 0;
    overflow-x: hidden;
  }

  /* Win95 title bar */
  .titlebar {
    background: linear-gradient(90deg, #000080, #1084d0);
    color: #fff;
    font-size: 16px;
    font-weight: bold;
    padding: 4px 8px;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .titlebar-icon {
    width: 16px; height: 16px;
    background: #ff0000;
    border: 1px solid #fff;
  }

  /* Win95 window body */
  .window {
    border: 2px solid;
    border-color: #dfdfdf #808080 #808080 #dfdfdf;
  }
  .window-inner {
    border: 2px solid;
    border-color: #fff #404040 #404040 #fff;
    padding: 10px;
  }

  /* Tabs */
  .tabs {
    display: flex;
    gap: 0;
    margin-bottom: -2px;
    position: relative;
    z-index: 1;
  }
  .tab {
    font-family: 'VT323', 'Courier New', monospace;
    font-size: 15px;
    padding: 4px 16px;
    background: #c0c0c0;
    border: 2px solid;
    border-color: #fff #404040 #404040 #fff;
    border-bottom: none;
    cursor: pointer;
    outline: none;
    position: relative;
  }
  .tab.active {
    background: #c0c0c0;
    border-bottom: 2px solid #c0c0c0;
    font-weight: bold;
    z-index: 2;
  }
  .tab:not(.active) {
    background: #a0a0a0;
    top: 2px;
  }
  .tab-content {
    display: none;
    border: 2px solid;
    border-color: #fff #404040 #404040 #fff;
    padding: 10px;
    background: #c0c0c0;
  }
  .tab-content.active { display: block; }

  /* Inset field */
  .field {
    border: 2px solid;
    border-color: #808080 #fff #fff #808080;
    background: #fff;
    padding: 4px 6px;
    font-family: 'VT323', 'Courier New', monospace;
    font-size: 16px;
    color: #000;
    width: 100%;
    outline: none;
  }
  .field:focus { outline: 1px dotted #000; }

  .lbl { font-size: 15px; margin-bottom: 3px; margin-top: 8px; color: #000; }

  /* Groupbox */
  .groupbox {
    border: 2px solid;
    border-color: #808080 #fff #fff #808080;
    padding: 10px;
    margin-top: 10px;
    position: relative;
  }
  .groupbox-title {
    position: absolute;
    top: -10px; left: 10px;
    background: #c0c0c0;
    padding: 0 4px;
    font-size: 15px;
  }

  .row { display: flex; gap: 8px; align-items: flex-end; }
  .row .grow { flex: 1; }

  /* Win95 button */
  button, select {
    font-family: 'VT323', 'Courier New', monospace;
    font-size: 16px;
    padding: 4px 16px;
    background: #c0c0c0;
    color: #000;
    border: 2px solid;
    border-color: #fff #404040 #404040 #fff;
    cursor: pointer;
    outline: none;
  }
  button:active {
    border-color: #404040 #fff #fff #404040;
    padding: 5px 15px 3px 17px;
  }
  button:disabled {
    color: #808080;
    text-shadow: 1px 1px #fff;
    cursor: default;
  }

  select { padding: 3px 6px; }

  .buttons { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }

  /* Progress bar */
  .progress-wrap {
    margin-top: 8px;
    border: 2px solid;
    border-color: #808080 #fff #fff #808080;
    height: 22px;
    background: #fff;
    position: relative;
    overflow: hidden;
  }
  .progress-bar {
    height: 100%; width: 0%;
    background: repeating-linear-gradient(90deg, #000080 0px, #000080 10px, transparent 10px, transparent 12px);
    transition: width 0.3s;
  }
  .progress-text {
    position: absolute; top: 0; left: 0; right: 0; bottom: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px; color: #000;
    mix-blend-mode: difference;
  }

  /* Log area */
  .log {
    margin-top: 8px;
    border: 2px solid;
    border-color: #808080 #fff #fff #808080;
    background: #fff;
    padding: 6px;
    font-family: 'VT323', 'Courier New', monospace;
    font-size: 14px;
    line-height: 1.4;
    height: 120px;
    overflow-y: auto;
    color: #000;
    white-space: pre-wrap;
  }
  .log::-webkit-scrollbar { width: 16px; }
  .log::-webkit-scrollbar-track { background: #c0c0c0; border: 1px solid #808080; }
  .log::-webkit-scrollbar-thumb {
    background: #c0c0c0;
    border: 2px solid;
    border-color: #fff #404040 #404040 #fff;
  }

  .status {
    margin-top: 6px;
    font-size: 14px;
    border: 2px solid;
    border-color: #808080 #fff #fff #808080;
    padding: 3px 6px;
    background: #c0c0c0;
    min-height: 20px;
  }
  .status.error { color: #ff0000; }
  .status.done { color: #008000; }

  /* Card list for Anki tab */
  .card-list {
    border: 2px solid;
    border-color: #808080 #fff #fff #808080;
    background: #fff;
    height: 200px;
    overflow-y: auto;
    margin-top: 8px;
  }
  .card-list::-webkit-scrollbar { width: 16px; }
  .card-list::-webkit-scrollbar-track { background: #c0c0c0; border: 1px solid #808080; }
  .card-list::-webkit-scrollbar-thumb {
    background: #c0c0c0;
    border: 2px solid;
    border-color: #fff #404040 #404040 #fff;
  }
  .card-item {
    padding: 4px 8px;
    font-size: 14px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    border-bottom: 1px solid #e0e0e0;
  }
  .card-item:hover { background: #d0d0ff; }
  .card-item input[type="checkbox"] { margin: 0; }
  .card-item .card-name { color: #808080; min-width: 70px; }
  .card-item .card-text { flex: 1; }

  .select-bar { display: flex; gap: 8px; margin-top: 6px; align-items: center; font-size: 14px; }
</style>
</head>
<body>

<div class="window">
  <div class="titlebar">
    <div class="titlebar-icon"></div>
    YouTube to Flashcard
  </div>
  <div class="window-inner">

    <!-- Tabs -->
    <div class="tabs">
      <div class="tab active" onclick="switchTab('generate')">Generate Cards</div>
      <div class="tab" onclick="switchTab('anki')">Anki Upload</div>
    </div>

    <!-- TAB 1: Generate -->
    <div class="tab-content active" id="tab-generate">
      <div class="lbl">URL:</div>
      <input class="field" type="text" id="url" placeholder="https://www.youtube.com/watch?v=...">

      <div class="groupbox" style="margin-top:10px">
        <div class="groupbox-title">Options</div>
        <div class="row" style="margin-top:4px">
          <div>
            <div class="lbl">Language:</div>
            <input class="field" type="text" id="lang" placeholder="auto" style="width:100px">
          </div>
          <div class="grow">
            <div class="lbl">Output Folder:</div>
            <input class="field" type="text" id="output" value="output">
          </div>
        </div>
        <div class="row" style="margin-top:8px">
          <div class="grow">
            <div class="lbl">Cookies File: <span style="font-weight:normal;color:#666">(optional — needed if YouTube blocks the download)</span></div>
            <input class="field" type="text" id="cookies" placeholder="path to cookies.txt (leave empty to try without)">
          </div>
          <div>
            <div class="lbl">&nbsp;</div>
            <button onclick="browseCookies()">Browse...</button>
          </div>
        </div>
      </div>

      <div class="buttons">
        <button id="startBtn" onclick="startJob()">Start</button>
        <button id="cancelBtn" onclick="cancelJob()" disabled>Cancel</button>
        <button id="openBtn" onclick="openFolder()" disabled>Open Folder</button>
      </div>

      <div class="progress-wrap">
        <div class="progress-bar" id="progressBar"></div>
        <div class="progress-text" id="progressText"></div>
      </div>

      <div class="log" id="log">Ready.</div>
      <div class="status" id="status">Ready</div>
    </div>

    <!-- TAB 2: Anki Upload -->
    <div class="tab-content" id="tab-anki">

      <div class="groupbox">
        <div class="groupbox-title">Card Source</div>
        <div class="row" style="margin-top:4px">
          <div class="grow">
            <div class="lbl">Folder Path:</div>
            <input class="field" type="text" id="anki-folder" value="output" placeholder="path to card output folder">
          </div>
          <div>
            <div class="lbl">&nbsp;</div>
            <button onclick="ankiLoadFolder()">Load</button>
          </div>
        </div>
      </div>

      <div class="groupbox" style="margin-top:10px">
        <div class="groupbox-title">Search &amp; Select</div>
        <div class="row" style="margin-top:4px">
          <div class="grow">
            <div class="lbl">Target Phrase:</div>
            <input class="field" type="text" id="anki-search" placeholder="type a word or phrase to search..." oninput="ankiSearch()">
          </div>
        </div>

        <div class="card-list" id="anki-card-list">
          <div style="padding:8px;color:#808080;">Load a folder to see cards.</div>
        </div>
        <div class="select-bar">
          <span id="anki-count">0 cards</span>
          <button onclick="ankiSelectAll()">Select All</button>
          <button onclick="ankiSelectNone()">Select None</button>
        </div>
      </div>

      <div class="groupbox" style="margin-top:10px">
        <div class="groupbox-title">Language</div>
        <div class="row" style="margin-top:4px">
          <div>
            <div class="lbl">Card Language:</div>
            <select class="field" id="anki-lang" style="padding:3px 6px;">
              <option value="de">German (de)</option>
              <option value="ja">Japanese (ja)</option>
            </select>
          </div>
        </div>
      </div>

      <div class="groupbox" style="margin-top:10px">
        <div class="groupbox-title">Anki Deck</div>
        <div class="row" style="margin-top:4px">
          <div class="grow">
            <div class="lbl">Deck:</div>
            <select class="field" id="anki-deck" style="padding:3px 6px;">
              <option value="">-- click Refresh --</option>
            </select>
          </div>
          <div>
            <div class="lbl">&nbsp;</div>
            <button onclick="ankiRefreshDecks()">Refresh</button>
          </div>
          <div>
            <div class="lbl">&nbsp;</div>
            <button onclick="ankiNewDeck()">New Deck</button>
          </div>
        </div>
      </div>

      <div class="buttons">
        <button id="anki-upload-btn" onclick="ankiUpload()">Upload to Anki</button>
      </div>

      <div class="log" id="anki-log">Ready. Make sure Anki is open with AnkiConnect installed.</div>
      <div class="status" id="anki-status">Ready</div>
    </div>

  </div>
</div>

<script>
// ─── Tab switching ───
function switchTab(name) {
  document.querySelectorAll('.tab').forEach((t, i) => {
    t.classList.toggle('active', (name === 'generate' && i === 0) || (name === 'anki' && i === 1));
  });
  document.getElementById('tab-generate').classList.toggle('active', name === 'generate');
  document.getElementById('tab-anki').classList.toggle('active', name === 'anki');
}

// ─── TAB 1: Generate Cards ───
function startJob() {
  const url = document.getElementById('url').value.trim();
  if (!url) { alert('Please enter a YouTube URL.'); return; }
  document.getElementById('startBtn').disabled = true;
  document.getElementById('cancelBtn').disabled = false;
  document.getElementById('openBtn').disabled = true;
  document.getElementById('log').textContent = 'Starting...\\n';
  document.getElementById('status').textContent = 'Working...';
  document.getElementById('status').className = 'status';
  document.getElementById('progressBar').style.width = '0%';
  document.getElementById('progressText').textContent = '';
  const lang = document.getElementById('lang').value.trim();
  const output = document.getElementById('output').value.trim() || 'output';
  const cookies = document.getElementById('cookies').value.trim();
  pywebview.api.start_job(url, lang, output, cookies);
  pollStatus();
}

function cancelJob() {
  pywebview.api.cancel_job();
  document.getElementById('cancelBtn').disabled = true;
  document.getElementById('status').textContent = 'Cancelling...';
}

function openFolder() { pywebview.api.open_output(); }

function browseCookies() {
  pywebview.api.browse_file('cookies.txt').then(path => {
    if (path) document.getElementById('cookies').value = path;
  });
}

function pollStatus() {
  pywebview.api.get_status().then(data => {
    const log = document.getElementById('log');
    log.textContent = data.messages.join('\\n');
    log.scrollTop = log.scrollHeight;
    if (data.total > 0) {
      const pct = Math.round((data.progress / data.total) * 100);
      document.getElementById('progressBar').style.width = pct + '%';
      document.getElementById('progressText').textContent = pct + '%';
    }
    if (data.done || data.error || !data.running) {
      document.getElementById('startBtn').disabled = false;
      document.getElementById('cancelBtn').disabled = true;
      if (data.error) {
        document.getElementById('status').textContent = 'Error: ' + data.error;
        document.getElementById('status').className = 'status error';
      } else if (data.done) {
        document.getElementById('progressBar').style.width = '100%';
        document.getElementById('progressText').textContent = '100%';
        document.getElementById('status').textContent = 'Done! Cards saved.';
        document.getElementById('status').className = 'status done';
        document.getElementById('openBtn').disabled = false;
      } else if (!data.running) {
        document.getElementById('status').textContent = 'Cancelled.';
        document.getElementById('status').className = 'status';
      }
      return;
    }
    setTimeout(pollStatus, 400);
  });
}

// ─── TAB 2: Anki Upload ───
let allCards = [];
let filteredCards = [];

function ankiLog(msg) {
  const log = document.getElementById('anki-log');
  log.textContent += msg + '\\n';
  log.scrollTop = log.scrollHeight;
}

function ankiLoadFolder() {
  const folder = document.getElementById('anki-folder').value.trim();
  if (!folder) { alert('Enter a folder path.'); return; }
  document.getElementById('anki-log').textContent = 'Loading cards...\\n';
  pywebview.api.anki_load_folder(folder).then(data => {
    allCards = data.cards || [];
    ankiLog('Loaded ' + allCards.length + ' cards from: ' + folder);
    if (data.source_url) ankiLog('Source: ' + data.source_url);
    filteredCards = allCards;
    renderCardList();
  });
}

function ankiSearch() {
  const q = document.getElementById('anki-search').value.trim();
  if (!q) { filteredCards = allCards; }
  else { filteredCards = allCards.filter(c => c.text.toLowerCase().includes(q.toLowerCase())); }
  renderCardList();
}

function renderCardList() {
  const list = document.getElementById('anki-card-list');
  if (filteredCards.length === 0) {
    list.innerHTML = '<div style="padding:8px;color:#808080;">No matching cards.</div>';
    document.getElementById('anki-count').textContent = '0 cards';
    return;
  }
  list.innerHTML = filteredCards.map((c, i) =>
    '<label class="card-item">' +
    '<input type="checkbox" data-idx="' + i + '" checked> ' +
    '<span class="card-name">' + c.name + '</span> ' +
    '<span class="card-text">' + c.text.substring(0, 80) + (c.text.length > 80 ? '...' : '') + '</span>' +
    '</label>'
  ).join('');
  updateCount();
}

function updateCount() {
  const checked = document.querySelectorAll('#anki-card-list input[type=checkbox]:checked').length;
  document.getElementById('anki-count').textContent = checked + ' / ' + filteredCards.length + ' selected';
}

// Delegate change events
document.addEventListener('change', e => {
  if (e.target.matches('#anki-card-list input[type=checkbox]')) updateCount();
});

function ankiSelectAll() {
  document.querySelectorAll('#anki-card-list input[type=checkbox]').forEach(cb => cb.checked = true);
  updateCount();
}
function ankiSelectNone() {
  document.querySelectorAll('#anki-card-list input[type=checkbox]').forEach(cb => cb.checked = false);
  updateCount();
}

function ankiRefreshDecks() {
  pywebview.api.anki_get_decks().then(decks => {
    const sel = document.getElementById('anki-deck');
    sel.innerHTML = '';
    if (!decks || decks.length === 0) {
      sel.innerHTML = '<option value="">No decks (is Anki open?)</option>';
      return;
    }
    decks.forEach(d => {
      const opt = document.createElement('option');
      opt.value = d; opt.textContent = d;
      sel.appendChild(opt);
    });
    ankiLog('Loaded ' + decks.length + ' decks from Anki.');
  }).catch(err => {
    ankiLog('Error: ' + err + ' — Is Anki open with AnkiConnect?');
  });
}

function ankiNewDeck() {
  const name = prompt('New deck name:');
  if (!name || !name.trim()) return;
  pywebview.api.anki_create_deck(name.trim()).then(result => {
    ankiLog('Created deck: ' + name.trim());
    ankiRefreshDecks();
  }).catch(err => {
    ankiLog('Error creating deck: ' + err);
  });
}

function ankiUpload() {
  const deck = document.getElementById('anki-deck').value;
  if (!deck) { alert('Select a deck first.'); return; }

  const targetPhrase = document.getElementById('anki-search').value.trim();

  // Gather selected card indices
  const checkboxes = document.querySelectorAll('#anki-card-list input[type=checkbox]:checked');
  if (checkboxes.length === 0) { alert('Select at least one card.'); return; }

  const selectedIndices = [];
  checkboxes.forEach(cb => selectedIndices.push(parseInt(cb.dataset.idx)));
  const selectedCards = selectedIndices.map(i => filteredCards[i]);

  document.getElementById('anki-upload-btn').disabled = true;
  document.getElementById('anki-status').textContent = 'Uploading...';
  document.getElementById('anki-status').className = 'status';
  document.getElementById('anki-log').textContent = 'Starting upload...\\n';

  const folder = document.getElementById('anki-folder').value.trim();
  const lang = document.getElementById('anki-lang').value;
  pywebview.api.anki_upload(deck, targetPhrase, selectedCards, folder, lang);
  pollAnkiStatus();
}

function pollAnkiStatus() {
  pywebview.api.anki_get_upload_status().then(data => {
    const log = document.getElementById('anki-log');
    log.textContent = data.messages.join('\\n');
    log.scrollTop = log.scrollHeight;

    if (data.done || data.error) {
      document.getElementById('anki-upload-btn').disabled = false;
      if (data.error) {
        document.getElementById('anki-status').textContent = 'Error: ' + data.error;
        document.getElementById('anki-status').className = 'status error';
      } else {
        document.getElementById('anki-status').textContent = 'Done! Cards uploaded to Anki.';
        document.getElementById('anki-status').className = 'status done';
      }
      return;
    }
    setTimeout(pollAnkiStatus, 500);
  });
}
</script>
</body>
</html>
"""


class Api:
    def __init__(self):
        # Generate tab state
        self._cancelled = False
        self._output_dir = ""
        self._status = {
            "running": False, "progress": 0, "total": 0,
            "messages": [], "done": False, "error": None,
        }
        # Anki tab state
        self._anki_upload_status = {
            "messages": [], "done": False, "error": None,
        }

    # ── Generate tab ──────────────────────────────────────────────

    def start_job(self, url, lang, output, cookies=""):
        if self._status["running"]:
            return
        self._output_dir = os.path.abspath(output)
        self._cancelled = False
        self._status = {
            "running": True, "progress": 0, "total": 0,
            "messages": [], "done": False, "error": None,
        }
        lang = lang if lang else None
        cookies_path = cookies.strip() if cookies else None

        def worker():
            try:
                def cb(current, total, msg):
                    if self._cancelled:
                        self._kill_children()
                        raise InterruptedError("Cancelled.")
                    self._status["progress"] = current
                    self._status["total"] = total
                    self._status["messages"].append(
                        f"[{current}/{total}] {msg[:80]}" if total > 0 else msg
                    )
                    if len(self._status["messages"]) > 500:
                        self._status["messages"] = self._status["messages"][-300:]

                _, num = process_video(url, self._output_dir, lang=lang, progress_callback=cb, cookies_path=cookies_path)
                self._status["messages"].append(f"\nDone! {num} cards saved.")
                self._status["done"] = True
            except InterruptedError:
                self._status["messages"].append("Cancelled.")
            except Exception as e:
                if self._cancelled:
                    self._status["messages"].append("Cancelled.")
                else:
                    self._status["error"] = str(e)
                    self._status["messages"].append(f"\nError: {e}")
            finally:
                self._status["running"] = False

        threading.Thread(target=worker, daemon=True).start()

    def cancel_job(self):
        self._cancelled = True
        self._kill_children()

    def _kill_children(self):
        try:
            import psutil
            current = psutil.Process(os.getpid())
            for child in current.children(recursive=True):
                child.kill()
        except ImportError:
            os.system("pkill -P %d ffmpeg 2>/dev/null" % os.getpid())
            os.system("pkill -P %d yt-dlp 2>/dev/null" % os.getpid())

    def get_status(self):
        return self._status

    def browse_file(self, filename_hint=""):
        result = webview.windows[0].create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=("Text files (*.txt)", "All files (*.*)"),
        )
        if result:
            return result[0]
        return None

    def open_output(self):
        if os.path.isdir(self._output_dir):
            subprocess.Popen(["open", self._output_dir])

    # ── Anki tab ──────────────────────────────────────────────────

    def anki_load_folder(self, folder):
        folder = os.path.abspath(folder)
        cards = scan_card_folders(folder)
        source_url = get_source_url(folder)
        return {
            "cards": [{"name": c["name"], "text": c["text"], "folder": c["folder"],
                        "has_audio": c["has_audio"], "has_image": c["has_image"]} for c in cards],
            "source_url": source_url,
        }

    def anki_get_decks(self):
        return get_deck_names()

    def anki_create_deck(self, name):
        return create_deck(name)

    def anki_upload(self, deck_name, target_phrase, selected_cards, base_folder, lang="de"):
        self._anki_upload_status = {"messages": [], "done": False, "error": None}

        def log(msg):
            self._anki_upload_status["messages"].append(msg)

        def worker():
            try:
                base_folder_abs = os.path.abspath(base_folder)
                source_url = get_source_url(base_folder_abs)

                # Select language-specific helpers
                is_ja = lang == "ja"
                if is_ja:
                    model_name = ensure_japanese_model()
                    native_field = "Dictionary Entry (Japanese)"
                    fn_lookup_en = ja_lookup_english
                    fn_lookup_native = lookup_japanese
                    fn_word_audio = ja_generate_word_audio
                else:
                    model_name = ensure_german_model()
                    native_field = "Dictionary Entry (German)"
                    fn_lookup_en = de_lookup_english
                    fn_lookup_native = lookup_german
                    fn_word_audio = de_generate_word_audio

                log(f"Using model: {model_name}")

                has_target = bool(target_phrase)
                en_def = ""
                native_def = ""
                word_audio_path = None

                if has_target:
                    log(f"Looking up '{target_phrase}' in dictionaries...")
                    en_def = fn_lookup_en(target_phrase)
                    log(f"  EN: {en_def[:80] if en_def else '(not found)'}")
                    native_def = fn_lookup_native(target_phrase)
                    log(f"  Native: {native_def[:80] if native_def else '(not found)'}")
                    log(f"Generating word audio for '{target_phrase}'...")

                with tempfile.TemporaryDirectory() as tmpdir:
                    if has_target:
                        word_audio_path = fn_word_audio(
                            target_phrase,
                            os.path.join(tmpdir, "word.mp3"),
                        )
                        if word_audio_path:
                            log("  Word audio generated.")
                        else:
                            log("  Warning: word audio generation failed, continuing without it.")

                    total = len(selected_cards)
                    for i, card in enumerate(selected_cards, 1):
                        card_folder = card["folder"]
                        sentence = card["text"]
                        effective_target = target_phrase if has_target else sentence

                        log(f"[{i}/{total}] Uploading: {sentence[:60]}...")

                        fields = {
                            "Sentence": sentence,
                            "Image": "",
                            "Target Phrase": effective_target,
                            "Sentence Audio": "",
                            "Word Audio": "",
                            "Dictionary Entry (English)": en_def,
                            native_field: native_def,
                            "Source": source_url,
                        }

                        audio_files = []
                        picture_files = []

                        audio_path = os.path.join(card_folder, "audio.mp3")
                        if os.path.isfile(audio_path):
                            audio_files.append({
                                "path": audio_path,
                                "filename": f"ytf_sentence_{card['name']}.mp3",
                                "fields": ["Sentence Audio"],
                            })

                        if has_target and word_audio_path and os.path.isfile(word_audio_path):
                            safe_phrase = target_phrase.replace(" ", "_")[:30]
                            audio_files.append({
                                "path": word_audio_path,
                                "filename": f"ytf_word_{safe_phrase}.mp3",
                                "fields": ["Word Audio"],
                            })

                        img_path = os.path.join(card_folder, "frame.jpg")
                        if os.path.isfile(img_path):
                            picture_files.append({
                                "path": img_path,
                                "filename": f"ytf_frame_{card['name']}.jpg",
                                "fields": ["Image"],
                            })

                        add_note(deck_name, model_name, fields, audio_files, picture_files)
                        log(f"  Added to deck '{deck_name}'")

                log(f"\nDone! {total} cards uploaded to Anki.")
                self._anki_upload_status["done"] = True

            except Exception as e:
                self._anki_upload_status["error"] = str(e)
                log(f"\nError: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def anki_get_upload_status(self):
        return self._anki_upload_status


if __name__ == "__main__":
    api = Api()
    window = webview.create_window(
        "YouTube to Flashcard",
        html=HTML,
        js_api=api,
        width=600,
        height=650,
        min_size=(500, 500),
    )
    webview.start()
