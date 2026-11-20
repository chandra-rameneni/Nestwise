"""Cleans your voice recording (removes background noise, evens out the volume) and puts it on the walkthrough video.

    .venv/bin/python demo/add_voice.py ~/Desktop/my-voice.m4a
    .venv/bin/python demo/add_voice.py my-voice.m4a --video demo/recordings/<time>/walkthrough.mp4 --offset 3

How to record so this works best:
1. Start recording, then stay completely silent for 3 seconds. The tool learns your room's noise (fan, AC, hum)
   from that quiet stretch and removes it from everything.
2. Then press play on the walkthrough video and talk over it, following the teleprompter in DEMO_SCRIPT.md.
3. Any recorder works (QuickTime: File > New Audio Recording; or Voice Memos). Any format ffmpeg reads is fine.

What it does, in order (all built into ffmpeg, nothing downloaded):
- learns the noise from 0.5 s to 2.5 s and removes it (afftdn, which keeps tracking the noise as it changes),
- cuts rumble below 80 Hz and hiss above 12 kHz,
- quietly lowers what's left between your sentences (a soft gate, so breaths and room tone don't creep back),
- evens out the loudness to -16 LUFS, the usual level for online video,
- drops the first --offset seconds (the silent stretch) so your voice lines up with the video.
It prints the background noise level before and after, so you can see the difference.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CLEAN = ("asendcmd=c='0.5 afftdn sn start; 2.5 afftdn sn stop',"
         "afftdn=nr=24:nf=-45:tn=1,"
         "highpass=f=80,lowpass=f=12000,"
         "agate=threshold=0.012:ratio=3:attack=10:release=250:range=0.12,"
         "loudnorm=I=-16:TP=-1.5:LRA=11")


def noise_db(path: Path, start: float, end: float) -> float | None:
    """RMS level (dB) of a stretch that should be silent."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-ss", str(start), "-to", str(end), "-i", str(path),
                        "-af", "astats=measure_overall=RMS_level:measure_perchannel=none", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.findall(r"RMS level dB: (-?[\d.]+|-inf)", r.stderr)
    return None if not m else (-120.0 if m[-1] == "-inf" else float(m[-1]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("voice", type=Path, help="your recording")
    ap.add_argument("--video", type=Path, default=None, help="default: the newest demo/recordings/*/walkthrough.mp4")
    ap.add_argument("--offset", type=float, default=3.0, help="seconds of silence at the start to drop (default 3)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if not args.voice.exists():
        print(f"Can't find {args.voice}")
        return 2
    video = args.video
    if video is None:
        found = sorted((ROOT / "demo" / "recordings").glob("*/walkthrough.mp4"))
        if not found:
            print("No walkthrough video yet. Run demo/record_walkthrough.py first.")
            return 2
        video = found[-1]
    folder = video.parent
    clean = folder / "voice_clean.wav"
    out = args.out or folder / "final.mp4"

    before = noise_db(args.voice, 0.5, 2.5)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(args.voice), "-af", CLEAN, "-ar", "48000",
                    "-ac", "1", str(folder / "voice_full_clean.wav")], check=True)
    after = noise_db(folder / "voice_full_clean.wav", 0.5, 2.5)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(args.offset), "-i",
                    str(folder / "voice_full_clean.wav"), str(clean)], check=True)
    (folder / "voice_full_clean.wav").unlink(missing_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(clean), "-map", "0:v",
                    "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(out)], check=True)

    if before is not None and after is not None:
        print(f"Background noise: {before:.0f} dB before, {after:.0f} dB after (lower is quieter; "
              f"below -60 dB is effectively silent).")
    if before is not None and before > -35:
        print("Note: the first 3 seconds were loud. Did you stay silent at the start? If not, record again, or "
              "use --offset 0 so nothing is cut.", file=sys.stderr)
    print(f"Clean voice: {clean}\nFinal video: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
