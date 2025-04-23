# transcribe.py use py -3.10 on work pc


import argparse
import os
import json
import whisperx
from tqdm import tqdm
from config_transcribe import device, model_size, compute_type, language

def transcribe(video_path, sentence_level=False, word_level=False):
    print(f"[INFO] Loading model '{model_size}' on {device} with {compute_type} precision...")
    model = whisperx.load_model(model_size, device=device, compute_type=compute_type)

    audio = whisperx.load_audio(video_path)
    print(f"[INFO] Running transcription{' (lang='+language+')' if language else ''}...")
    result = model.transcribe(audio, language=language)

    # load alignment model
    # load alignment model
    print("[INFO] Loading alignment model...")
    align_model, metadata = whisperx.load_align_model(
        language_code=language or result["language"],
        device=device
    )


    # align each segment with a progress bar
    word_segments = []
    if word_level:
        print("[INFO] Aligning segments for word-level timestamps:")
        for segment in tqdm(result["segments"], desc="Aligning", unit="segment"):
            out = whisperx.align([segment], align_model, metadata, audio, device=device)
            word_segments.extend(out["word_segments"])

    # prepare output folder
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    output_folder = os.path.join(f"{video_name}_files", "transcribed")
    os.makedirs(output_folder, exist_ok=True)

    # word-level JSON
    if word_level:
        word_path = os.path.join(output_folder, f"{video_name}_word.json")
        with open(word_path, "w", encoding="utf-8") as wf:
            json.dump(word_segments, wf, indent=2, ensure_ascii=False)
        print(f"[✔] Word-level transcription → {word_path}")

    # sentence-level JSON
    if sentence_level:
        sentence_path = os.path.join(output_folder, f"{video_name}_sentence.json")
        with open(sentence_path, "w", encoding="utf-8") as sf:
            json.dump(result["segments"], sf, indent=2, ensure_ascii=False)
        print(f"[✔] Sentence-level transcription → {sentence_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Transcribe with WhisperX (sentence/word-level) using config_transcribe.py"
    )
    parser.add_argument("video_path", help="Path to video/audio file")
    parser.add_argument("-s", "--sentence", action="store_true", help="Enable sentence-level transcription")
    parser.add_argument("-w", "--word", action="store_true", help="Enable word-level transcription")
    args = parser.parse_args()

    if not (args.sentence or args.word):
        print("⚠ Please specify at least one of -s (sentence) or -w (word).")
        exit(1)

    transcribe(args.video_path, sentence_level=args.sentence, word_level=args.word)
