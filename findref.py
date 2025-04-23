#!/usr/bin/env python3
import argparse
import glob
import json
import os
import re
from config_findref import GROUP_GAP_S

def split_into_sentences(text):
    return [
        s.strip()
        for s in re.split(r'(?<=[.!?])\s+', text.strip())
        if s
    ]

def main():
    p = argparse.ArgumentParser(
        description="Locate WhisperX segments that contain your sentences."
    )
    p.add_argument("-f","--folders", nargs="*", default=[],
                   help="Folders containing *_sentence.json")
    p.add_argument("-t","--text", action="append", required=True,
                   help="Paragraph(s) to search (each -t can have multiple sentences)")
    p.add_argument("-o","--output", default="found.json",
                   help="Name for output JSON (written to processing/<output>/<output>.json)")
    args = p.parse_args()

    # build sentence set
    sentences = []
    for block in args.text:
        sentences.extend(split_into_sentences(block))
    S = set(sentences)

    # gather all sentence-level JSONs
    files = []
    for d in args.folders:
        files += glob.glob(os.path.join(d, "*_sentence.json"))
    if not files:
        print("❌ No *_sentence.json files found.", file=sys.stderr)
        return

    hits = []
    for path in files:
        data = json.load(open(path, encoding="utf-8"))
        grand = os.path.basename(os.path.dirname(os.path.dirname(path)))
        fname = os.path.basename(path)
        for seg in data:
            txt = seg["text"]
            found = [s for s in S if s in txt]
            if not found: continue
            hits.append({
                "folder":   grand,
                "file":     fname,
                "start":    seg["start"],
                "end":      seg["end"],
                "sentences": found
            })

    # optionally merge if segments are very close
    hits.sort(key=lambda x: x["start"])
    out = []
    if hits:
        cur = hits[0].copy()
        for nxt in hits[1:]:
            if nxt["start"] - cur["end"] <= GROUP_GAP_S:
                cur["end"] = max(cur["end"], nxt["end"])
                cur["sentences"].extend(nxt["sentences"])
            else:
                out.append(cur)
                cur = nxt.copy()
        out.append(cur)

    # write
    base = os.path.splitext(args.output)[0]
    odir = os.path.join("processing", base)
    os.makedirs(odir, exist_ok=True)
    out_path = os.path.join(odir, f"{base}.json")
    json.dump(out, open(out_path, "w", encoding="utf-8"), indent=2)
    print(f"✅ Found {len(out)} segment(s) → {out_path}")

if __name__ == "__main__":
    main()
