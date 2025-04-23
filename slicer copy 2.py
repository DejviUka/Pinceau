#!/usr/bin/env python3
# slicer.py

import argparse
import json
import os
import subprocess
import sys
import tempfile
import shutil

import whisperx
from config_transcribe import device, model_size, compute_type, language

def transcribe_sentences(clip_path, model):
    """
    Perform sentence‐level transcription on clip_path.
    Returns list of segments with 'start'/'end' times relative to clip.
    """
    audio = whisperx.load_audio(clip_path)
    result = model.transcribe(audio, language=language)
    return result["segments"]

def cut_video(src, start, end, dst):
    """
    Cut [start,end] seconds from src → dst (frame‐accurate).
    """
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", src,
        "-ss", f"{start:.3f}",
        "-to", f"{end:.3f}",
        "-c", "copy",
        dst
    ]
    subprocess.run(cmd, check=True)

def main():
    parser = argparse.ArgumentParser(
        description="Cut & stitch speech spans aligned to full sentences via WhisperX."
    )
    parser.add_argument("-i","--input", required=True,
                        help="Base name → reads processing/<input>/<input>.json")
    parser.add_argument("-o","--output", required=True,
                        help="Base name → writes processed/<output>/<input>.mp4")
    args = parser.parse_args()

    in_base  = args.input
    out_base = args.output

    # 1) Load findref output
    json_path = os.path.join("processing", in_base, f"{in_base}.json")
    if not os.path.isfile(json_path):
        sys.exit(f"Error: JSON not found: {json_path}")
    entries = json.load(open(json_path, encoding="utf-8"))
    if not entries:
        sys.exit("ℹ No segments to cut; exiting.")

    # sort by original start time
    entries.sort(key=lambda e: e["start"])

    # 2) Prepare WhisperX model for sentence re‐transcription
    print(f"[INFO] Loading WhisperX model '{model_size}' on {device} ({compute_type})...")
    model = whisperx.load_model(model_size, device=device, compute_type=compute_type)

    # 3) Prepare output dirs
    processed_dir = os.path.join("processed", out_base)
    os.makedirs(processed_dir, exist_ok=True)
    final_vid = os.path.join(processed_dir, f"{in_base}.mp4")

    tmp_dir = tempfile.mkdtemp(prefix="slicer_")
    cut_clips = []

    # tolerance to detect partial sentences
    eps = 0.05

    for idx, ent in enumerate(entries):
        folder = ent["folder"]
        base = folder[:-6] if folder.endswith("_files") else folder
        video_file = os.path.join(folder, f"{base}.mp4")
        if not os.path.isfile(video_file):
            print(f"⚠ Missing video: {video_file}, skipping", file=sys.stderr)
            continue

        # initial cut on findref times
        init_clip = os.path.join(tmp_dir, f"{idx:03d}_init.mp4")
        cut_video(video_file, ent["start"], ent["end"], init_clip)
        clip_duration = ent["end"] - ent["start"]

        # re‐transcribe the clip to get exact sentence boundaries
        segs = transcribe_sentences(init_clip, model)
        if not segs:
            print(f"⚠ No sentence segments in clip {idx}, removing", file=sys.stderr)
            os.remove(init_clip)
            continue

        # drop first if partial at start, drop last if partial at end
        first, last = segs[0], segs[-1]
        new_start = first["start"] if first["start"] > eps else 0.0
        new_end   = last["end"]   if last["end"]   < clip_duration - eps else clip_duration

        # if trimming needed, produce a trimmed clip
        if new_start > eps or new_end < clip_duration - eps:
            trim_clip = os.path.join(tmp_dir, f"{idx:03d}_trim.mp4")
            cut_video(init_clip, new_start, new_end, trim_clip)
            os.remove(init_clip)
            final_clip = trim_clip
            print(f"[{idx}] Trimmed partial sentences → {new_start:.3f}-{new_end:.3f}s")
        else:
            final_clip = init_clip
            print(f"[{idx}] Contains full sentences → keeping entire clip")

        cut_clips.append(final_clip)

    if not cut_clips:
        shutil.rmtree(tmp_dir)
        sys.exit("ℹ No valid clips after trimming; exiting.")

    # 4) Concatenate all final clips
    list_txt = os.path.join(tmp_dir, "concat.txt")
    with open(list_txt, "w") as f:
        for clip in cut_clips:
            f.write(f"file '{clip}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0",
        "-i", list_txt,
        "-c", "copy",
        final_vid
    ], check=True)

    shutil.rmtree(tmp_dir)
    print(f"✅ Final video created at {final_vid}")

if __name__ == "__main__":
    main()
