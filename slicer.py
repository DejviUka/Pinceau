#!/usr/bin/env python3
# slicer.py

import argparse
import json
import os
import subprocess
import sys
import tempfile
import shutil

def main():
    parser = argparse.ArgumentParser(
        description="Cut and stitch the precise speech spans from your findref JSON."
    )
    parser.add_argument(
        "-i", "--input", required=True,
        help="Base name → reads processing/<input>/<input>.json"
    )
    parser.add_argument(
        "-o", "--output", required=True,
        help="Base name → writes processed/<output>/<input>.mp4"
    )
    args = parser.parse_args()

    in_base  = args.input
    out_base = args.output

    json_path = os.path.join("processing", in_base, f"{in_base}.json")
    if not os.path.isfile(json_path):
        sys.exit(f"Error: JSON not found: {json_path}")

    segments = json.load(open(json_path, encoding="utf-8"))
    if not segments:
        sys.exit("ℹ No segments to cut; exiting.")

    out_dir = os.path.join("processed", out_base)
    os.makedirs(out_dir, exist_ok=True)
    final_vid = os.path.join(out_dir, f"{in_base}.mp4")

    tmp = tempfile.mkdtemp(prefix="slicer_")
    cuts = []

    for idx, seg in enumerate(segments):
        fld = seg["folder"]
        name = fld[:-6] if fld.endswith("_files") else fld
        src  = os.path.join(fld, f"{name}.mp4")
        if not os.path.isfile(src):
            print(f"⚠ Skipping missing video: {src}", file=sys.stderr)
            continue

        cut_path = os.path.join(tmp, f"{idx:03d}.mp4")
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", src,
            "-ss", f"{seg['start']:.3f}",
            "-to", f"{seg['end']:.3f}",
            "-c", "copy",
            cut_path
        ]
        print(f"[{idx}] Cutting {seg['start']:.3f}s–{seg['end']:.3f}s from {src}")
        subprocess.run(cmd, check=True)
        cuts.append(cut_path)

    if not cuts:
        sys.exit("ℹ No cuts made; exiting.")

    list_file = os.path.join(tmp, "list.txt")
    with open(list_file, "w") as lf:
        for c in cuts:
            lf.write(f"file '{c}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        final_vid
    ], check=True)

    shutil.rmtree(tmp)
    print(f"✅ Final video created at {final_vid}")

if __name__ == "__main__":
    main()
