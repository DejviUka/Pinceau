#!/usr/bin/env python3
# slicer.py

import argparse
import json
import os
import subprocess
import sys
import tempfile
import shutil

from config_transcribe import SILENCE_BETWEEN_CLIPS_S

def cut_segment(src, start_s, end_s, dst):
    """
    Frame‐accurate copy‐codec cut from src at [start_s, end_s] → dst.
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
        description="Cut & stitch speech spans with stable silence between them."
    )
    p.add_argument(
        "-i", "--input", required=True,
        help="Base name → reads processing/<input>/<input>.json"
    )
    p.add_argument(
        "-o", "--output", required=True,
        help="Base name → writes processed/<output>/<input>.mp4"
    )
    args = p.parse_args()

    in_base  = args.input
    out_base = args.output

    # 1) Load findref JSON
    js = os.path.join("processing", in_base, f"{in_base}.json")
    if not os.path.isfile(js):
        sys.exit(f"Error: JSON not found: {js}")
    entries = json.load(open(js, encoding="utf-8"))
    if not entries:
        sys.exit("ℹ No segments to cut; exiting.")

    # 2) Sort by original start
    entries.sort(key=lambda e: (e["folder"], e["start"]))

    # 3) Prepare output dirs
    out_dir = os.path.join("processed", out_base)
    os.makedirs(out_dir, exist_ok=True)
    final_vid = os.path.join(out_dir, f"{in_base}.mp4")

    tmp = tempfile.mkdtemp(prefix="slicer_")
    clips = []
    half_pad = SILENCE_BETWEEN_CLIPS_S / 2.0

    # 4) Build padded clip list
    for idx, ent in enumerate(entries):
        folder = ent["folder"]
        name   = folder[:-6] if folder.endswith("_files") else folder
        src    = os.path.join(folder, f"{name}.mp4")
        if not os.path.isfile(src):
            print(f"⚠ Missing video {src}, skipping", file=sys.stderr)
            continue

        st, en = ent["start"], ent["end"]

        # compute pad_before
        if idx > 0 and entries[idx-1]["folder"] == ent["folder"]:
            prev_end = entries[idx-1]["end"]
            gap = st - prev_end
            pad_before = min(half_pad, gap/2.0)
        else:
            pad_before = half_pad

        # compute pad_after
        if idx < len(entries)-1 and entries[idx+1]["folder"] == ent["folder"]:
            next_start = entries[idx+1]["start"]
            gap2 = next_start - en
            pad_after = min(half_pad, gap2/2.0)
        else:
            pad_after = half_pad

        cs = max(0.0, st - pad_before)
        ce = en + pad_after

        clips.append({"src": src, "start": cs, "end": ce})
        print(f"[{idx:02d}] clip: {cs:.3f}s → {ce:.3f}s from {src}")

    if not clips:
        shutil.rmtree(tmp)
        sys.exit("ℹ No clips to cut; exiting.")

    # 5) Cut each padded segment
    cut_paths = []
    for i, c in enumerate(clips):
        outp = os.path.join(tmp, f"{i:03d}.mp4")
        cut_segment(c["src"], c["start"], c["end"], outp)
        cut_paths.append(outp)

    # 6) Write ffmpeg concat list & stitch
    list_txt = os.path.join(tmp, "list.txt")
    with open(list_txt, "w") as f:
        for pth in cut_paths:
            f.write(f"file '{pth}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0",
        "-i", list_txt,
        "-c", "copy",
        final_vid
    ], check=True)

    shutil.rmtree(tmp)
    print(f"✅ Final video created at {final_vid}")

if __name__ == "__main__":
    main()
