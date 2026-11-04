#!/usr/bin/env python3
"""Read text with Paradee and save an MP3. CLI options override the settings below."""

import argparse
from datetime import datetime
from pathlib import Path
import sys
from time import perf_counter


# Editable settings (MP3 quality is the bitrate in kbps).
DEFAULT_VOICE = "af_heart"
DEFAULT_OUTPUT = "paradee.mp3"
DEFAULT_QUALITY = 128

VOICES = ("af_heart", "bf_isabella", "am_puck", "bm_fable")
# MPEG-2 Layer III bitrates supported at Paradee's 24 kHz sample rate.
MP3_BITRATES = (8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read text with Paradee and save a mono MP3.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("text", nargs="?", help="text to speak; otherwise read stdin")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--text", dest="inline_text", help="text to speak")
    source.add_argument("--file", type=Path, help="UTF-8 text file to read")
    parser.add_argument("--voice", choices=VOICES, default=DEFAULT_VOICE,
                        help="voice to speak with")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT,
                        help="output MP3 filename")
    parser.add_argument("--quality", type=int, choices=MP3_BITRATES,
                        default=DEFAULT_QUALITY, help="MP3 bitrate in kbps")
    args = parser.parse_args(argv)

    if args.text is not None and (args.inline_text is not None or args.file is not None):
        parser.error("provide only one text source: positional text, --text, or --file")
    # Validate edited defaults too; argparse's choices only check supplied options.
    if args.voice not in VOICES:
        parser.error(f"invalid DEFAULT_VOICE; choose from {', '.join(VOICES)}")
    if args.quality not in MP3_BITRATES:
        parser.error(f"invalid DEFAULT_QUALITY; choose from {MP3_BITRATES} kbps")

    try:
        if args.file is not None:
            text = args.file.read_text(encoding="utf-8")
        elif args.inline_text is not None:
            text = args.inline_text
        elif args.text is not None:
            text = args.text
        elif not sys.stdin.isatty():
            text = sys.stdin.read()
        else:
            parser.error("provide text, --file, or pipe text through stdin")
    except (OSError, UnicodeError) as exc:
        parser.exit(1, f"error: could not read text: {exc}\n")
    if not text.strip():
        parser.error("text must not be empty or whitespace-only")

    started_at = datetime.now().astimezone()
    started_timer = perf_counter()
    print(f"Started at: {started_at.isoformat(timespec='seconds')}", flush=True)

    try:
        import lameenc
        import numpy as np
        from paradee import Paradee, SAMPLE_RATE
    except ImportError as exc:
        parser.exit(1, f"error: missing dependency ({exc}). Install with: "
                       "pip install -e '.[mp3]'\n")

    try:
        audio = Paradee()(text, voice=args.voice)
        if audio.size == 0:
            raise ValueError("the supplied text produced no speech")
        pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
        encoder = lameenc.Encoder()
        encoder.set_in_sample_rate(SAMPLE_RATE)
        encoder.set_out_sample_rate(SAMPLE_RATE)
        encoder.set_channels(1)
        encoder.set_bit_rate(args.quality)
        encoder.set_quality(2)
        mp3 = encoder.encode(pcm.tobytes()) + encoder.flush()
    except Exception as exc:
        parser.exit(1, f"error: speech generation or MP3 encoding failed: {exc}\n")

    try:
        args.output.write_bytes(mp3)
    except OSError as exc:
        parser.exit(1, f"error: could not save MP3: {exc}\n")
    elapsed = perf_counter() - started_timer
    ended_at = datetime.now().astimezone()
    print(f"wrote {args.output} ({len(audio) / SAMPLE_RATE:.1f} s, "
          f"{args.voice}, {args.quality} kbps)")
    print(f"Ended at: {ended_at.isoformat(timespec='seconds')}")
    print(f"Generation time: {elapsed:.2f} seconds")
    return 0


if __name__ == "__main__":
    sys.exit(main())

