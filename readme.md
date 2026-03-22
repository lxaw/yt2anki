# YouTube to Flashcard

Turn any captioned YouTube video into study-ready flashcard assets — one folder per caption line, each containing an audio clip, a video frame, and the subtitle text.

![YouTube to Flashcard app](example_screenshot.png)

## What It Does

1. Downloads a YouTube video via `yt-dlp`
2. Extracts captions (manual or auto-generated)
3. Splits the video into per-sentence segments
4. Saves each segment as a **card** folder:

```
card_001/
  audio.mp3   — the spoken line
  frame.jpg   — screenshot from that moment
  text.txt    — the caption text
```

## Example Output

Source: [Resident Evil Requiem #09](https://www.youtube.com/watch?v=lwTqv3m1SSs) (German auto-captions)

**Frame:**

![Card 008 frame](output/card_008/frame.jpg)

**Text:**
```
gerade glaube ich hier ein bisschen
```

**Audio:** [Listen to audio clip](output/card_008/audio.mp3)

## Requirements

- Python 3.10+
- [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) on your PATH
- [`ffmpeg`](https://ffmpeg.org/) on your PATH

## Quick Start

### Install Python dependencies

```bash
pip install pywebview psutil
```

### Run the desktop app

```bash
python app.py
```

### Or use the CLI

```bash
python youtube_to_cards.py "https://www.youtube.com/watch?v=VIDEO_ID"
python youtube_to_cards.py "https://www.youtube.com/watch?v=VIDEO_ID" -o my_cards -l de
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `-o`, `--output` | Output directory | `output` |
| `-l`, `--lang` | Caption language code (e.g. `en`, `de`, `ja`) | auto-detect |

## Notes

- Only works with videos that have captions (manual or auto-generated). Videos without captions will show an error.
- YouTube may rate-limit subtitle downloads — if you get a 429 error, wait a moment and retry, or specify the video's native language with `-l`.
- Auto-generated captions are automatically de-duplicated to remove repeated fragments.
