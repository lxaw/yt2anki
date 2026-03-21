#!/usr/bin/env python3
"""CLI interface for YouTube to Flashcard."""

import argparse
import os
import sys

from core import process_video


def main():
    parser = argparse.ArgumentParser(
        description="Download a YouTube video and split it into per-sentence cards."
    )
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument(
        "-o", "--output", default="output",
        help="Output directory (default: ./output)",
    )
    parser.add_argument(
        "-l", "--lang", default=None,
        help="Caption language code, e.g. 'en', 'ja' (auto-detected if omitted)",
    )
    args = parser.parse_args()

    output_dir = os.path.abspath(args.output)

    def progress(current, total, msg):
        if total > 0:
            print(f"  [{current}/{total}] {msg[:60]}{'...' if len(msg) > 60 else ''}")
        else:
            print(msg)

    try:
        title, num_cards = process_video(
            args.url, output_dir, lang=args.lang, progress_callback=progress
        )
        print(f"\nDone! {num_cards} cards saved to {output_dir}/")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
