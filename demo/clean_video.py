"""One command to tidy a screen recording with your voice (e.g. from QuickTime):

    .venv/bin/python demo/clean_video.py ~/Downloads/my-demo.mov

It writes my-demo_clean.mov next to the original (the original is never changed) and prints what it did.

1. Cleans the sound:
   - cuts low rumble (below 80 Hz) and removes clicks (mouse, keyboard, mouth),
   - learns the room's background noise from the first quiet stretch and removes it,
   - raises the voice to normal online-video loudness (-16 LUFS) with a fixed boost (so silence stays silent),
     and a limiter so loud moments don't distort,
   - optional: subtle background music that dips while you talk (--music soft, or --music my-track.mp3),
   - a very soft "room tone" under everything (--room-tone, default -52 dB; 'off' for none).
2. Removes dead air:
   - silence at the very start and end is cut,
   - long pauses are shortened to about half a second,
   - BUT a pause is kept wherever the screen is changing (a page loading, the assistant answering, scrolling),
     so nothing that happens on screen is skipped. Only the parts of a pause where the screen is still are cut.

Options: --keep-pauses (only clean the sound), --pad 0.25 (seconds kept on each side of a cut),
--min-pause 0.6 (shorter pauses are left alone).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def duration(path: Path) -> float:
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                      str(path)]).stdout.strip())


def intervals(log: str, kind: str, end: float) -> list[tuple[float, float]]:
    """Pairs of <kind>_start / <kind>_end from an ffmpeg detect filter's log."""
    st = [float(x) for x in re.findall(rf"{kind}_start: ([\d.]+)", log)]
    en = [float(x) for x in re.findall(rf"{kind}_end: ([\d.]+)", log)]
    if len(en) < len(st):
        en.append(end)
    return list(zip(st, en))


def merge(spans: list[tuple[float, float]], gap: float) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for s, e in sorted(spans):
        if out and s - out[-1][1] < gap:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def overlap(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out = []
    for s1, e1 in a:
        for s2, e2 in b:
            s, e = max(s1, s2), min(e1, e2)
            if e > s:
                out.append((s, e))
    return out


# A soft ambient pad (Cmaj7, Am7, Fmaj7, G6; 4 s each, slow swells), made by ffmpeg itself: no download, no licence.
_CHORDS = [(261.63, 329.63, 392.00, 493.88), (220.00, 261.63, 329.63, 392.00),
           (174.61, 220.00, 261.63, 329.63), (196.00, 246.94, 293.66, 329.63)]


def soft_pad(seconds: float) -> str:
    """An ffmpeg source (filtergraph string) for a gentle chord pad, `seconds` long."""
    k = "mod(floor(t/4),4)"
    note = lambda i: "if(eq({k},0),{a},if(eq({k},1),{b},if(eq({k},2),{c},{d})))".format(
        k=k, a=_CHORDS[0][i], b=_CHORDS[1][i], c=_CHORDS[2][i], d=_CHORDS[3][i])
    env = "(0.5-0.5*cos(2*PI*(t-4*floor(t/4))/4))"            # each chord swells in and out
    voices = "+".join(f"sin(2*PI*{note(i)}*t)" for i in range(4))
    bass = f"0.6*sin(2*PI*({note(0)})/2*t)"
    expr = f"0.12*{env}*({voices}+{bass})"
    return (f"aevalsrc='{expr}':s=48000:d={seconds:.2f},lowpass=f=1800,"
            "aecho=0.8:0.6:90|180:0.25|0.15,afade=t=in:d=2")


def level_db(path: Path, start: float, end: float) -> float | None:
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-ss", str(start), "-to", str(end), "-i", str(path), "-vn",
             "-af", "astats=measure_overall=RMS_level:measure_perchannel=none", "-f", "null", "-"])
    m = re.findall(r"RMS level dB: (-?[\d.]+|-inf)", r.stderr)
    return None if not m else (-120.0 if m[-1] == "-inf" else float(m[-1]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--keep-pauses", action="store_true", help="only clean the sound; cut nothing")
    ap.add_argument("--pad", type=float, default=0.25, help="seconds of pause kept on each side of a cut")
    ap.add_argument("--min-pause", type=float, default=0.6, help="pauses shorter than this are left alone")
    ap.add_argument("--music", default=None,
                    help="subtle background music that dips while you speak: 'soft' (a gentle pad made by ffmpeg) "
                         "or a path to a royalty-free track (mp3/m4a/wav; it loops if short)")
    ap.add_argument("--music-level", type=float, default=-30.0,
                    help="music loudness in dB when you're not speaking (default -30; voice is about -16)")
    ap.add_argument("--room-tone", default="off",
                    help="optional soft room sound under everything, in dB (e.g. -52). Off by default: the PM preferred silent gaps")
    args = ap.parse_args()
    src = args.video.expanduser()
    if not src.exists():
        print(f"Can't find {src}")
        return 2
    out = args.out or src.with_name(src.stem + "_clean.mov")
    dur = duration(src)

    # ---- 1. sound: find a quiet stretch to learn the noise from, then measure loudness
    quiet = intervals(run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-vn", "-af",
                           "silencedetect=noise=-40dB:d=0.6", "-f", "null", "-"]).stderr, "silence", dur)
    learn = next(((s + 0.1, min(e - 0.1, s + 2.0)) for s, e in quiet if e - s > 0.6), None)
    denoise = "highpass=f=80,adeclick=w=55:o=75," + (f"asendcmd=c='{learn[0]:.2f} afftdn sn start; {learn[1]:.2f} afftdn sn stop',"
                                  if learn else "") + "afftdn=nr=12:nf=-50:tn=1"
    meas = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-vn", "-af",
                f"{denoise},loudnorm=I=-16:TP=-1.5:print_format=json", "-f", "null", "-"]).stderr
    loud = float(json.loads(meas[meas.rindex("{"):meas.rindex("}") + 1])["input_i"])
    gain = max(min(-16.0 - loud, 20.0), 0.0) if loud > -70 else 0.0
    sound = f"{denoise},volume={gain:.1f}dB,alimiter=limit=0.84:level=false"

    # ---- 2. pauses: silent AND the screen is still
    keep = [(0.0, dur)]
    cut_n = kept_n = 0
    if not args.keep_pauses:
        silences = merge(intervals(run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-vn", "-af",
                                        f"{denoise},silencedetect=noise=-45dB:d={args.min_pause}", "-f", "null",
                                        "-"]).stderr, "silence", dur), 0.35)
        still = intervals(run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-an", "-vf",
                               "scale=480:-2,freezedetect=n=0.003:d=0.4", "-f", "null", "-"]).stderr,
                          "lavfi.freezedetect.freeze", dur)
        cuts = []
        for s, e in overlap(silences, still):
            a = 0.0 if s < 0.5 else s + args.pad                   # very start / very end: cut it all
            b = dur if dur - e < 0.5 else e - args.pad
            if b - a >= 0.3:
                cuts.append((a, b))
        cuts = merge(cuts, 0.05)
        cut_n = len(cuts)
        kept_n = sum(1 for s, e in silences if not any(c[0] < e and c[1] > s for c in cuts))
        keep, cur = [], 0.0
        for a, b in cuts:
            if a - cur > 0.05:
                keep.append((cur, a))
            cur = b
        if dur - cur > 0.05:
            keep.append((cur, dur))

    # ---- 3. render. Room tone: brown noise, band-limited, at a fixed level (calibrated: this filter chain at
    # amplitude 1 measures -16.4 dB RMS), laid under the whole cleaned voice track.
    total = sum(b - a for a, b in keep)
    tone = None if str(args.room_tone).lower() == "off" else float(args.room_tone)
    tone_chain = (f";anoisesrc=color=brown:amplitude=1:sample_rate=48000:duration={total + 1:.2f},highpass=f=100,"
                  f"lowpass=f=3000,volume={tone + 16.4:.1f}dB[rt];[vo][rt]amix=inputs=2:normalize=0:duration=first[vt]"
                  if tone is not None else ";[vo]anull[vt]")
    extra_inputs: list[str] = []
    if args.music:
        if args.music == "soft":
            src_m = soft_pad(total + 1) + ",aformat=channel_layouts=stereo"
            music_in = f";{src_m},loudnorm=I={args.music_level}:TP=-6[mraw]"
        else:
            extra_inputs = ["-stream_loop", "-1", "-i", str(Path(args.music).expanduser())]
            music_in = (f";[1:a]atrim=0:{total + 1:.2f},aresample=48000,aformat=channel_layouts=stereo,"
                        f"loudnorm=I={args.music_level}:TP=-6,afade=t=in:d=2[mraw]")
        # the music dips about 5 dB whenever you speak (sidechain "ducking"), then eases back up in the pauses
        tone_chain += (music_in + f";[vt]asplit=2[vk][vs];[mraw]afade=t=out:st={max(total - 2.5, 0):.2f}:d=2.5[mf];"
                       "[mf][vs]sidechaincompress=threshold=0.03:ratio=2.5:attack=40:release=700:makeup=1[md];"
                       "[vk][md]amix=inputs=2:normalize=0:duration=first[a]")
    else:
        tone_chain += ";[vt]anull[a]"
    if len(keep) == 1 and keep[0] == (0.0, dur):
        graph = f"[0:a]{sound},aresample=48000[vo]" + tone_chain
        r = run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), *extra_inputs, "-filter_complex", graph, "-map", "0:v",
                 "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(out)])
    else:
        parts = [f"[0:a]{sound},aresample=48000[cl]", f"[cl]asplit={len(keep)}" +
                 "".join(f"[s{i}]" for i in range(len(keep))), f"[0:v]split={len(keep)}" +
                 "".join(f"[w{i}]" for i in range(len(keep)))]
        for i, (a, b) in enumerate(keep):
            parts.append(f"[w{i}]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS[v{i}]")
            parts.append(f"[s{i}]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.03,"
                         f"afade=t=out:st={max(b - a - 0.03, 0):.3f}:d=0.03[a{i}]")
        parts.append("".join(f"[v{i}][a{i}]" for i in range(len(keep))) + f"concat=n={len(keep)}:v=1:a=1[v][vo]")
        r = run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), *extra_inputs, "-filter_complex",
                 ";".join(parts) + tone_chain,
                 "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                 "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(out)])
    if r.returncode != 0:
        print(r.stderr[-1500:])
        return 1

    before = level_db(src, *learn) if learn else None
    print(f"Done: {out}")
    print(f"- Length: {dur:.1f} s -> {duration(out):.1f} s")
    if not args.keep_pauses:
        print(f"- Pauses cut or shortened: {cut_n}; kept because the screen was changing: {kept_n}")
    print(f"- Voice loudness: {loud:.0f} LUFS -> about -16 LUFS (boost {gain:.1f} dB); clicks removed")
    print(f"- Room tone under everything: {'off' if tone is None else f'{tone:.0f} dB (soft, masks leftover hiss)'}")
    if args.music:
        print(f"- Background music: {'soft pad (generated)' if args.music == 'soft' else args.music}, "
              f"about {args.music_level:.0f} dB in the pauses, dipping while you speak")
    if before is not None:
        print(f"- Background noise in the quiet stretch it learned from: {before:.0f} dB "
              f"({'already silent' if before < -60 else 'removed'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
