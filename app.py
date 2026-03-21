#!/usr/bin/env python3
"""YouTube to Flashcard — Native macOS app via pywebview."""

import os
import subprocess
import threading

import webview

from core import process_video

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
    letter-spacing: 0.5px;
  }
  .titlebar-icon {
    width: 16px; height: 16px;
    background: #ff0000;
    border: 1px solid #fff;
    display: inline-block;
  }

  /* Win95 window body */
  .window {
    border: 2px solid;
    border-color: #dfdfdf #808080 #808080 #dfdfdf;
    margin: 0;
  }
  .window-inner {
    border: 2px solid;
    border-color: #fff #404040 #404040 #fff;
    padding: 12px;
  }

  /* Inset field (sunken) */
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
  .field:focus {
    outline: 1px dotted #000;
  }

  /* Labels */
  .lbl {
    font-size: 15px;
    margin-bottom: 3px;
    margin-top: 10px;
    color: #000;
  }

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
    color: #000;
  }

  .row { display: flex; gap: 8px; align-items: flex-end; }
  .row .grow { flex: 1; }

  /* Win95 raised button */
  button {
    font-family: 'VT323', 'Courier New', monospace;
    font-size: 16px;
    padding: 4px 16px;
    background: #c0c0c0;
    color: #000;
    border: 2px solid;
    border-color: #fff #404040 #404040 #fff;
    cursor: pointer;
    min-width: 80px;
    outline: none;
  }
  button:active {
    border-color: #404040 #fff #fff #404040;
    padding: 5px 15px 3px 17px;
  }
  button:focus {
    outline: 1px dotted #000;
    outline-offset: -4px;
  }
  button:disabled {
    color: #808080;
    text-shadow: 1px 1px #fff;
    cursor: default;
  }
  button:disabled:active {
    border-color: #fff #404040 #404040 #fff;
    padding: 4px 16px;
  }

  .buttons { display: flex; gap: 8px; margin-top: 12px; }

  /* Progress bar — Win95 chunky blocks */
  .progress-wrap {
    margin-top: 10px;
    border: 2px solid;
    border-color: #808080 #fff #fff #808080;
    height: 24px;
    background: #fff;
    position: relative;
    overflow: hidden;
  }
  .progress-bar {
    height: 100%; width: 0%;
    background: repeating-linear-gradient(
      90deg,
      #000080 0px, #000080 10px,
      transparent 10px, transparent 12px
    );
    transition: width 0.3s;
  }
  .progress-text {
    position: absolute; top: 0; left: 0; right: 0; bottom: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px;
    color: #000;
    mix-blend-mode: difference;
    font-family: 'VT323', monospace;
  }

  /* Log — sunken textarea look */
  .log {
    margin-top: 10px;
    border: 2px solid;
    border-color: #808080 #fff #fff #808080;
    background: #fff;
    padding: 6px;
    font-family: 'VT323', 'Courier New', monospace;
    font-size: 14px;
    line-height: 1.4;
    height: 170px;
    overflow-y: auto;
    color: #000;
    white-space: pre-wrap;
  }
  .log::-webkit-scrollbar { width: 16px; }
  .log::-webkit-scrollbar-track {
    background: #c0c0c0;
    border: 1px solid #808080;
  }
  .log::-webkit-scrollbar-thumb {
    background: #c0c0c0;
    border: 2px solid;
    border-color: #fff #404040 #404040 #fff;
  }

  .status {
    margin-top: 8px;
    font-size: 15px;
    color: #000;
    border: 2px solid;
    border-color: #808080 #fff #fff #808080;
    padding: 3px 6px;
    background: #c0c0c0;
    min-height: 22px;
  }
  .status.error { color: #ff0000; }
  .status.done { color: #008000; }
</style>
</head>
<body>

<div class="window">
  <div class="titlebar">
    <div class="titlebar-icon"></div>
    YouTube to Flashcard
  </div>
  <div class="window-inner">

    <div class="lbl">URL:</div>
    <input class="field" type="text" id="url" placeholder="https://www.youtube.com/watch?v=...">

    <div class="groupbox" style="margin-top:12px">
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
</div>

<script>
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

  pywebview.api.start_job(url, lang, output);
  pollStatus();
}

function cancelJob() {
  pywebview.api.cancel_job();
  document.getElementById('cancelBtn').disabled = true;
  document.getElementById('status').textContent = 'Cancelling...';
}

function openFolder() {
  pywebview.api.open_output();
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
</script>
</body>
</html>
"""


class Api:
    def __init__(self):
        self._cancelled = False
        self._output_dir = ""
        self._status = {
            "running": False,
            "progress": 0,
            "total": 0,
            "messages": [],
            "done": False,
            "error": None,
        }

    def start_job(self, url, lang, output):
        if self._status["running"]:
            return

        self._output_dir = os.path.abspath(output)
        self._cancelled = False
        self._status = {
            "running": True,
            "progress": 0,
            "total": 0,
            "messages": [],
            "done": False,
            "error": None,
        }

        lang = lang if lang else None

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

                _, num = process_video(
                    url, self._output_dir, lang=lang, progress_callback=cb
                )
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

    def open_output(self):
        if os.path.isdir(self._output_dir):
            subprocess.Popen(["open", self._output_dir])


if __name__ == "__main__":
    api = Api()
    window = webview.create_window(
        "YouTube to Flashcard",
        html=HTML,
        js_api=api,
        width=520,
        height=500,
        min_size=(420, 380),
    )
    webview.start()
