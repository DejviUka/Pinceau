#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import tempfile
import shutil

from config_transcribe import SILENCE_BETWEEN_CLIPS_S

def force_keyframes(src, times, dst):
    """
    Re-encode `src` to `dst`, forcing keyframes at each timestamp in `times`.
    Uses a fast x264 preset and copies audio.
    """
    # build comma-separated list of times like "12.345,67.890,…"
    times_str = ",".join(f"{t:.3f}" for t in sorted(set(times)))
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", src,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-force_key_frames", times_str,
        "-c:a", "copy",
        dst
    ]
    print(f"⟳ Forcing keyframes in {os.path.basename(src)} at {times_str}")
    subprocess.run(cmd, check=True)

def cut_segment(src, start_s, end_s, dst):
    """
    Frame-accurate cut [start_s,end_s] from `src` → `dst`, copying codecs.
    """
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", src,
        "-ss", f"{start_s:.3f}",
        "-to", f"{end_s:.3f}",
        "-c", "copy",
        dst
    ]
    subprocess.run(cmd, check=True)

def main():
    p = argparse.ArgumentParser(
        description="Cut only your matched sentences—no freezing—via forced keyframes."
    )
    p.add_argument("-i","--input", required=True,
                   help="Base name of findref run (reads processing/<input>/<input>.json)")
    p.add_argument("-o","--output", required=True,
                   help="Base name for output (writes processed/<output>/<input>.mp4)")
    args = p.parse_args()

    # 1) load findref JSON
    in_base = args.input
    proc_json = os.path.join("processing", in_base, f"{in_base}.json")
    if not os.path.isfile(proc_json):
        sys.exit(f"Error: JSON not found: {proc_json}")
    entries = json.load(open(proc_json, encoding="utf-8"))
    if not entries:
        sys.exit("ℹ No segments found → nothing to cut.")

    # 2) collect each unique video and its sentence-start times
    video_times = {}
    for e in entries:
        fld = e["folder"]
        # derive base video name
        base = fld[:-6] if fld.endswith("_files") else fld
        video_path = os.path.join(fld, f"{base}.mp4")
        if not os.path.isfile(video_path):
            print(f"⚠ Video missing: {video_path}", file=sys.stderr)
            continue
        video_times.setdefault(video_path, []).append(e["start"])

    # 3) set up temp workspace
    tmp = tempfile.mkdtemp(prefix="slicer_")
    keyed_dir = os.path.join(tmp, "keyed")
    os.makedirs(keyed_dir, exist_ok=True)

    # 4) force keyframes in each source video
    keyed_map = {}
    for src, times in video_times.items():
        base = os.path.splitext(os.path.basename(src))[0]
        dst = os.path.join(keyed_dir, f"{base}.mp4")
        force_keyframes(src, times, dst)
        keyed_map[src] = dst

    # 5) prepare output
    out_dir = os.path.join("processed", args.output)
    os.makedirs(out_dir, exist_ok=True)
    final_out = os.path.join(out_dir, f"{in_base}.mp4")

    # 6) cut each segment (with optional silence padding)
    half_sil = SILENCE_BETWEEN_CLIPS_S / 2.0
    cuts = []
    for idx, e in enumerate(entries):
        fld = e["folder"]
        base = fld[:-6] if fld.endswith("_files") else fld
        orig = os.path.join(fld, f"{base}.mp4")
        src = keyed_map.get(orig, orig)  # fallback to original if keying failed

        st, en = e["start"], e["end"]
        # pad half-silence before/after each cut
        cs = max(0.0, st - half_sil)
        ce = en + half_sil

        out_clip = os.path.join(tmp, f"{idx:03d}.mp4")
        print(f"[{idx}] Cutting {cs:.3f}s → {ce:.3f}s from {os.path.basename(src)}")
        cut_segment(src, cs, ce, out_clip)
        cuts.append(out_clip)

    if not cuts:
        shutil.rmtree(tmp)
        sys.exit("ℹ No cuts were made; exiting.")

    # 7) concatenate all clips
    list_txt = os.path.join(tmp, "list.txt")
    with open(list_txt, "w") as lf:
        for c in cuts:
            lf.write(f"file '{c}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0",
        "-i", list_txt,
        "-c", "copy",
        final_out
    ], check=True)

    shutil.rmtree(tmp)
    print(f"✅ Finished: {final_out}")

if __name__ == "__main__":
    main()
