import argparse
import json
import os
import glob

def main():
    parser = argparse.ArgumentParser(description="Find sentences in JSON files and output timestamps.")
    parser.add_argument("-j", "--json-files", nargs="*", default=[], help="Specific JSON files to process")
    parser.add_argument("-f", "--folders", nargs="*", default=[], help="Folders containing *_sentence.json files")
    parser.add_argument("-o", "--output", default="found_sentences.json", help="Output JSON file name")
    parser.add_argument("-t", "--text", action="append", help="Sentences to find (specify multiple times or separate with '|')")
    args = parser.parse_args()

    # Collect JSON files from specified files and folders
    json_files = args.json_files
    for folder in args.folders:
        json_files.extend(glob.glob(os.path.join(folder, "*_sentence.json")))

    if not json_files:
        print("No JSON files to process.")
        return

    # Process sentences to find
    sentences = []
    for t in args.text or []:
        sentences.extend(s.strip() for s in t.split("|") if s.strip())
    if not sentences:
        print("No sentences provided. Use -t to specify sentences.")
        return

    results = []

    # Process each JSON file
    for json_file in json_files:
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
                grandparent_folder = os.path.basename(os.path.dirname(os.path.dirname(json_file)))
                file_name = os.path.basename(json_file)
                for entry in data:
                    text = entry["text"]
                    start = entry["start"]
                    end = entry["end"]
                    sentence_spans = entry.get("sentence_spans", [])
                    matching_sentences = []
                    for span in sentence_spans:
                        sentence = text[span[0]:span[1]].strip()
                        if sentence in sentences:
                            matching_sentences.append(sentence)
                    if matching_sentences:
                        results.append({
                            "folder": grandparent_folder,
                            "file": file_name,
                            "start": start,
                            "end": end,
                            "sentences": matching_sentences
                        })
        except FileNotFoundError:
            print(f"Warning: File {json_file} not found.")
        except json.JSONDecodeError:
            print(f"Warning: File {json_file} is not a valid JSON.")
        except KeyError as e:
            print(f"Warning: File {json_file} missing required field {e}.")

    if results:
        # Determine output path: processing/<output_base_name>/<output_file_name>
        output_base_name = os.path.splitext(os.path.basename(args.output))[0]
        output_dir = os.path.join("processing", output_base_name)
        output_path = os.path.join(output_dir, args.output)
        os.makedirs(output_dir, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=4)
        print(f"Output saved to {output_path}")
    else:
        print("No matches found.")

if __name__ == "__main__":
    main()