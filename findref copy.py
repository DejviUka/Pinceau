#!/usr/bin/env python3
import argparse
import glob
import json
import os
import re

from config_findref import ROUNDNESS_MS

def split_into_sentences(text):
    """
    Naïve sentence splitter on ., ! or ? followed by whitespace.
    """
    return [
        s.strip() 
        for s in re.split(r'(?<=[.!?])\s+', text.strip())
        if s
    ]

def main():
    parser = argparse.ArgumentParser(
        description="Find and group sentences in JSON files based on proximity."
    )
    parser.add_argument(
        "-j", "--json-files", nargs="*", default=[],
        help="Specific JSON files to process"
    )
    parser.add_argument(
        "-f", "--folders", nargs="*", default=[],
        help="Folders containing *_sentence.json files"
    )
    parser.add_argument(
        "-t", "--text", action="append",
        help="Text or paragraph(s) to search (each -t can contain multiple sentences)"
    )
    parser.add_argument(
        "-o", "--output", default="found_sentences.json",
        help="Output JSON file name"
    )
    args = parser.parse_args()

    # 1) Collect JSON files
    json_files = list(args.json_files)
    for folder in args.folders:
        json_files.extend(glob.glob(os.path.join(folder, "*_sentence.json")))

    if not json_files:
        print("No JSON files to process.")
        return

    # 2) Break input paragraphs into individual sentences
    sentences = []
    for t in args.text or []:
        sentences.extend(split_into_sentences(t))
    if not sentences:
        print("No sentences provided. Use -t to specify sentences.")
        return
    sentences_set = set(sentences)

    results = []

    # 3) Process each file
    for json_file in json_files:
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Cannot read {json_file}: {e}")
            continue

        # for reporting
        grandparent = os.path.basename(os.path.dirname(os.path.dirname(json_file)))
        fname = os.path.basename(json_file)

        for entry in data:
            text = entry.get("text", "")
            entry_start = entry.get("start")
            if entry_start is None:
                print(f"Warning: Entry missing 'start' in {json_file}")
                continue

            spans = entry.get("sentence_spans", [])
            # Gather all matching sentences with absolute timestamps
            matches = []
            for start_off, end_off in spans:
                s = text[start_off:end_off].strip()
                if s in sentences_set:
                    matches.append({
                        "sentence": s,
                        "start": entry_start + start_off,
                        "end":   entry_start + end_off
                    })

            # If we found matches, group them by proximity
            if matches:
                matches.sort(key=lambda x: x["start"])
                grouped = []
                current = [matches[0]]
                for m in matches[1:]:
                    if m["start"] - current[-1]["end"] <= ROUNDNESS_MS:
                        current.append(m)
                    else:
                        grouped.append(current)
                        current = [m]
                grouped.append(current)

                # Emit one result per group
                for grp in grouped:
                    results.append({
                        "folder":    grandparent,
                        "file":      fname,
                        "start":     grp[0]["start"],
                        "end":       grp[-1]["end"],
                        "sentences": [m["sentence"] for m in grp]
                    })

    # 4) Write output
    if results:
        base = os.path.splitext(os.path.basename(args.output))[0]
        out_dir = os.path.join("processing", base)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, args.output)
        with open(out_path, "w") as f:
            json.dump(results, f, indent=4)
        print(f"Output saved to {out_path}")
    else:
        print("No matches found.")

if __name__ == "__main__":
    main()
